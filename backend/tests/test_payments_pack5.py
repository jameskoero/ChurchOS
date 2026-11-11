"""Fix Pack 5: M-Pesa prompts, unsigned callbacks, Paybill matching and the inbox."""
import os
from datetime import date

import pytest

from conftest import ADMIN_PASSWORD, BACKEND

SECRET = 'callback-secret-0123456789abcdef'
STAFF = 'Staff-Login-13579'
B_PASS = 'Second-Church-2468'
TODAY = date.today().isoformat()
CB = '/api/payments/mpesa/callback/'
C2B = '/api/payments/mpesa/c2b/'


@pytest.fixture(autouse=True)
def mpesa_env(monkeypatch):
    monkeypatch.setenv('MPESA_CALLBACK_SECRET', SECRET)
    monkeypatch.delenv('MPESA_ALLOWED_IPS', raising=False)


@pytest.fixture()
def fake_stk(monkeypatch):
    from services import mpesa
    calls = []

    def fake(phone, amount, account_ref, description):
        calls.append({'phone': phone, 'amount': amount, 'ref': account_ref})
        return {'merchant_request_id': 'M-%d' % len(calls), 'checkout_request_id': 'ws_CO_%d' % len(calls)}
    monkeypatch.setattr(mpesa, 'stk_push', fake)
    return calls


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


def member(client, h, first='Grace'):
    res = client.post('/api/members/', headers=h, json={'first_name': first, 'last_name': 'Otieno',
                                                         'phone': '0711000111'})
    assert res.status_code == 201, res.get_json()
    return res.get_json()


def callback(client, checkout, code=0, amount=500, receipt='SK12ABC34D', secret=SECRET):
    body = {'Body': {'stkCallback': {'MerchantRequestID': 'M-1', 'CheckoutRequestID': checkout,
                                     'ResultCode': code, 'ResultDesc': 'done'}}}
    if code == 0:
        body['Body']['stkCallback']['CallbackMetadata'] = {'Item': [
            {'Name': 'Amount', 'Value': amount}, {'Name': 'MpesaReceiptNumber', 'Value': receipt},
            {'Name': 'PhoneNumber', 'Value': 254711000111}]}
    return client.post(CB + secret, json=body)


def start(client, h, **extra):
    body = {'phone': '0711000111', 'amount': 500}
    body.update(extra)
    return client.post('/api/payments/mpesa/stk', headers=h, json=body)


def ledger(client, h):
    return client.get('/api/finance/', headers=h).get_json()['transactions']


def set_paybill(client, h, shortcode='600111'):
    me = client.get('/api/auth/me', headers=h).get_json()
    res = client.put('/api/churches/%d' % me['church_id'], headers=h, json={'paybill': shortcode})
    assert res.status_code == 200, res.get_json()


def c2b(client, bill_ref, trans_id='TX1', amount=300, shortcode='600111', secret=SECRET):
    return client.post(C2B + secret + '/confirmation', json={
        'TransID': trans_id, 'TransAmount': str(amount), 'BusinessShortCode': shortcode,
        'BillRefNumber': bill_ref, 'MSISDN': 'hashed', 'FirstName': 'Jane', 'LastName': 'Doe',
        'TransTime': '20261110120000'})


def test_phone_numbers_are_normalised():
    from routes.payments import normalize_phone
    for good in ('0712345678', '+254712345678', '254712345678', '712345678', '0112345678', '0712 345 678'):
        assert normalize_phone(good) and normalize_phone(good).startswith('254'), good
    assert normalize_phone('0712345678') == '254712345678'
    for bad in ('12345', 'abc', '0212345678', '2547123456789', None, ''):
        assert normalize_phone(bad) is None, bad


def test_stk_needs_a_finance_role_and_good_input(client, fake_stk):
    a = admin(client)
    viewer = staff(client, a, 'view1', 'viewer')
    assert start(client, viewer).status_code == 403
    assert start(client, a, phone='123').status_code == 400
    for bad in (0, -1, 'abc', 1.5, 150001):
        assert start(client, a, amount=bad).status_code == 400, bad
    assert start(client, a, transaction_type='expense').status_code == 400
    assert start(client, a, member_id=99999).status_code == 404
    assert fake_stk == []


