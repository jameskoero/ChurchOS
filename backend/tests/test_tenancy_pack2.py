"""Fix Pack 2: one church can never see or change another church's data."""
import glob
import os
import re
from datetime import date, datetime, timedelta

from conftest import ADMIN_PASSWORD, BACKEND

TODAY = date.today().isoformat()
NEXT_WEEK = (datetime.utcnow() + timedelta(days=7)).replace(microsecond=0).isoformat()
B_PASSWORD = 'Second-Church-2468'
STAFF_PASSWORD = 'Staff-Login-13579'


def headers_for(client, username, password):
    res = client.post('/api/auth/login', json={'username': username, 'password': password})
    assert res.status_code == 200, res.get_json()
    return {'Authorization': 'Bearer ' + res.get_json()['access_token']}


def owner(client):
    return headers_for(client, 'admin', ADMIN_PASSWORD)


def second_church(client, a):
    res = client.post('/api/churches/', headers=a, json={
        'name': 'Second Church', 'admin_username': 'badmin',
        'admin_email': 'b@example.org', 'admin_password': B_PASSWORD})
    assert res.status_code == 201, res.get_json()
    return res.get_json()['church']['id'], headers_for(client, 'badmin', B_PASSWORD)


def add_user(client, h, username, role):
    res = client.post('/api/users/', headers=h, json={
        'username': username, 'email': username + '@example.org',
        'password': STAFF_PASSWORD, 'role': role})
    assert res.status_code == 201, res.get_json()
    return res.get_json()['id']


def add_member(client, h, first):
    res = client.post('/api/members/', headers=h, json={'first_name': first, 'last_name': 'Test'})
    assert res.status_code == 201, res.get_json()
    return res.get_json()['id']


def add_money(client, h, amount, **extra):
    body = {'transaction_type': 'tithe', 'amount': amount, 'transaction_date': TODAY}
    body.update(extra)
    return client.post('/api/finance/', headers=h, json=body)


def test_first_admin_becomes_owner_and_old_rows_get_a_church(app):
    from app import _tenancy_upgrade
    from models import db, User, Member
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        assert admin.is_platform_owner is True
        old = Member(member_id=Member.generate_member_id(), first_name='Old', last_name='Row')
        db.session.add(old)
        db.session.commit()
        assert old.church_id is None
        _tenancy_upgrade()
        assert db.session.get(Member, old.id).church_id == admin.church_id


def test_members_are_separate(client):
    a = owner(client)
    _, b = second_church(client, a)
    mine = add_member(client, a, 'Alpha')
    theirs = add_member(client, b, 'Beta')
    a_list = client.get('/api/members/', headers=a).get_json()['members']
    b_list = client.get('/api/members/', headers=b).get_json()['members']
    assert [m['id'] for m in a_list] == [mine]
    assert [m['id'] for m in b_list] == [theirs]
    assert client.get(f'/api/members/{mine}', headers=b).status_code == 404
    assert client.put(f'/api/members/{mine}', headers=b, json={'first_name': 'X'}).status_code == 404
    assert client.delete(f'/api/members/{mine}', headers=b).status_code == 404
    assert client.get(f'/api/members/{mine}', headers=a).get_json()['first_name'] == 'Alpha'
    assert client.get('/api/members/stats/summary', headers=b).get_json()['total'] == 1


def test_money_is_separate(client):
    a = owner(client)
    _, b = second_church(client, a)
    mine = add_money(client, a, 1000)
    assert mine.status_code == 201, mine.get_json()
    tx = mine.get_json()['id']
    assert add_money(client, b, 250).status_code == 201
    a_list = client.get('/api/finance/', headers=a).get_json()['transactions']
    b_list = client.get('/api/finance/', headers=b).get_json()['transactions']
    assert [float(t['amount']) for t in a_list] == [1000.0]
    assert [float(t['amount']) for t in b_list] == [250.0]
    assert client.get('/api/finance/summary', headers=a).get_json()['total_income'] == 1000.0
    assert client.get('/api/finance/summary', headers=b).get_json()['total_income'] == 250.0
    assert client.put(f'/api/finance/{tx}', headers=b, json={'amount': 1}).status_code == 404
    assert client.delete(f'/api/finance/{tx}', headers=b).status_code == 404
    a_member = add_member(client, a, 'Alpha')
    assert add_money(client, b, 50, member_id=a_member).status_code == 404


