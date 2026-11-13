"""Fix Pack 22: denominations (with Other), regions led by a bishop, invitations, totals and member lists."""
import json
from datetime import date

from conftest import ADMIN_PASSWORD

PASS = 'Second-Church-2468'
STAFF = 'Staff-Login-13579'


def login(client, username, password):
    res = client.post('/api/auth/login', json={'username': username, 'password': password})
    assert res.status_code == 200, res.get_json()
    return {'Authorization': 'Bearer ' + res.get_json()['access_token']}


def bishop(client):
    return login(client, 'admin', ADMIN_PASSWORD)


def church(client, owner, name, username):
    res = client.post('/api/churches/', headers=owner, json={'name': name, 'admin_username': username,
                      'admin_email': username + '@example.org', 'admin_password': PASS})
    assert res.status_code == 201, res.get_json()
    return res.get_json()['church']['id'], login(client, username, PASS)


def find(client, h, text):
    return client.get('/api/governance/denominations', headers=h, query_string={'search': text}).get_json()['denominations']


def use(client, h, text):
    d = find(client, h, text)[0]
    assert client.put('/api/governance/church', headers=h, json={'denomination_id': d['id']}).status_code == 200
    return d


def region_with_altar(client):
    b = bishop(client)
    use(client, b, 'Repentance')
    assert client.post('/api/governance/regions', headers=b, json={'name': 'Migosi Region'}).status_code == 201
    altar_id, altar = church(client, b, 'Kanyakwar Altar', 'altar1')
    code = 'COS-%04d' % altar_id
    inv = client.post('/api/governance/regions/mine/invites', headers=b, json={'code': code})
    assert inv.status_code == 201, inv.get_json()
    pending = client.get('/api/governance/church', headers=altar).get_json()['invites']
    assert client.post('/api/governance/invites/%d/accept' % pending[0]['id'], headers=altar).status_code == 200
    return b, altar_id, altar


def test_starting_list_and_search_by_name_or_short_name(client):
    h = bishop(client)
    names = [d['name'] for d in find(client, h, '')]
    for expected in ('Ministry of Repentance and Holiness', 'Power of Jesus Around the World Church',
                     'Voice of Salvation and Healing Church', 'Pentecostal Assemblies of God'):
        assert expected in names
    assert find(client, h, 'VOSH')[0]['name'] == 'Voice of Salvation and Healing Church'
    assert find(client, h, 'power jesus')[0]['name'] == 'Power of Jesus Around the World Church'
    mrh = find(client, h, 'Repentance')[0]
    assert (mrh['unit_label'], mrh['region_leader_title'], mrh['unit_leader_title'], mrh['seat_label']) == \
        ('Altar', 'Bishop', 'Senior Pastor', 'Main Altar')
    assert find(client, h, 'PAG')[0]['unit_label'] == 'Church'          # other structures are not assumed


def test_other_denomination_is_usable_at_once_and_waits_for_owner_approval(client):
    owner = bishop(client)
    _, b = church(client, owner, 'Second Church', 'badmin')
    _, c = church(client, owner, 'Third Church', 'cadmin')
    assert client.post('/api/governance/denominations/request', headers=b, json={'name': 'ab'}).status_code == 400
    made = client.post('/api/governance/denominations/request', headers=b, json={'name': 'Glory  Fire   Ministries'})
    assert made.status_code == 201 and made.get_json()['denomination']['status'] == 'pending'
    assert client.get('/api/governance/church', headers=b).get_json()['denomination']['name'] == 'Glory Fire Ministries'
    assert find(client, c, 'Glory') == []                                # not public until approved
    assert client.get('/api/governance/denominations/pending', headers=b).status_code == 403
    pending = client.get('/api/governance/denominations/pending', headers=owner).get_json()['denominations']
    assert [d['name'] for d in pending] == ['Glory Fire Ministries']
    assert client.put('/api/governance/denominations/%d' % pending[0]['id'], headers=b, json={'status': 'listed'}).status_code == 403
    assert client.put('/api/governance/denominations/%d' % pending[0]['id'], headers=owner,
                      json={'status': 'listed', 'unit_label': 'Assembly'}).status_code == 200
    assert find(client, c, 'Glory')[0]['unit_label'] == 'Assembly'


