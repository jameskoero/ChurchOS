"""Fix Pack 25: ready to sell. Request form the owner approves, legal pages, uptime check."""
import os

from conftest import ADMIN_PASSWORD, BACKEND

REPO = os.path.dirname(BACKEND)
SRC = os.path.join(REPO, 'frontend', 'src')

GOOD = {'church_name': 'Nyalenda Gospel Church', 'contact_name': 'Pastor Test', 'phone': '0712 345 678',
        'county': 'Kisumu', 'denomination': 'Ministry of Repentance and Holiness',
        'members_estimate': 80, 'agree': True}


def owner(client):
    res = client.post('/api/auth/login', json={'username': 'admin', 'password': ADMIN_PASSWORD})
    assert res.status_code == 200, res.get_json()
    return {'Authorization': 'Bearer ' + res.get_json()['access_token']}


def test_request_needs_no_login_and_creates_nothing_but_a_request(client):
    res = client.post('/api/public/request', json=GOOD)
    assert res.status_code == 201, res.get_json()
    o = owner(client)
    rows = client.get('/api/public/requests', headers=o).get_json()['requests']
    assert len(rows) == 1 and rows[0]['phone'] == '+254712345678' and rows[0]['status'] == 'pending'
    names = [c['name'] for c in client.get('/api/churches/', headers=o).get_json()['churches']]
    assert 'Nyalenda Gospel Church' not in names


def test_request_is_checked(client):
    for change in ({'church_name': 'ab'}, {'contact_name': ''}, {'phone': '12345'},
                   {'email': 'not-an-email'}, {'county': 'Atlantis'}, {'agree': False},
                   {'members_estimate': 'many'}):
        res = client.post('/api/public/request', json=dict(GOOD, **change))
        assert res.status_code == 400, (change, res.get_json())
    assert client.post('/api/public/request', data='nope').status_code == 400


def test_bot_field_is_ignored_and_double_send_is_one_request(client):
    assert client.post('/api/public/request', json=dict(GOOD, website='http://spam')).status_code == 201
    assert client.post('/api/public/request', json=GOOD).status_code == 201
    assert client.post('/api/public/request', json=GOOD).status_code == 200
    rows = client.get('/api/public/requests', headers=owner(client)).get_json()['requests']
    assert len(rows) == 1


def test_only_the_platform_owner_can_read_or_decide(client):
    client.post('/api/public/request', json=GOOD)
    assert client.get('/api/public/requests').status_code == 401
    o = owner(client)
    # a church admin who is not the owner
    made = client.post('/api/churches/', headers=o, json={
        'name': 'Other Church', 'admin_username': 'other_admin', 'admin_email': 'o@example.org',
        'admin_password': 'Other-Church-2468'})
    assert made.status_code == 201, made.get_json()
    res = client.post('/api/auth/login', json={'username': 'other_admin', 'password': 'Other-Church-2468'})
    h = {'Authorization': 'Bearer ' + res.get_json()['access_token']}
    assert client.get('/api/public/requests', headers=h).status_code == 403
    assert client.put('/api/public/requests/1', headers=h, json={'action': 'approve'}).status_code == 403


def test_approving_makes_a_trial_church_with_its_denomination_and_only_once(client):
    client.post('/api/public/request', json=GOOD)
    o = owner(client)
    rid = client.get('/api/public/requests', headers=o).get_json()['requests'][0]['id']
    res = client.put('/api/public/requests/%d' % rid, headers=o, json={'action': 'approve'})
    assert res.status_code == 200, res.get_json()
    body = res.get_json()
    assert body['church']['name'] == 'Nyalenda Gospel Church' and body['church']['subscription_plan'] == 'trial'
    assert 'Add first admin' in body['next']
    info = client.get('/api/churches/%d' % body['church']['id'], headers=o).get_json()
    assert info['denomination'] == 'Ministry of Repentance and Holiness'
    again = client.put('/api/public/requests/%d' % rid, headers=o, json={'action': 'approve'})
    assert again.status_code == 409
    approved = client.get('/api/public/requests', headers=o, query_string={'status': 'approved'}).get_json()
    assert len(approved['requests']) == 1 and approved['requests'][0]['church_id'] == body['church']['id']


def test_declining_makes_no_church_and_bad_action_is_refused(client):
    client.post('/api/public/request', json=GOOD)
    o = owner(client)
    rid = client.get('/api/public/requests', headers=o).get_json()['requests'][0]['id']
    assert client.put('/api/public/requests/%d' % rid, headers=o, json={'action': 'maybe'}).status_code == 400
    assert client.put('/api/public/requests/%d' % rid, headers=o, json={'action': 'decline'}).status_code == 200
    names = [c['name'] for c in client.get('/api/churches/', headers=o).get_json()['churches']]
    assert 'Nyalenda Gospel Church' not in names
    assert client.put('/api/public/requests/999', headers=o, json={'action': 'decline'}).status_code == 404


def test_pages_links_and_uptime_check_exist():
    app_js = open(os.path.join(SRC, 'App.js'), encoding='utf8').read()
    for path in ("path='/privacy'", "path='/terms'", "path='/request'", "path='requests'"):
        assert path in app_js, path
    login = open(os.path.join(SRC, 'pages', 'Login.js'), encoding='utf8').read()
    assert 'to="/privacy"' in login and 'to="/terms"' in login and 'to="/request"' in login
    pub = open(os.path.join(SRC, 'pages', 'Public.js'), encoding='utf8').read()
    for phrase in ('Data Protection Act, 2019', 'does not receive, hold or move church money',
                   'never ask for your password', 'odpc.go.ke'):
        assert phrase in pub, phrase
    flow = open(os.path.join(REPO, '.github', 'workflows', 'uptime.yml'), encoding='utf8').read()
    assert '/api/health' in flow and 'exit 1' in flow and 'schedule' in flow