def test_stk_creates_a_pending_request_with_a_masked_phone(client, fake_stk):
    a = admin(client)
    m = member(client, a)
    res = start(client, a, member_id=m['id'])
    assert res.status_code == 202, res.get_json()
    body = res.get_json()
    assert body['status'] == 'pending' and body['amount'] == 500.0
    assert '0711000111' not in str(body) and '254711000111' not in str(body)
    assert fake_stk[0]['phone'] == '254711000111' and fake_stk[0]['ref'] == m['member_id']
    assert client.get('/api/payments/requests/%d' % body['id'], headers=a).get_json()['status'] == 'pending'


def test_stk_says_so_when_mpesa_is_not_set_up(client, monkeypatch):
    for name in ('MPESA_CONSUMER_KEY', 'MPESA_CONSUMER_SECRET', 'MPESA_SHORTCODE', 'MPESA_PASSKEY', 'MPESA_CALLBACK_URL'):
        monkeypatch.delenv(name, raising=False)
    res = start(client, admin(client))
    assert res.status_code == 503 and res.get_json()['code'] == 'MPESA_NOT_CONFIGURED'


def test_callback_secret_is_checked(client, fake_stk, monkeypatch):
    a = admin(client)
    start(client, a)
    assert callback(client, 'ws_CO_1', secret='wrong-secret-000000000000').status_code == 404
    assert ledger(client, a) == []
    monkeypatch.delenv('MPESA_CALLBACK_SECRET')
    assert callback(client, 'ws_CO_1').status_code == 503


def test_a_confirmed_payment_is_recorded_once(client, fake_stk):
    a = admin(client)
    m = member(client, a)
    req = start(client, a, member_id=m['id'], transaction_type='offering').get_json()
    assert callback(client, 'ws_CO_1').get_json()['ResultCode'] == 0
    rows = ledger(client, a)
    assert len(rows) == 1
    row = rows[0]
    assert row['amount'] == 500.0 and row['mpesa_ref'] == 'SK12ABC34D'
    assert row['transaction_type'] == 'offering' and row['member_id'] == m['id']
    assert row['payment_method'] == 'mpesa' and row['verified'] is False
    assert client.get('/api/payments/requests/%d' % req['id'], headers=a).get_json()['status'] == 'paid'
    callback(client, 'ws_CO_1')
    assert len(ledger(client, a)) == 1
    actions = [e['action'] for e in client.get('/api/finance/audit', headers=a).get_json()['entries']]
    assert 'payment.paid' in actions and 'payment.request' in actions


def test_cancelled_failed_and_mismatched_payments_record_nothing(client, fake_stk):
    a = admin(client)
    r1 = start(client, a).get_json()
    callback(client, 'ws_CO_1', code=1032)
    r2 = start(client, a).get_json()
    callback(client, 'ws_CO_2', code=1)
    r3 = start(client, a).get_json()
    callback(client, 'ws_CO_3', amount=499, receipt='SK99ZZZ99')
    status = lambda r: client.get('/api/payments/requests/%d' % r['id'], headers=a).get_json()['status']
    assert [status(r1), status(r2), status(r3)] == ['cancelled', 'failed', 'review']
    assert ledger(client, a) == []


def test_unknown_checkout_is_acknowledged_and_ignored(client):
    res = callback(client, 'ws_CO_unknown')
    assert res.status_code == 200 and res.get_json()['ResultCode'] == 0
    assert ledger(client, admin(client)) == []


def test_requests_are_church_scoped(client, fake_stk):
    a = admin(client)
    req = start(client, a).get_json()
    client.post('/api/churches/', headers=a, json={'name': 'Second Church', 'admin_username': 'badmin',
                'admin_email': 'b@example.org', 'admin_password': B_PASS})
    b = login(client, 'badmin', B_PASS)
    assert client.get('/api/payments/requests/%d' % req['id'], headers=b).status_code == 404
    assert client.get('/api/payments/requests', headers=b).get_json()['requests'] == []