def test_events_and_attendance_are_separate(client):
    a = owner(client)
    _, b = second_church(client, a)
    ev = client.post('/api/events/', headers=a, json={'title': 'A event', 'start_date': NEXT_WEEK})
    assert ev.status_code == 201, ev.get_json()
    event_id = ev.get_json()['id']
    assert client.get('/api/events/', headers=b).get_json()['events'] == []
    assert client.get('/api/events/upcoming', headers=b).get_json() == []
    assert client.get(f'/api/events/{event_id}', headers=b).status_code == 404
    assert client.delete(f'/api/events/{event_id}', headers=b).status_code == 404

    a_member = add_member(client, a, 'Alpha')
    mark = {'member_id': a_member, 'service_type': 'Sunday Morning', 'service_date': TODAY}
    made = client.post('/api/attendance/', headers=a, json=mark)
    assert made.status_code == 201, made.get_json()
    assert client.post('/api/attendance/', headers=b, json=mark).status_code == 404
    assert client.get('/api/attendance/', headers=b).get_json()['records'] == []
    assert len(client.get('/api/attendance/', headers=a).get_json()['records']) == 1
    assert client.delete(f"/api/attendance/{made.get_json()['id']}", headers=b).status_code == 404
    assert client.get('/api/attendance/stats/summary', headers=a).get_json()['total_records'] == 1
    assert client.get('/api/attendance/stats/summary', headers=b).get_json()['total_records'] == 0


def test_dashboard_counts_only_the_callers_church(client):
    a = owner(client)
    _, b = second_church(client, a)
    add_member(client, a, 'Alpha')
    add_member(client, a, 'Gamma')
    add_member(client, b, 'Beta')
    add_money(client, a, 1000)
    add_money(client, b, 250)
    a_stats = client.get('/api/dashboard/stats', headers=a).get_json()
    b_stats = client.get('/api/dashboard/stats', headers=b).get_json()
    assert a_stats['members']['total'] == 2 and b_stats['members']['total'] == 1
    assert a_stats['finance']['monthly_income'] == 1000.0
    assert b_stats['finance']['monthly_income'] == 250.0
    assert b_stats['total_users'] == 1


def test_only_finance_roles_see_money(client):
    a = owner(client)
    add_money(client, a, 1000)
    add_user(client, a, 'viewer1', 'viewer')
    add_user(client, a, 'pastor1', 'pastor')
    viewer = headers_for(client, 'viewer1', STAFF_PASSWORD)
    pastor = headers_for(client, 'pastor1', STAFF_PASSWORD)
    assert client.get('/api/finance/', headers=viewer).status_code == 403
    assert client.get('/api/finance/summary', headers=viewer).status_code == 403
    assert client.get('/api/finance/', headers=pastor).status_code == 200
    hidden = client.get('/api/dashboard/stats', headers=viewer).get_json()
    assert hidden['finance']['monthly_income'] == 0 and hidden['finance_trend'] == []
    assert client.get('/api/dashboard/stats', headers=a).get_json()['finance']['monthly_income'] == 1000.0
    member = add_member(client, a, 'Alpha')
    mark = {'member_id': member, 'service_type': 'Sunday Morning', 'service_date': TODAY}
    assert client.post('/api/attendance/', headers=viewer, json=mark).status_code == 403


