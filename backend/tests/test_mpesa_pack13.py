"""Fix Pack 13: callback paths Safaricom accepts, and a status check when no callback arrives."""
from datetime import datetime, timedelta

import pytest

from conftest import ADMIN_PASSWORD

SECRET = 'callback-secret-0123456789abcdef'


@pytest.fixture(autouse=True)
def mpesa_env(monkeypatch):
    monkeypatch.setenv('MPESA_CALLBACK_SECRET', SECRET)


@pytest.fixture()
def fake(monkeypatch):
    from services import mpesa
    state = {'query': None}

    def push(phone, amount, account_ref, description):
        return {'merchant_request_id': 'M-1', 'checkout_request_id': 'ws_CO_Q1'}

    def query(checkout):
        if state['query'] is None:
            raise mpesa.MpesaError('still processing')
        return state['query']
    monkeypatch.setattr(mpesa, 'stk_push', push)
    monkeypatch.setattr(mpesa, 'stk_query', query)
    return state


def admin(client):
    res = client.post('/api/auth/login', json={'username': 'admin', 'password': ADMIN_PASSWORD})
    return {'Authorization': 'Bearer ' + res.get_json()['access_token']}


def age(app, request_id, seconds):
    from models import db, PaymentRequest
    with app.app_context():
        pr = db.session.get(PaymentRequest, request_id)
        pr.created_at = datetime.utcnow() - timedelta(seconds=seconds)
        db.session.commit()


def status(client, h, request_id):
    from routes import payments
    payments._last_query.clear()
    return client.get('/api/payments/requests/%d' % request_id, headers=h).get_json()


def test_callback_address_avoids_the_blocked_word(monkeypatch):
    from services import mpesa
    cfg = {'MPESA_CALLBACK_URL': 'https://churchos-yitr.onrender.com', 'MPESA_CALLBACK_SECRET': SECRET}
    path = mpesa.callback_url(cfg).split('onrender.com', 1)[1]
    assert 'mpesa' not in path.lower() and path.startswith('/api/payments/stk/callback/')


def test_new_callback_paths_work(client, fake):
    h = admin(client)
    req = client.post('/api/payments/mpesa/stk', headers=h, json={'phone': '0711000111', 'amount': 5}).get_json()
    body = {'Body': {'stkCallback': {'CheckoutRequestID': 'ws_CO_Q1', 'ResultCode': 0, 'ResultDesc': 'ok',
            'CallbackMetadata': {'Item': [{'Name': 'Amount', 'Value': 5},
                                          {'Name': 'MpesaReceiptNumber', 'Value': 'SKQ1AAA111'}]}}}}
    assert client.post('/api/payments/stk/callback/' + SECRET, json=body).status_code == 200
    assert status(client, h, req['id'])['status'] == 'paid'
    assert client.post('/api/payments/c2b/' + SECRET + '/validation', json={}).status_code == 200


def test_status_check_settles_a_prompt_when_no_callback_came(app, client, fake):
    h = admin(client)
    req = client.post('/api/payments/mpesa/stk', headers=h, json={'phone': '0711000111', 'amount': 5}).get_json()
    assert status(client, h, req['id'])['status'] == 'pending'      # too new to check
    age(app, req['id'], 30)
    assert status(client, h, req['id'])['status'] == 'pending'      # Safaricom still processing
    fake['query'] = ('0', 'The service request is processed successfully.')
    assert status(client, h, req['id'])['status'] == 'paid'
    rows = client.get('/api/finance/', headers=h).get_json()['transactions']
    assert len(rows) == 1 and rows[0]['amount'] == 5.0 and rows[0]['mpesa_ref'] is None
    late = {'Body': {'stkCallback': {'CheckoutRequestID': 'ws_CO_Q1', 'ResultCode': 0, 'ResultDesc': 'ok',
            'CallbackMetadata': {'Item': [{'Name': 'Amount', 'Value': 5},
                                          {'Name': 'MpesaReceiptNumber', 'Value': 'SKQ1LATE11'}]}}}}
    client.post('/api/payments/stk/callback/' + SECRET, json=late)
    rows = client.get('/api/finance/', headers=h).get_json()['transactions']
    assert len(rows) == 1 and rows[0]['mpesa_ref'] == 'SKQ1LATE11'
    assert status(client, h, req['id'])['mpesa_receipt'] == 'SKQ1LATE11'


def test_status_check_records_a_cancelled_prompt(app, client, fake):
    h = admin(client)
    req = client.post('/api/payments/mpesa/stk', headers=h, json={'phone': '0711000111', 'amount': 5}).get_json()
    age(app, req['id'], 30)
    fake['query'] = ('1032', 'Request cancelled by user')
    assert status(client, h, req['id'])['status'] == 'cancelled'
    assert client.get('/api/finance/', headers=h).get_json()['transactions'] == []