def test_paybill_payment_matches_a_member_by_account_text(client):
    a = admin(client)
    set_paybill(client, a)
    m = member(client, a)
    assert c2b(client, m['member_id'], trans_id='TX1').get_json()['ResultCode'] == 0
    row = ledger(client, a)[0]
    assert row['amount'] == 300.0 and row['member_id'] == m['id'] and row['mpesa_ref'] == 'TX1'
    assert c2b(client, m['member_id'], trans_id='TX2').status_code == 200
    assert c2b(client, '0711 000 111', trans_id='TX3').status_code == 200
    assert c2b(client, m['member_id'].split('-')[1], trans_id='TX4').status_code == 200
    assert len(ledger(client, a)) == 4
    c2b(client, m['member_id'], trans_id='TX1')
    assert len(ledger(client, a)) == 4


def test_unmatched_payment_goes_to_the_inbox_and_can_be_matched(client):
    a = admin(client)
    set_paybill(client, a)
    m = member(client, a)
    c2b(client, 'WHO IS THIS', trans_id='TXU1')
    inbox = client.get('/api/payments/inbox', headers=a).get_json()
    assert inbox['unmatched'] == 1 and ledger(client, a) == []
    event = inbox['events'][0]
    assert event['bill_ref'] == 'WHO IS THIS' and event['status'] == 'unmatched'
    res = client.post('/api/payments/inbox/%d/match' % event['id'], headers=a,
                      json={'member_id': m['id'], 'transaction_type': 'tithe'})
    assert res.status_code == 200 and res.get_json()['status'] == 'matched'
    assert len(ledger(client, a)) == 1
    again = client.post('/api/payments/inbox/%d/match' % event['id'], headers=a, json={'member_id': m['id']})
    assert again.status_code == 409
    assert client.get('/api/payments/inbox', headers=a).get_json()['unmatched'] == 0


def test_inbox_items_can_be_ignored_with_a_reason(client):
    a = admin(client)
    set_paybill(client, a)
    c2b(client, 'ELECTRICITY', trans_id='TXI1')
    event = client.get('/api/payments/inbox', headers=a).get_json()['events'][0]
    path = '/api/payments/inbox/%d/ignore' % event['id']
    assert client.post(path, headers=a, json={}).status_code == 400
    res = client.post(path, headers=a, json={'reason': 'Not a church payment'})
    assert res.status_code == 200 and res.get_json()['status'] == 'ignored'


def test_paybill_for_an_unknown_shortcode_is_ignored_and_inbox_is_scoped(client):
    a = admin(client)
    set_paybill(client, a)
    assert c2b(client, 'X', trans_id='TXN1', shortcode='999999').status_code == 200
    c2b(client, 'X', trans_id='TXN2')
    client.post('/api/churches/', headers=a, json={'name': 'Second Church', 'admin_username': 'badmin',
                'admin_email': 'b@example.org', 'admin_password': B_PASS})
    b = login(client, 'badmin', B_PASS)
    assert client.get('/api/payments/inbox?status=all', headers=b).get_json()['events'] == []
    assert len(client.get('/api/payments/inbox?status=all', headers=a).get_json()['events']) == 1
    viewer = staff(client, a, 'view1', 'viewer')
    assert client.get('/api/payments/inbox', headers=viewer).status_code == 403


def test_a_reference_already_in_the_ledger_is_not_recorded_twice(client):
    a = admin(client)
    set_paybill(client, a)
    m = member(client, a)
    client.post('/api/finance/', headers=a, json={'transaction_type': 'tithe', 'amount': 300,
                'transaction_date': TODAY, 'mpesa_ref': 'TXD1'})
    c2b(client, m['member_id'], trans_id='TXD1')
    assert len(ledger(client, a)) == 1
    event = client.get('/api/payments/inbox', headers=a).get_json()['events'][0]
    assert event['status'] == 'unmatched'


def test_the_old_unused_webhook_module_is_gone():
    assert not os.path.exists(os.path.join(BACKEND, 'services', 'webhook_security.py'))
