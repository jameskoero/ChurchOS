"""Fix Pack 17: plans, owner-confirmed invoices, member limits, and pausing new records when a plan ends."""
from datetime import datetime, timedelta

import models
from conftest import ADMIN_PASSWORD

B_PASS = 'Second-Church-2468'


def login(client, username, password):
    res = client.post('/api/auth/login', json={'username': username, 'password': password})
    assert res.status_code == 200, res.get_json()
    return {'Authorization': 'Bearer ' + res.get_json()['access_token']}


def owner(client):
    return login(client, 'admin', ADMIN_PASSWORD)


def second_church(client, o):
    res = client.post('/api/churches/', headers=o, json={'name': 'Second Church', 'admin_username': 'badmin',
                      'admin_email': 'b@example.org', 'admin_password': B_PASS})
    assert res.status_code == 201, res.get_json()
    return res.get_json()['church']['id'], login(client, 'badmin', B_PASS)


def set_dates(app, church_id, **fields):
    with app.app_context():
        church = models.db.session.get(models.Church, church_id)
        for key, value in fields.items():
            setattr(church, key, value)
        models.db.session.commit()


def add_member(client, h, first='Grace'):
    return client.post('/api/members/', headers=h, json={'first_name': first, 'last_name': 'Otieno'})


def test_owner_church_is_complimentary_and_unlimited(client):
    body = client.get('/api/billing/status', headers=owner(client)).get_json()
    assert body['state'] == 'complimentary' and body['member_limit'] is None


def test_new_church_starts_on_trial_with_a_member_limit(client, monkeypatch):
    o = owner(client)
    _, b = second_church(client, o)
    body = client.get('/api/billing/status', headers=b).get_json()
    assert body['state'] == 'trial' and body['plan'] == 'trial' and body['member_limit'] == 50
    assert 28 <= body['days_left'] <= 30
    monkeypatch.setitem(models.PLAN_LIMITS['trial'], 'members', 2)
    assert add_member(client, b, 'One').status_code == 201
    assert add_member(client, b, 'Two').status_code == 201
    third = add_member(client, b, 'Three')
    assert third.status_code == 402 and third.get_json()['code'] == 'PLAN_LIMIT'


def test_ended_trial_has_grace_then_pauses_new_records_but_not_reading(app, client):
    o = owner(client)
    church_id, b = second_church(client, o)
    set_dates(app, church_id, trial_ends_at=datetime.utcnow() - timedelta(days=2))
    body = client.get('/api/billing/status', headers=b).get_json()
    assert body['state'] == 'grace' and body['previous'] == 'trial'
    assert add_member(client, b).status_code == 201
    set_dates(app, church_id, trial_ends_at=datetime.utcnow() - timedelta(days=10))
    assert client.get('/api/billing/status', headers=b).get_json()['state'] == 'locked'
    paused = add_member(client, b, 'Late')
    assert paused.status_code == 402 and paused.get_json()['code'] == 'SUBSCRIPTION_LOCKED'
    assert client.get('/api/members/', headers=b).status_code == 200
    assert client.post('/api/auth/login', json={'username': 'badmin', 'password': B_PASS}).status_code == 200


def test_owner_invoices_and_confirms_payment_which_restores_the_church(app, client):
    o = owner(client)
    church_id, b = second_church(client, o)
    set_dates(app, church_id, trial_ends_at=datetime.utcnow() - timedelta(days=10))
    assert client.post('/api/billing/invoices', headers=b, json={'church_id': church_id, 'plan': 'seed'}).status_code == 403
    assert client.post('/api/billing/invoices', headers=o, json={'church_id': church_id, 'plan': 'trial'}).status_code == 400
    assert client.post('/api/billing/invoices', headers=o, json={'church_id': church_id, 'plan': 'seed', 'months': 13}).status_code == 400
    inv = client.post('/api/billing/invoices', headers=o, json={'church_id': church_id, 'plan': 'seed', 'months': 2})
    assert inv.status_code == 201 and inv.get_json()['amount'] == 3000.0
    inv_id = inv.get_json()['id']
    due = client.get('/api/billing/status', headers=b).get_json()['invoices_due']
    assert [d['id'] for d in due] == [inv_id]
    assert client.post('/api/billing/invoices/%d/paid' % inv_id, headers=b, json={'method': 'mpesa', 'reference': 'X'}).status_code == 403
    assert client.post('/api/billing/invoices/%d/paid' % inv_id, headers=o, json={'method': 'mpesa'}).status_code == 400
    paid = client.post('/api/billing/invoices/%d/paid' % inv_id, headers=o, json={'method': 'mpesa', 'reference': 'SKPAID123'})
    assert paid.status_code == 200 and paid.get_json()['status'] == 'paid'
    body = client.get('/api/billing/status', headers=b).get_json()
    assert body['state'] == 'active' and body['plan'] == 'seed' and body['member_limit'] == 100
    assert 58 <= body['days_left'] <= 60
    assert add_member(client, b).status_code == 201
    assert client.post('/api/billing/invoices/%d/void' % inv_id, headers=o).status_code == 409
    rev = client.get('/api/billing/revenue', headers=o).get_json()
    assert rev['total_paid'] == 3000.0 and rev['churches_by_state'].get('active') == 1
    assert client.get('/api/billing/revenue', headers=b).status_code == 403


def test_church_admins_see_only_their_own_invoices(client):
    o = owner(client)
    church_id, b = second_church(client, o)
    client.post('/api/billing/invoices', headers=o, json={'church_id': church_id, 'plan': 'seed'})
    other = client.post('/api/churches/', headers=o, json={'name': 'Third Church', 'admin_username': 'cadmin',
                        'admin_email': 'c@example.org', 'admin_password': B_PASS})
    c = login(client, 'cadmin', B_PASS)
    client.post('/api/billing/invoices', headers=o, json={'church_id': other.get_json()['church']['id'], 'plan': 'growth'})
    assert [i['plan'] for i in client.get('/api/billing/invoices', headers=b).get_json()['invoices']] == ['seed']
    assert [i['plan'] for i in client.get('/api/billing/invoices', headers=c).get_json()['invoices']] == ['growth']
    assert len(client.get('/api/billing/invoices', headers=o).get_json()['invoices']) == 2
    assert client.get('/api/billing/churches', headers=b).status_code == 403
