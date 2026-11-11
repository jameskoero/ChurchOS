"""Fix Pack 3: exact money, second-person checks, void not delete, audit trail."""
from datetime import date

from conftest import ADMIN_PASSWORD

TODAY = date.today().isoformat()
STAFF = 'Staff-Login-13579'
B_PASS = 'Second-Church-2468'


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


def post_tx(client, h, amount, **extra):
    body = {'transaction_type': 'tithe', 'amount': amount, 'transaction_date': TODAY}
    body.update(extra)
    return client.post('/api/finance/', headers=h, json=body)


def listed(client, h, query=''):
    return client.get('/api/finance/' + query, headers=h).get_json()['transactions']


def test_amounts_are_exact_and_validated(client):
    a = admin(client)
    ok = post_tx(client, a, '10.105')
    assert ok.status_code == 201, ok.get_json()
    assert ok.get_json()['amount'] == 10.11
    for bad in (0, -5, 'abc', 'nan', 'inf', None, True, '1e99999', 99999999999):
        res = post_tx(client, a, bad)
        assert res.status_code == 400, (bad, res.get_json())
    assert post_tx(client, a, 100, transaction_type='bribe').status_code == 400
    assert post_tx(client, a, 100, transaction_date='31/12/2026').status_code == 400
    assert client.post('/api/finance/', headers=a, data='not json',
                       content_type='text/plain').status_code == 400
    post_tx(client, a, '0.10')
    post_tx(client, a, '0.20')
    summary = client.get('/api/finance/summary', headers=a).get_json()
    assert summary['total_income'] == 10.41


def test_verified_is_never_trusted_from_the_client(client):
    a = admin(client)
    res = post_tx(client, a, 500, verified=True)
    assert res.status_code == 201
    assert res.get_json()['verified'] is False
    assert res.get_json()['status'] == 'posted'


def test_duplicate_mpesa_reference_is_refused_per_church(client):
    a = admin(client)
    assert post_tx(client, a, 100, mpesa_ref='sk12abc34').status_code == 201
    again = post_tx(client, a, 100, mpesa_ref='SK12ABC34')
    assert again.status_code == 409
    assert again.get_json()['code'] == 'DUPLICATE_MPESA_REF'
    other = post_tx(client, a, 100, mpesa_ref='SK99ZZZ99')
    assert client.put(f"/api/finance/{other.get_json()['id']}", headers=a,
                      json={'mpesa_ref': 'sk12abc34'}).status_code == 409
    # Another church may use the same reference.
    res = client.post('/api/churches/', headers=a, json={
        'name': 'Second Church', 'admin_username': 'badmin',
        'admin_email': 'b@example.org', 'admin_password': B_PASS})
    assert res.status_code == 201
    b = login(client, 'badmin', B_PASS)
    assert post_tx(client, b, 100, mpesa_ref='SK12ABC34').status_code == 201


def test_a_second_person_must_verify(client):
    a = admin(client)
    treasurer = staff(client, a, 'treas1', 'treasurer')
    tx = post_tx(client, a, 1000).get_json()['id']
    own = client.post(f'/api/finance/{tx}/verify', headers=a)
    assert own.status_code == 403 and own.get_json()['code'] == 'NEEDS_SECOND_PERSON'
    via_put = client.put(f'/api/finance/{tx}', headers=a, json={'verified': True})
    assert via_put.status_code == 403
    ok = client.post(f'/api/finance/{tx}/verify', headers=treasurer)
    assert ok.status_code == 200
    body = ok.get_json()
    assert body['verified'] is True and body['verified_by'] != body['recorded_by']


def test_a_one_person_church_can_still_verify(client):
    a = admin(client)
    tx = post_tx(client, a, 1000).get_json()['id']
    assert client.post(f'/api/finance/{tx}/verify', headers=a).status_code == 200


def test_verified_money_is_locked(client):
    a = admin(client)
    treasurer = staff(client, a, 'treas1', 'treasurer')
    tx = post_tx(client, a, 1000, description='Sunday').get_json()['id']
    assert client.post(f'/api/finance/{tx}/verify', headers=treasurer).status_code == 200
    changed = client.put(f'/api/finance/{tx}', headers=treasurer, json={'amount': 1})
    assert changed.status_code == 409 and changed.get_json()['code'] == 'LOCKED'
    assert client.put(f'/api/finance/{tx}', headers=treasurer, json={'verified': False}).status_code == 409
    note = client.put(f'/api/finance/{tx}', headers=treasurer, json={'notes': 'checked'})
    assert note.status_code == 200 and note.get_json()['notes'] == 'checked'
    assert [t['amount'] for t in listed(client, a)] == [1000.0]


