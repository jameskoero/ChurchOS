"""Fix Pack 19: offline attendance. The server side (roster and safe-to-repeat sync) and the files that make the app open with no signal."""
import os
import struct
from datetime import date, timedelta

from conftest import ADMIN_PASSWORD, BACKEND

REPO = os.path.dirname(BACKEND)
STAFF = 'Staff-Login-13579'
B_PASS = 'Second-Church-2468'
TODAY = date.today()


def login(client, username, password):
    res = client.post('/api/auth/login', json={'username': username, 'password': password})
    assert res.status_code == 200, res.get_json()
    return {'Authorization': 'Bearer ' + res.get_json()['access_token']}


def admin(client):
    return login(client, 'admin', ADMIN_PASSWORD)


def member(client, h, first):
    res = client.post('/api/members/', headers=h, json={'first_name': first, 'last_name': 'Test'})
    assert res.status_code == 201, res.get_json()
    return res.get_json()['id']


def mark(cid, member_id, day=None, service='Sunday Morning'):
    return {'client_id': cid, 'member_id': member_id, 'service_type': service,
            'service_date': (day or TODAY).isoformat()}


def text(*parts):
    with open(os.path.join(REPO, *parts), encoding='utf8') as f:
        return f.read()


def test_roster_lists_active_members_and_who_is_already_recorded(client):
    a = admin(client)
    one, two = member(client, a, 'Alpha'), member(client, a, 'Beta')
    gone = member(client, a, 'Gone')
    client.post('/api/members/%d/erase' % gone, headers=a)
    client.post('/api/attendance/', headers=a, json={'member_id': one, 'service_type': 'Sunday Morning',
                                                     'service_date': TODAY.isoformat()})
    body = client.get('/api/checkin/roster?service_date=%s&service_type=Sunday Morning' % TODAY.isoformat(),
                      headers=a).get_json()
    assert sorted(m['id'] for m in body['members']) == sorted([one, two])
    assert set(body['members'][0]) == {'id', 'member_id', 'full_name'}
    assert body['already'] == [one] and body['truncated'] is False
    other = client.get('/api/checkin/roster?service_date=%s&service_type=Friday Prayer' % TODAY.isoformat(),
                       headers=a).get_json()
    assert other['already'] == []


def test_roster_and_sync_are_for_pastoral_staff_and_one_church(client):
    a = admin(client)
    m = member(client, a, 'Alpha')
    client.post('/api/users/', headers=a, json={'username': 'view1', 'email': 'v@example.org',
                                                'password': STAFF, 'role': 'viewer'})
    viewer = login(client, 'view1', STAFF)
    assert client.get('/api/checkin/roster', headers=viewer).status_code == 403
    assert client.post('/api/checkin/sync', headers=viewer, json={'records': [mark('c1', m)]}).status_code == 403
    client.post('/api/churches/', headers=a, json={'name': 'Second Church', 'admin_username': 'badmin',
                'admin_email': 'b@example.org', 'admin_password': B_PASS})
    b = login(client, 'badmin', B_PASS)
    assert client.get('/api/checkin/roster', headers=b).get_json()['members'] == []
    res = client.post('/api/checkin/sync', headers=b, json={'records': [mark('c1', m)]})
    assert res.get_json()['created'] == 0 and res.get_json()['rejected'] == [{'client_id': 'c1', 'reason': 'member not found'}]


def test_sync_saves_marks_once_even_if_repeated(client):
    a = admin(client)
    one, two = member(client, a, 'Alpha'), member(client, a, 'Beta')
    batch = [mark('c1', one), mark('c2', two), mark('c3', one)]
    first = client.post('/api/checkin/sync', headers=a, json={'records': batch})
    assert first.status_code == 200, first.get_json()
    body = first.get_json()
    assert body['created'] == 2 and body['duplicates'] == 1 and body['done'] == ['c1', 'c2', 'c3'] and body['rejected'] == []
    again = client.post('/api/checkin/sync', headers=a, json={'records': batch}).get_json()
    assert again['created'] == 0 and again['duplicates'] == 3
    listed = client.get('/api/attendance/?per_page=50', headers=a).get_json()['records']
    assert len(listed) == 2


def test_sync_rejects_bad_marks_but_keeps_the_good_ones(client):
    a = admin(client)
    m = member(client, a, 'Alpha')
    batch = [mark('ok', m),
             mark('late', m, TODAY + timedelta(days=5)),
             mark('odd', m, service='Midnight Party'),
             {'client_id': 'bad-date', 'member_id': m, 'service_type': 'Sunday Morning', 'service_date': 'not-a-date'},
             mark('ghost', 999999),
             {'member_id': m}]
    body = client.post('/api/checkin/sync', headers=a, json={'records': batch}).get_json()
    assert body['created'] == 1 and body['done'] == ['ok']
    reasons = {r['client_id']: r['reason'] for r in body['rejected']}
    assert reasons == {'late': 'invalid date', 'odd': 'unknown service', 'bad-date': 'invalid date',
                       'ghost': 'member not found', '': 'missing id'}
    assert client.post('/api/checkin/sync', headers=a, json={'records': []}).status_code == 400
    assert client.post('/api/checkin/sync', headers=a, json={'records': [mark('x%d' % i, m) for i in range(501)]}).status_code == 400


def test_offline_files_are_in_place():
    worker = text('frontend', 'public', 'sw.js')
    assert "addEventListener('fetch'" in worker and "startsWith('/api/')" in worker
    assert "request.method !== 'GET'" in worker and 'self.location.origin' in worker
    index = text('frontend', 'src', 'index.js')
    assert "serviceWorker.register('/sw.js')" in index and 'unregister()' not in index
    assert "path='checkin'" in text('frontend', 'src', 'App.js')
    assert "path: '/checkin'" in text('frontend', 'src', 'components', 'Layout.js')
    assert 'clearRoster' in text('frontend', 'src', 'contexts', 'AuthContext.js')


def test_app_icons_exist_so_the_app_can_be_installed():
    for name, size in (('logo192.png', 192), ('logo512.png', 512)):
        with open(os.path.join(REPO, 'frontend', 'public', name), 'rb') as f:
            head = f.read(24)
        assert head[:8] == b'\x89PNG\r\n\x1a\n', name
        assert struct.unpack('>II', head[16:24]) == (size, size), name
    assert os.path.getsize(os.path.join(REPO, 'frontend', 'public', 'favicon.ico')) > 100