def test_users_are_separate_and_protected(client):
    a = owner(client)
    _, b = second_church(client, a)
    b_users = client.get('/api/users/', headers=b).get_json()
    assert [u['username'] for u in b_users] == ['badmin']
    a_admin_id = client.get('/api/auth/me', headers=a).get_json()['id']
    assert client.get(f'/api/users/{a_admin_id}', headers=b).status_code == 404
    assert client.put(f'/api/users/{a_admin_id}', headers=b, json={'role': 'viewer'}).status_code == 404
    assert client.delete(f'/api/users/{a_admin_id}', headers=b).status_code == 404

    # A second admin in the owner's church cannot change the platform owner.
    add_user(client, a, 'admin2', 'admin')
    admin2 = headers_for(client, 'admin2', STAFF_PASSWORD)
    assert client.put(f'/api/users/{a_admin_id}', headers=admin2, json={'is_active': False}).status_code == 403
    assert client.delete(f'/api/users/{a_admin_id}', headers=admin2).status_code == 403

    # Nobody can change their own role, and a role change ends old sessions.
    b_admin_id = b_users[0]['id']
    assert client.put(f'/api/users/{b_admin_id}', headers=b, json={'role': 'viewer'}).status_code == 400
    staff_id = add_user(client, b, 'staff1', 'viewer')
    staff = headers_for(client, 'staff1', STAFF_PASSWORD)
    assert client.get('/api/auth/me', headers=staff).status_code == 200
    assert client.put(f'/api/users/{staff_id}', headers=b, json={'role': 'secretary'}).status_code == 200
    assert client.get('/api/auth/me', headers=staff).status_code == 401
    weak = client.post('/api/users/', headers=b, json={
        'username': 'weak1', 'email': 'weak1@example.org', 'password': 'short', 'role': 'viewer'})
    assert weak.status_code == 400


def test_churches_are_owner_business(client):
    a = owner(client)
    b_id, b = second_church(client, a)
    a_id = client.get('/api/auth/me', headers=a).get_json()['church_id']

    assert client.get('/api/churches/', headers=b).get_json()['total'] == 1
    assert client.get(f'/api/churches/{a_id}', headers=b).status_code == 404
    assert client.put(f'/api/churches/{a_id}', headers=b, json={'name': 'Taken'}).status_code == 404
    assert client.post('/api/churches/', headers=b, json={'name': 'Mine too'}).status_code == 403
    assert client.delete(f'/api/churches/{a_id}', headers=b).status_code == 403
    own = client.put(f'/api/churches/{b_id}', headers=b,
                     json={'name': 'Renamed', 'subscription_plan': 'cathedral'})
    assert own.status_code == 200
    assert own.get_json()['church']['name'] == 'Renamed'
    assert own.get_json()['church']['subscription_plan'] == 'trial'

    assert client.get('/api/churches/', headers=a).get_json()['total'] == 2
    assert client.delete(f'/api/churches/{b_id}', headers=a).status_code == 409
    empty = client.post('/api/churches/', headers=a, json={'name': 'Empty Church'})
    assert empty.status_code == 201
    assert client.delete(f"/api/churches/{empty.get_json()['church']['id']}", headers=a).status_code == 200


def test_page_size_is_capped(app):
    from tenancy import page_size, MAX_PAGE
    with app.test_request_context('/?per_page=100000'):
        assert page_size(20) == MAX_PAGE
    with app.test_request_context('/'):
        assert page_size(20) == 20


def test_no_route_reads_a_table_without_a_church_filter():
    assert not os.path.exists(os.path.join(BACKEND, 'tenant.py'))
    for path in glob.glob(os.path.join(BACKEND, 'routes', '*.py')):
        name = os.path.basename(path)
        source = open(path, encoding='utf8').read()
        if name in ('members.py', 'finance.py', 'events.py', 'attendance.py', 'dashboard.py'):
            assert 'db.session.query(' not in source, name
            assert not re.search(r'\b(Member|Finance|Event|Attendance)\.query\b', source), name
        if name == 'users.py':
            assert 'User.query.get' not in source and 'User.query.order_by' not in source