def test_delete_voids_and_keeps_the_row(client):
    a = admin(client)
    treasurer = staff(client, a, 'treas1', 'treasurer')
    keep = post_tx(client, a, 300).get_json()['id']
    gone = post_tx(client, a, 700).get_json()['id']
    assert client.delete(f'/api/finance/{gone}', headers=treasurer).status_code == 403
    res = client.delete(f'/api/finance/{gone}', headers=a, json={'reason': 'Entered twice'})
    assert res.status_code == 200
    assert res.get_json()['transaction']['status'] == 'void'
    assert res.get_json()['transaction']['void_reason'] == 'Entered twice'
    assert [t['id'] for t in listed(client, a)] == [keep]
    assert len(listed(client, a, '?include_void=1')) == 2
    assert client.get('/api/finance/summary', headers=a).get_json()['total_income'] == 300.0
    assert client.get('/api/dashboard/stats', headers=a).get_json()['finance']['monthly_income'] == 300.0
    assert client.put(f'/api/finance/{gone}', headers=a, json={'notes': 'x'}).status_code == 409
    assert client.post(f'/api/finance/{gone}/verify', headers=treasurer).status_code == 409
    assert client.delete(f'/api/finance/{gone}', headers=a).status_code == 409


def test_a_voided_reference_can_be_used_again(client):
    a = admin(client)
    first = post_tx(client, a, 100, mpesa_ref='SK55AAA55').get_json()['id']
    client.delete(f'/api/finance/{first}', headers=a)
    assert post_tx(client, a, 100, mpesa_ref='SK55AAA55').status_code == 201


def test_every_change_is_in_the_audit_trail(client):
    a = admin(client)
    tx = post_tx(client, a, 1000).get_json()['id']
    client.put(f'/api/finance/{tx}', headers=a, json={'amount': 1200})
    client.delete(f'/api/finance/{tx}', headers=a, json={'reason': 'Wrong church'})
    res = client.get(f'/api/finance/audit?entity_id={tx}', headers=a)
    assert res.status_code == 200
    entries = res.get_json()['entries']
    assert [e['action'] for e in entries] == ['finance.void', 'finance.update', 'finance.create']
    update = entries[1]
    assert update['before']['amount'] == '1000.00' and update['after']['amount'] == '1200.00'
    assert entries[0]['after']['status'] == 'void'
    assert all(e['user_id'] for e in entries)


def test_audit_trail_is_admin_only_and_church_scoped(client):
    a = admin(client)
    post_tx(client, a, 100)
    treasurer = staff(client, a, 'treas1', 'treasurer')
    assert client.get('/api/finance/audit', headers=treasurer).status_code == 403
    client.post('/api/churches/', headers=a, json={
        'name': 'Second Church', 'admin_username': 'badmin',
        'admin_email': 'b@example.org', 'admin_password': B_PASS})
    b = login(client, 'badmin', B_PASS)
    assert client.get('/api/finance/audit', headers=b).get_json()['entries'] == []
    assert len(client.get('/api/finance/audit', headers=a).get_json()['entries']) == 1


def test_audit_rows_cannot_be_changed_or_deleted(app):
    import pytest
    from models import db, AuditLog
    with app.app_context():
        row = AuditLog(church_id=1, user_id=1, action='x', entity='finance', entity_id=1)
        db.session.add(row)
        db.session.commit()
        row.action = 'changed'
        with pytest.raises(RuntimeError):
            db.session.commit()
        db.session.rollback()
        db.session.delete(db.session.get(AuditLog, row.id))
        with pytest.raises(RuntimeError):
            db.session.commit()
        db.session.rollback()


def test_member_giving_total_ignores_voided_money(client):
    a = admin(client)
    member = client.post('/api/members/', headers=a,
                         json={'first_name': 'Alpha', 'last_name': 'Test'}).get_json()['id']
    post_tx(client, a, 400, member_id=member)
    gone = post_tx(client, a, 600, member_id=member).get_json()['id']
    assert client.get(f'/api/members/{member}', headers=a).get_json()['total_giving'] == 1000.0
    client.delete(f'/api/finance/{gone}', headers=a)
    assert client.get(f'/api/members/{member}', headers=a).get_json()['total_giving'] == 400.0
    assert post_tx(client, a, 50, member_id=987654).status_code == 404
