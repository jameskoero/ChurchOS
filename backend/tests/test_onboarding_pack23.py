"""Fix Pack 23: registering an altar with its denomination and first admin, and adding a first admin later."""
import os

from conftest import ADMIN_PASSWORD, BACKEND

REPO = os.path.dirname(BACKEND)
PASS = 'Senior-Pastor-2468'


def login(client, username, password):
    res = client.post('/api/auth/login', json={'username': username, 'password': password})
    assert res.status_code == 200, res.get_json()
    return {'Authorization': 'Bearer ' + res.get_json()['access_token']}


def owner(client):
    return login(client, 'admin', ADMIN_PASSWORD)


def mrh_id(client, h):
    rows = client.get('/api/governance/denominations', headers=h, query_string={'search': 'Repentance'}).get_json()
    return rows['denominations'][0]['id']


def test_register_an_altar_with_its_denomination_and_senior_pastor_login(client):
    o = owner(client)
    res = client.post('/api/churches/', headers=o, json={
        'name': 'Kaego Altar', 'county': 'Kisumu', 'denomination_id': mrh_id(client, o),
        'admin_full_name': 'Senior Pastor Test', 'admin_username': 'kaego_sp',
        'admin_email': 'kaego@example.org', 'admin_password': PASS})
    assert res.status_code == 201, res.get_json()
    sp = login(client, 'kaego_sp', PASS)
    info = client.get('/api/governance/church', headers=sp).get_json()
    assert info['church'] == 'Kaego Altar'
    assert info['denomination']['name'] == 'Ministry of Repentance and Holiness'
    assert info['labels']['unit_label'] == 'Altar'


def test_other_denomination_typed_at_registration_waits_for_approval(client):
    o = owner(client)
    res = client.post('/api/churches/', headers=o, json={'name': 'New Church', 'denomination_other': 'Glory  Fire Ministries'})
    assert res.status_code == 201, res.get_json()
    pending = client.get('/api/governance/denominations/pending', headers=o).get_json()['denominations']
    assert [d['name'] for d in pending] == ['Glory Fire Ministries']


def test_an_unknown_denomination_id_creates_nothing(client):
    o = owner(client)
    before = len(client.get('/api/churches/', headers=o).get_json()['churches'])
    assert client.post('/api/churches/', headers=o, json={'name': 'X Church', 'denomination_id': 99999}).status_code == 400
    assert len(client.get('/api/churches/', headers=o).get_json()['churches']) == before


def test_first_admin_can_be_added_once_and_only_by_the_owner(client):
    o = owner(client)
    cid = client.post('/api/churches/', headers=o, json={'name': 'Kaego Altar'}).get_json()['church']['id']
    weak = client.post('/api/churches/%d/first-admin' % cid, headers=o, json={'username': 'kaego_sp', 'email': 'k@example.org', 'password': 'short1'})
    assert weak.status_code == 400
    ok = client.post('/api/churches/%d/first-admin' % cid, headers=o, json={
        'full_name': 'Senior Pastor Test', 'username': 'kaego_sp', 'email': 'k@example.org', 'password': PASS})
    assert ok.status_code == 201, ok.get_json()
    sp = login(client, 'kaego_sp', PASS)
    assert client.get('/api/governance/church', headers=sp).get_json()['church'] == 'Kaego Altar'
    again = client.post('/api/churches/%d/first-admin' % cid, headers=o, json={
        'username': 'second', 'email': 's@example.org', 'password': PASS})
    assert again.status_code == 409 and again.get_json()['code'] == 'HAS_ADMIN'
    other = client.post('/api/churches/', headers=o, json={'name': 'Other Altar'}).get_json()['church']['id']
    assert client.post('/api/churches/%d/first-admin' % other, headers=sp, json={
        'username': 'x1', 'email': 'x1@example.org', 'password': PASS}).status_code == 403
    dup = client.post('/api/churches/%d/first-admin' % other, headers=o, json={
        'username': 'kaego_sp', 'email': 'new@example.org', 'password': PASS})
    assert dup.status_code == 409


def test_forms_show_the_real_password_rule_and_no_paybill_fields():
    users = open(os.path.join(REPO, 'frontend', 'src', 'pages', 'Users.js'), encoding='utf8').read()
    assert 'minLength={10}' in users and 'At least 10 characters' in users and 'Min. 8' not in users
    churches = open(os.path.join(REPO, 'frontend', 'src', 'pages', 'Churches.js'), encoding='utf8').read()
    assert 'till_number' not in churches and 'Add first admin' in churches and 'denomination_other' in churches
