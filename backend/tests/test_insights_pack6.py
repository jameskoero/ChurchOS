"""Fix Pack 6: explainable insights (care list, giving flags, forecast, summary, attention)."""
from datetime import date, timedelta

from conftest import ADMIN_PASSWORD

STAFF = 'Staff-Login-13579'
B_PASS = 'Second-Church-2468'
TODAY = date.today()


def login(client, username, password):
    res = client.post('/api/auth/login', json={'username': username, 'password': password})
    assert res.status_code == 200, res.get_json()
    return {'Authorization': 'Bearer ' + res.get_json()['access_token']}


def admin(client):
    return login(client, 'admin', ADMIN_PASSWORD)


def staff(client, h, username, role):
    res = client.post('/api/users/', headers=h, json={
        'username': username, 'email': username + '@example.org',
        'password': STAFF, 'role': role})
    assert res.status_code == 201, res.get_json()
    return login(client, username, STAFF)


def member(client, h, first, **extra):
    body = {'first_name': first, 'last_name': 'Test'}
    body.update(extra)
    res = client.post('/api/members/', headers=h, json=body)
    assert res.status_code == 201, res.get_json()
    return res.get_json()['id']


def came(client, h, member_id, days_ago):
    res = client.post('/api/attendance/', headers=h, json={
        'member_id': member_id, 'service_type': 'Sunday Morning',
        'service_date': (TODAY - timedelta(days=days_ago)).isoformat()})
    assert res.status_code == 201, res.get_json()


def give(client, h, amount, days_ago=0, member_id=None, kind='tithe'):
    body = {'transaction_type': kind, 'amount': amount,
            'transaction_date': (TODAY - timedelta(days=days_ago)).isoformat()}
    if member_id:
        body['member_id'] = member_id
    res = client.post('/api/finance/', headers=h, json=body)
    assert res.status_code == 201, res.get_json()
    return res.get_json()['id']


def test_care_list_names_regulars_who_went_quiet(client):
    a = admin(client)
    quiet = member(client, a, 'Quiet')
    steady = member(client, a, 'Steady')
    newcomer = member(client, a, 'Newcomer')
    for days in (35, 42, 49, 56):
        came(client, a, quiet, days)
    for days in (7, 35, 42, 49):
        came(client, a, steady, days)
    came(client, a, newcomer, 40)
    res = client.get('/api/insights/care', headers=a)
    assert res.status_code == 200
    body = res.get_json()
    assert [m['full_name'] for m in body['members']] == ['Quiet Test']
    row = body['members'][0]
    assert row['attended_before'] == 4 and row['weeks_absent'] >= 4
    assert 'not at all' in row['reason']
    assert 'person decides' in body['method']


def test_care_list_ignores_erased_and_other_churches(client):
    a = admin(client)
    gone = member(client, a, 'Gone')
    for days in (35, 42, 49):
        came(client, a, gone, days)
    assert client.get('/api/insights/care', headers=a).get_json()['total'] == 1
    client.post('/api/members/%d/erase' % gone, headers=a)
    assert client.get('/api/insights/care', headers=a).get_json()['total'] == 0
    other = member(client, a, 'Other')
    for days in (35, 42, 49):
        came(client, a, other, days)
    client.post('/api/churches/', headers=a, json={'name': 'Second Church', 'admin_username': 'badmin',
                'admin_email': 'b@example.org', 'admin_password': B_PASS})
    b = login(client, 'badmin', B_PASS)
    assert client.get('/api/insights/care', headers=b).get_json()['total'] == 0


def test_care_list_is_for_pastoral_roles_only(client):
    a = admin(client)
    assert client.get('/api/insights/care', headers=staff(client, a, 'view1', 'viewer')).status_code == 403
    assert client.get('/api/insights/care', headers=staff(client, a, 'treas1', 'treasurer')).status_code == 403
    assert client.get('/api/insights/care', headers=staff(client, a, 'past1', 'pastor')).status_code == 200


def test_giving_flags_duplicates_and_oversized_gifts(client):
    a = admin(client)
    m = member(client, a, 'Giver')
    one = give(client, a, 500, days_ago=2, member_id=m)
    two = give(client, a, 500, days_ago=2, member_id=m)
    for index in range(12):
        give(client, a, 100 + index, days_ago=60 + index)
    big = give(client, a, 5000, days_ago=3)
    body = client.get('/api/insights/giving', headers=a).get_json()
    dupes = [f for f in body['flags'] if f['kind'] == 'possible_duplicate']
    assert len(dupes) == 1 and sorted(dupes[0]['finance_ids']) == sorted([one, two])
    large = [f for f in body['flags'] if f['kind'] == 'unusually_large']
    assert big in [i for f in large for i in f['finance_ids']]
    assert all('usual' in f['reason'] for f in large)


def test_giving_flags_stay_quiet_without_enough_history(client):
    a = admin(client)
    for amount in (100, 200, 9000):
        give(client, a, amount, days_ago=3)
    assert client.get('/api/insights/giving', headers=a).get_json()['flags'] == []


def test_forecast_needs_three_full_months(client):
    a = admin(client)
    give(client, a, 1000, days_ago=40)
    body = client.get('/api/insights/forecast', headers=a).get_json()
    assert body['available'] is False and 'at least 3' in body['reason']


def test_forecast_averages_the_last_three_full_months(client):
    a = admin(client)
    first = TODAY.replace(day=1)
    amounts = {}
    cursor = first
    for index, value in enumerate((3000, 2000, 1000), start=1):
        cursor = (cursor - timedelta(days=1)).replace(day=15)
        give(client, a, value, days_ago=(TODAY - cursor).days)
        cursor = cursor.replace(day=1)
    body = client.get('/api/insights/forecast', headers=a).get_json()
    assert body['available'] is True
    assert body['expected'] == 2000.0 and body['low'] == 1000.0 and body['high'] == 3000.0


def test_summary_uses_only_ledger_numbers(client):
    a = admin(client)
    assert 'Giving' not in ' '.join(client.get('/api/insights/summary', headers=a).get_json()['lines'])
    member(client, a, 'One')
    give(client, a, 1200, days_ago=0)
    lines = client.get('/api/insights/summary', headers=a).get_json()['lines']
    assert any(line.startswith('Giving so far this month: KES 1,200') for line in lines)
    assert 'Active members: 1.' in lines
    viewer = staff(client, a, 'view1', 'viewer')
    assert client.get('/api/insights/summary', headers=viewer).status_code == 403


def test_dashboard_attention_lists_what_needs_doing(client):
    a = admin(client)
    m = member(client, a, 'Quiet')
    for days in (35, 42, 49):
        came(client, a, m, days)
    give(client, a, 700)
    items = {i['key']: i for i in client.get('/api/dashboard/stats', headers=a).get_json()['attention']}
    assert items['verify']['count'] == 1 and items['verify']['to'] == '/finance'
    assert items['care']['count'] == 1
    assert items['consent']['count'] == 1
    treasurer = staff(client, a, 'treas1', 'treasurer')
    keys = {i['key'] for i in client.get('/api/dashboard/stats', headers=treasurer).get_json()['attention']}
    assert 'verify' in keys and 'care' not in keys and 'consent' not in keys
    viewer = staff(client, a, 'view1', 'viewer')
    assert client.get('/api/dashboard/stats', headers=viewer).get_json()['attention'] == []
