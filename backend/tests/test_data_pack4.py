"""Fix Pack 4: member privacy (consent, redaction, export, erase) and deploy hygiene."""
import json
import os
from datetime import date

from conftest import ADMIN_PASSWORD, BACKEND

REPO = os.path.dirname(BACKEND)
STAFF = 'Staff-Login-13579'
B_PASS = 'Second-Church-2468'
TODAY = date.today().isoformat()
PRIVATE = ('date_of_birth', 'address', 'marital_status', 'next_of_kin',
           'next_of_kin_phone', 'baptism_date', 'notes')


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


def new_member(client, h, **extra):
    body = {'first_name': 'Grace', 'last_name': 'Otieno', 'phone': '0711000111',
            'address': 'Kondele, Kisumu', 'marital_status': 'married',
            'next_of_kin': 'Brian Otieno', 'next_of_kin_phone': '0722000222',
            'notes': 'Visited by pastor', 'date_of_birth': '1990-05-01'}
    body.update(extra)
    res = client.post('/api/members/', headers=h, json=body)
    assert res.status_code == 201, res.get_json()
    return res.get_json()


def test_consent_is_recorded_and_can_be_withdrawn(client):
    a = admin(client)
    plain = new_member(client, a)
    assert plain['consent_at'] is None
    agreed = new_member(client, a, first_name='Ruth', consent=True)
    assert agreed['consent_at'] and agreed['consent_version'] == 'v1'
    res = client.put(f"/api/members/{plain['id']}", headers=a, json={'consent': True})
    assert res.get_json()['consent_at'] is not None
    res = client.put(f"/api/members/{agreed['id']}", headers=a, json={'consent': False})
    assert res.get_json()['consent_at'] is None


def test_sensitive_fields_are_hidden_from_other_roles(client):
    a = admin(client)
    member = new_member(client, a)
    viewer = staff(client, a, 'view1', 'viewer')
    treasurer = staff(client, a, 'treas1', 'treasurer')
    pastor = staff(client, a, 'past1', 'pastor')
    for h in (viewer, treasurer):
        row = client.get('/api/members/', headers=h).get_json()['members'][0]
        one = client.get(f"/api/members/{member['id']}", headers=h).get_json()
        for field in PRIVATE:
            assert field not in row and field not in one, field
        assert row['first_name'] == 'Grace' and row['phone'] == '0711000111'
    for h in (a, pastor):
        one = client.get(f"/api/members/{member['id']}", headers=h).get_json()
        assert one['next_of_kin'] == 'Brian Otieno' and one['notes'] == 'Visited by pastor'


def test_export_gives_one_members_data_to_pastoral_staff_only(client):
    a = admin(client)
    member = new_member(client, a)
    client.post('/api/attendance/', headers=a, json={
        'member_id': member['id'], 'service_type': 'Sunday Morning', 'service_date': TODAY})
    client.post('/api/finance/', headers=a, json={
        'transaction_type': 'tithe', 'amount': 500, 'transaction_date': TODAY,
        'member_id': member['id']})
    viewer = staff(client, a, 'view1', 'viewer')
    assert client.get(f"/api/members/{member['id']}/export", headers=viewer).status_code == 403
    res = client.get(f"/api/members/{member['id']}/export", headers=a)
    assert res.status_code == 200
    body = res.get_json()
    assert body['member']['next_of_kin'] == 'Brian Otieno'
    assert len(body['attendance']) == 1 and body['giving'][0]['amount'] == 500.0
    pastor = staff(client, a, 'past1', 'pastor')
    assert client.get(f"/api/members/{member['id']}/export", headers=pastor).get_json()['giving']


def test_erase_removes_personal_details_but_keeps_the_ledger(client):
    a = admin(client)
    member = new_member(client, a, consent=True)
    mid = member['id']
    client.post('/api/finance/', headers=a, json={
        'transaction_type': 'tithe', 'amount': 500, 'transaction_date': TODAY, 'member_id': mid})
    pastor = staff(client, a, 'past1', 'pastor')
    assert client.post(f'/api/members/{mid}/erase', headers=pastor).status_code == 403
    res = client.post(f'/api/members/{mid}/erase', headers=a)
    assert res.status_code == 200
    erased = res.get_json()['member']
    assert erased['full_name'] == 'Erased Member' and erased['erased'] is True
    assert erased['phone'] is None and erased['next_of_kin'] is None and erased['notes'] is None
    assert erased['consent_at'] is None and erased['membership_status'] == 'erased'
    tx = client.get('/api/finance/', headers=a).get_json()['transactions']
    assert len(tx) == 1 and tx[0]['amount'] == 500.0
    assert client.put(f'/api/members/{mid}', headers=a, json={'first_name': 'Back'}).status_code == 410
    assert client.get(f'/api/members/{mid}/export', headers=a).status_code == 410
    assert client.post(f'/api/members/{mid}/erase', headers=a).status_code == 409
    audit = client.get('/api/finance/audit', headers=a).get_json()['entries']
    assert 'member.erase' in [e['action'] for e in audit]
    assert 'Grace' not in json.dumps(audit) and 'Otieno' not in json.dumps(audit)


def test_privacy_actions_stay_inside_one_church(client):
    a = admin(client)
    member = new_member(client, a)
    client.post('/api/churches/', headers=a, json={
        'name': 'Second Church', 'admin_username': 'badmin',
        'admin_email': 'b@example.org', 'admin_password': B_PASS})
    b = login(client, 'badmin', B_PASS)
    assert client.get(f"/api/members/{member['id']}/export", headers=b).status_code == 404
    assert client.post(f"/api/members/{member['id']}/erase", headers=b).status_code == 404


def test_a_member_with_records_cannot_be_hard_deleted(client):
    a = admin(client)
    kept = new_member(client, a)
    client.post('/api/finance/', headers=a, json={
        'transaction_type': 'tithe', 'amount': 50, 'transaction_date': TODAY,
        'member_id': kept['id']})
    blocked = client.delete(f"/api/members/{kept['id']}", headers=a)
    assert blocked.status_code == 409 and blocked.get_json()['code'] == 'HAS_RECORDS'
    lone = new_member(client, a, first_name='Solo')
    assert client.delete(f"/api/members/{lone['id']}", headers=a).status_code == 200


def test_deploy_files_are_clean():
    for stale in ('Procfile', 'nixpacks.toml', 'railway.toml', 'runtime.txt'):
        assert not os.path.exists(os.path.join(BACKEND, stale)), stale
    docker = open(os.path.join(BACKEND, 'Dockerfile'), encoding='utf8').read()
    assert 'USER appuser' in docker and 'HEALTHCHECK' in docker
    render = open(os.path.join(REPO, 'render.yaml'), encoding='utf8').read()
    assert 'healthCheckPath: /api/health' in render
    assert 'ADMIN_BOOTSTRAP_PASSWORD' in render
    security = open(os.path.join(REPO, 'SECURITY.md'), encoding='utf8').read()
    assert '2.x' in security and 'Report a vulnerability' in security
    ignore = open(os.path.join(REPO, '.gitignore'), encoding='utf8').read().split('\n')
    assert 'package-lock.json' not in [line.strip() for line in ignore]