def test_bishop_creates_region_and_an_altar_joins_only_by_accepting(client):
    b = bishop(client)
    assert client.post('/api/governance/regions', headers=b, json={'name': 'Migosi Region'}).status_code == 400
    use(client, b, 'Repentance')
    made = client.post('/api/governance/regions', headers=b, json={'name': 'Migosi Region'})
    assert made.status_code == 201
    info = client.get('/api/governance/church', headers=b).get_json()
    assert info['is_seat'] and info['leads_region'] and info['region']['name'] == 'Migosi Region'
    altar_id, altar = church(client, b, 'Kanyakwar Altar', 'altar1')
    assert client.post('/api/governance/regions/mine/invites', headers=b, json={'code': 'COS-9999'}).status_code == 404
    client.post('/api/governance/regions/mine/invites', headers=b, json={'code': 'COS-%04d' % altar_id})
    assert client.get('/api/governance/regions/mine/churches/%d/members' % altar_id, headers=b).status_code == 404
    pending = client.get('/api/governance/church', headers=altar).get_json()['invites']
    assert len(pending) == 1 and pending[0]['region']['name'] == 'Migosi Region'
    assert client.post('/api/governance/invites/%d/accept' % pending[0]['id'], headers=altar).status_code == 200
    joined = client.get('/api/governance/church', headers=altar).get_json()
    assert joined['region']['name'] == 'Migosi Region'
    assert joined['denomination']['name'] == 'Ministry of Repentance and Holiness'
    assert joined['labels']['unit_leader_title'] == 'Senior Pastor'


def test_bishop_sees_totals_and_member_lists_and_each_look_is_logged_at_the_altar(client):
    b, altar_id, altar = region_with_altar(client)
    client.post('/api/members/', headers=b, json={'first_name': 'Mercy', 'last_name': 'Chepkemoi', 'phone': '0711000111'})
    client.post('/api/members/', headers=altar, json={'first_name': 'Peter', 'last_name': 'Otieno', 'phone': '0722000222'})
    client.post('/api/members/', headers=altar, json={'first_name': 'Ann', 'last_name': 'Akinyi'})
    gift = client.post('/api/finance/', headers=altar, json={'transaction_type': 'tithe', 'amount': 500,
                                                         'transaction_date': date.today().isoformat()})
    assert gift.status_code == 201, gift.get_json()
    overview = client.get('/api/governance/regions/mine', headers=b).get_json()
    by_name = {c['name']: c for c in overview['churches']}
    assert by_name['Kanyakwar Altar']['members'] == 2 and by_name['Kanyakwar Altar']['giving_30d'] == 500.0
    assert overview['totals']['members'] == 3
    members = client.get('/api/governance/regions/mine/churches/%d/members' % altar_id, headers=b).get_json()
    assert members['total'] == 2 and {m['full_name'] for m in members['members']} == {'Peter Otieno', 'Ann Akinyi'}
    assert any(m['phone'] == '0722000222' for m in members['members'])
    found = client.get('/api/governance/regions/mine/churches/%d/members' % altar_id, headers=b,
                       query_string={'search': 'Peter Otieno'}).get_json()
    assert found['total'] == 1
    log = client.get('/api/finance/audit', headers=altar).get_json()['entries']
    assert any(e['action'] == 'governance.view_members' for e in log)


def test_altar_admins_and_others_cannot_use_the_bishop_view(client):
    b, altar_id, altar = region_with_altar(client)
    assert client.get('/api/governance/regions/mine', headers=altar).status_code == 403
    me = client.get('/api/governance/church', headers=b).get_json()
    seat_id = me['region']['seat_church_id']
    assert client.get('/api/governance/regions/mine/churches/%d/members' % seat_id, headers=altar).status_code == 404
    _, outsider = church(client, b, 'Outside Church', 'oadmin')
    assert client.get('/api/governance/regions/mine', headers=outsider).status_code == 403
    client.post('/api/users/', headers=b, json={'username': 'sec1', 'email': 's@example.org', 'password': STAFF, 'role': 'secretary'})
    sec = login(client, 'sec1', STAFF)
    assert client.get('/api/governance/regions/mine', headers=sec).status_code == 403


def test_an_altar_can_leave_and_the_seat_cannot(client):
    b, altar_id, altar = region_with_altar(client)
    assert client.post('/api/governance/church/leave', headers=b).status_code == 409
    assert client.post('/api/governance/church/leave', headers=altar).status_code == 200
    assert client.get('/api/governance/regions/mine/churches/%d/members' % altar_id, headers=b).status_code == 404
    names = [c['name'] for c in client.get('/api/governance/regions/mine', headers=b).get_json()['churches']]
    assert 'Kanyakwar Altar' not in names


def test_other_denominations_cannot_be_invited_or_switch_while_in_a_region(client):
    b = bishop(client)
    use(client, b, 'Repentance')
    client.post('/api/governance/regions', headers=b, json={'name': 'Migosi Region'})
    other_id, other = church(client, b, 'PAG Church', 'padmin')
    use(client, other, 'PAG')
    res = client.post('/api/governance/regions/mine/invites', headers=b, json={'code': 'COS-%04d' % other_id})
    assert res.status_code == 409 and res.get_json()['code'] == 'OTHER_DENOMINATION'
    pag = find(client, b, 'PAG')[0]
    assert client.put('/api/governance/church', headers=b, json={'denomination_id': pag['id']}).status_code == 409
