"""Fix Pack 16: giving reports, member statements, and the encrypted nightly backup."""
import os
from datetime import date, timedelta

from conftest import ADMIN_PASSWORD, BACKEND

REPO = os.path.dirname(BACKEND)
STAFF = 'Staff-Login-13579'
B_PASS = 'Second-Church-2468'
D = date.today()


def login(client, username, password):
    res = client.post('/api/auth/login', json={'username': username, 'password': password})
    assert res.status_code == 200, res.get_json()
    return {'Authorization': 'Bearer ' + res.get_json()['access_token']}


def admin(client):
    return login(client, 'admin', ADMIN_PASSWORD)


def money(client, h, kind, amount, day, **extra):
    body = dict(transaction_type=kind, amount=amount, transaction_date=day.isoformat(), **extra)
    res = client.post('/api/finance/', headers=h, json=body)
    assert res.status_code == 201, res.get_json()
    return res.get_json()['id']


def test_giving_report_totals_a_period_and_skips_voided(client):
    a = admin(client)
    money(client, a, 'tithe', 1000, D, category='Sunday')
    money(client, a, 'offering', 250, D)
    money(client, a, 'expense', 400, D)
    gone = money(client, a, 'tithe', 999, D)
    client.delete('/api/finance/%d' % gone, headers=a, json={'reason': 'test'})
    money(client, a, 'tithe', 5000, D - timedelta(days=500))
    res = client.get('/api/reports/giving?from=%s&to=%s' % ((D - timedelta(days=3)).isoformat(), D.isoformat()), headers=a)
    assert res.status_code == 200, res.get_json()
    body = res.get_json()
    assert body['income_total'] == 1250.0 and body['expense_total'] == 400.0 and body['net'] == 850.0
    assert body['count'] == 3
    assert {r['type']: r['total'] for r in body['by_type']} == {'tithe': 1000.0, 'offering': 250.0, 'expense': 400.0}
    assert body['by_month'][0]['income'] == 1250.0


def test_giving_report_checks_dates_and_roles(client):
    a = admin(client)
    assert client.get('/api/reports/giving?from=bad', headers=a).status_code == 400
    assert client.get('/api/reports/giving?from=2026-02-01&to=2026-01-01', headers=a).status_code == 400
    assert client.get('/api/reports/giving?from=2020-01-01&to=2026-01-01', headers=a).status_code == 400
    client.post('/api/users/', headers=a, json={'username': 'view1', 'email': 'view1@example.org',
                                                'password': STAFF, 'role': 'viewer'})
    assert client.get('/api/reports/giving', headers=login(client, 'view1', STAFF)).status_code == 403


def test_member_statement_lists_one_members_gifts_for_a_year(client):
    a = admin(client)
    m = client.post('/api/members/', headers=a, json={'first_name': 'Grace', 'last_name': 'Otieno'}).get_json()
    money(client, a, 'tithe', 300, D, member_id=m['id'])
    money(client, a, 'offering', 200, D, member_id=m['id'])
    money(client, a, 'tithe', 999, D)
    body = client.get('/api/reports/member/%d?year=%d' % (m['id'], D.year), headers=a).get_json()
    assert body['total'] == 500.0 and len(body['items']) == 2
    assert body['member']['full_name'] == 'Grace Otieno'
    assert client.get('/api/reports/member/%d?year=1990' % m['id'], headers=a).status_code == 400


def test_reports_stay_inside_one_church(client):
    a = admin(client)
    m = client.post('/api/members/', headers=a, json={'first_name': 'Grace', 'last_name': 'Otieno'}).get_json()
    money(client, a, 'tithe', 300, D)
    client.post('/api/churches/', headers=a, json={'name': 'Second Church', 'admin_username': 'badmin',
                'admin_email': 'b@example.org', 'admin_password': B_PASS})
    b = login(client, 'badmin', B_PASS)
    assert client.get('/api/reports/giving', headers=b).get_json()['income_total'] == 0
    assert client.get('/api/reports/member/%d' % m['id'], headers=b).status_code == 404


def test_backup_workflow_encrypts_before_upload():
    text = open(os.path.join(REPO, '.github', 'workflows', 'backup.yml'), encoding='utf8').read()
    assert 'pg_dump' in text and '--symmetric' in text and 'AES256' in text
    assert 'secrets.BACKUP_DATABASE_URL' in text and 'secrets.BACKUP_PASSPHRASE' in text
    assert 'retention-days: 14' in text and 'schedule' in text
    upload = text.index('upload-artifact')
    assert text.index('--symmetric') < upload and 'rm -f db.dump' in text
    assert os.path.exists(os.path.join(REPO, 'docs', 'BACKUPS.md'))
