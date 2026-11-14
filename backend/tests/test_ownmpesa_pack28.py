"""Fix Pack 28: a church's own Safaricom Paybill. Off until configured; keys encrypted and write-only; callbacks
tied to one church; the platform's keys are never used for a church that has its own, or for a broken vault.
No test touches the network: Safaricom calls are replaced with fakes."""
import pytest
from cryptography.fernet import Fernet

from conftest import ADMIN_PASSWORD
from models import ChurchMpesa, PaymentRequest, PaymentEvent, Finance, db
from services import mpesa, vault
from test_governance_pack22 import PASS, church, login

PLATFORM_SECRET = 'platform-secret-0123456789abcdef'


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv('MPESA_VAULT_KEY', Fernet.generate_key().decode())
    monkeypatch.setenv('MPESA_CALLBACK_URL', 'https://churchos-yitr.onrender.com')
    monkeypatch.setenv('MPESA_CALLBACK_SECRET', PLATFORM_SECRET)
    monkeypatch.delenv('MPESA_ALLOWED_IPS', raising=False)
    monkeypatch.delenv('MPESA_ENV', raising=False)


@pytest.fixture()
def fake(monkeypatch):
    calls = {'token': [], 'push': [], 'register': [], 'query': []}

    def access_token(cfg):
        calls['token'].append(cfg['MPESA_CONSUMER_KEY'])
        if cfg['MPESA_CONSUMER_KEY'] == 'bad-consumer-key':
            raise mpesa.MpesaError('Safaricom answered HTTP 400')
        return 'tok'

    def call(url, payload=None, headers=None):
        calls['register'].append((url, payload))
        return {'ResponseCode': '0', 'ResponseDescription': 'Success'}

    def stk_push(phone, amount, ref, desc, cfg=None):
        calls['push'].append({'cfg': cfg, 'phone': phone, 'amount': amount})
        return {'merchant_request_id': 'M-%d' % len(calls['push']), 'checkout_request_id': 'ws_OWN_%d' % len(calls['push'])}

    def stk_query(checkout, cfg=None):
        calls['query'].append((checkout, cfg))
        return '0', 'ok'
    monkeypatch.setattr(mpesa, 'access_token', access_token)
    monkeypatch.setattr(mpesa, '_call', call)
    monkeypatch.setattr(mpesa, 'stk_push', stk_push)
    monkeypatch.setattr(mpesa, 'stk_query', stk_query)
    return calls


KEYS = {'shortcode': '123456', 'env': 'sandbox', 'consumer_key': 'consumer-key-AAAA1111',
        'consumer_secret': 'consumer-secret-BBBB2222', 'passkey': 'passkey-CCCC3333DDDD4444'}


def two(client):
    owner = login(client, 'admin', ADMIN_PASSWORD)
    a_id, a = church(client, owner, 'Kaego Altar', 'sp1')
    b_id, b = church(client, owner, 'Other Altar', 'sp2')
    return owner, (a_id, a), (b_id, b)


def connect(client, h, **over):
    body = dict(KEYS, **over)
    res = client.put('/api/payments/own', headers=h, json=body)
    assert res.status_code == 200, res.get_json()
    return res.get_json()['own']


def switch_on(client, h):
    assert client.post('/api/payments/own/test', headers=h).status_code == 200
    assert client.post('/api/payments/own/enable', headers=h, json={'enabled': True}).status_code == 200


def test_vault_round_trip_and_failures(monkeypatch):
    token = vault.encrypt('secret value')
    assert token != 'secret value' and vault.decrypt(token) == 'secret value'
    monkeypatch.setenv('MPESA_VAULT_KEY', Fernet.generate_key().decode())      # key changed: old data unreadable
    with pytest.raises(vault.VaultError):
        vault.decrypt(token)
    monkeypatch.setenv('MPESA_VAULT_KEY', '')
    assert vault.ready() is False
    with pytest.raises(vault.VaultError):
        vault.encrypt('x')


def test_off_by_default_and_only_admins_see_the_screen(client, fake):
    _, (_, a), _ = two(client)
    body = client.get('/api/payments/own', headers=a).get_json()
    assert body['own'] is None and body['missing'] == []
    assert client.post('/api/payments/own/enable', headers=a, json={'enabled': True}).status_code == 400


def test_keys_are_stored_encrypted_and_never_returned(app, client, fake):
    _, (a_id, a), _ = two(client)
    view = connect(client, a)
    assert view['keys_saved'] is True and view['enabled'] is False
    text = str(client.get('/api/payments/own', headers=a).get_json())
    for secret in (KEYS['consumer_key'], KEYS['consumer_secret'], KEYS['passkey']):
        assert secret not in text
    with app.app_context():
        row = ChurchMpesa.query.filter_by(church_id=a_id).first()
        assert KEYS['passkey'] not in (row.passkey_enc + row.consumer_key_enc + row.consumer_secret_enc)
        assert vault.decrypt(row.passkey_enc) == KEYS['passkey']


def test_saving_needs_the_vault_and_good_input(client, fake, monkeypatch):
    _, (_, a), _ = two(client)
    assert client.put('/api/payments/own', headers=a, json=dict(KEYS, shortcode='12ab')).status_code == 400
    assert client.put('/api/payments/own', headers=a, json=dict(KEYS, env='maybe')).status_code == 400
    assert client.put('/api/payments/own', headers=a, json=dict(KEYS, passkey='')).status_code == 400
    monkeypatch.setenv('MPESA_VAULT_KEY', '')
    res = client.put('/api/payments/own', headers=a, json=KEYS)
    assert res.status_code == 503 and res.get_json()['code'] == 'VAULT_NOT_READY'


def test_cannot_switch_on_before_a_good_test_and_a_bad_key_is_refused(client, fake):
    _, (_, a), _ = two(client)
    connect(client, a, consumer_key='bad-consumer-key')
    assert client.post('/api/payments/own/test', headers=a).status_code == 502
    assert client.post('/api/payments/own/enable', headers=a, json={'enabled': True}).status_code == 400
    connect(client, a)
    switch_on(client, a)
    # Changing the target switches it off again until it is retested.
    view = connect(client, a, shortcode='654321')
    assert view['enabled'] is False and view['verified_at'] is None


def test_a_live_shortcode_belongs_to_one_church(client, fake):
    _, (_, a), (_, b) = two(client)
    connect(client, a, env='live')
    res = client.put('/api/payments/own', headers=b, json=dict(KEYS, env='live'))
    assert res.status_code == 409


def test_register_urls_are_clean_and_live_registration_is_once(client, fake):
    _, (_, a), _ = two(client)
    connect(client, a, env='live')
    assert client.post('/api/payments/own/register-c2b', headers=a).status_code == 400      # not tested yet
    assert client.post('/api/payments/own/test', headers=a).status_code == 200
    assert client.post('/api/payments/own/register-c2b', headers=a).status_code == 200
    url, payload = fake['register'][-1]
    assert url.endswith('/mpesa/c2b/v1/registerurl') and url.startswith(mpesa.LIVE)
    for word in ('mpesa', 'safaricom', 'query'):
        assert word not in payload['ConfirmationURL'].lower() and word not in payload['ValidationURL'].lower()
    assert payload['ShortCode'] == '123456' and payload['ResponseType'] == 'Completed'
    assert client.post('/api/payments/own/register-c2b', headers=a).get_json()['code'] == 'ALREADY_REGISTERED'


def test_prompts_use_the_churchs_own_keys_and_never_the_platforms(app, client, fake):
    _, (a_id, a), _ = two(client)
    connect(client, a)
    switch_on(client, a)
    res = client.post('/api/payments/mpesa/stk', headers=a, json={'phone': '0712345678', 'amount': 500})
    assert res.status_code == 202, res.get_json()
    cfg = fake['push'][-1]['cfg']
    assert cfg['MPESA_SHORTCODE'] == '123456' and cfg['MPESA_PASSKEY'] == KEYS['passkey']
    assert cfg['MPESA_CALLBACK_SECRET'] != PLATFORM_SECRET
    with app.app_context():
        assert PaymentRequest.query.filter_by(church_id=a_id).first().via == 'own'


def test_a_broken_vault_stops_prompts_instead_of_using_platform_keys(client, fake, monkeypatch):
    _, (_, a), _ = two(client)
    connect(client, a)
    switch_on(client, a)
    monkeypatch.setenv('MPESA_VAULT_KEY', Fernet.generate_key().decode())
    res = client.post('/api/payments/mpesa/stk', headers=a, json={'phone': '0712345678', 'amount': 500})
    assert res.status_code == 503 and res.get_json()['code'] == 'MPESA_OWN_BROKEN'
    assert fake['push'] == []


def test_live_platform_keys_are_refused_for_a_church_without_its_own(client, fake, monkeypatch):
    _, (_, a), _ = two(client)
    monkeypatch.setenv('MPESA_ENV', 'live')
    res = client.post('/api/payments/mpesa/stk', headers=a, json={'phone': '0712345678', 'amount': 500})
    assert res.status_code == 409 and res.get_json()['code'] == 'MPESA_OWN_REQUIRED'
    assert fake['push'] == []


def _token_of(app, church_id):
    with app.app_context():
        return ChurchMpesa.query.filter_by(church_id=church_id).first().callback_token


def _paid_body(checkout, amount=500):
    return {'Body': {'stkCallback': {'MerchantRequestID': 'M-1', 'CheckoutRequestID': checkout, 'ResultCode': 0,
            'ResultDesc': 'ok', 'CallbackMetadata': {'Item': [
                {'Name': 'Amount', 'Value': amount}, {'Name': 'MpesaReceiptNumber', 'Value': 'OWN1234567'}]}}}}


def test_a_church_callback_records_money_only_for_that_church(app, client, fake):
    _, (a_id, a), (b_id, b) = two(client)
    connect(client, a)
    switch_on(client, a)
    connect(client, b, shortcode='777777')
    switch_on(client, b)
    client.post('/api/payments/mpesa/stk', headers=a, json={'phone': '0712345678', 'amount': 500})
    # Church B's token cannot settle church A's prompt.
    wrong = client.post('/api/payments/stk/callback/' + _token_of(app, b_id), json=_paid_body('ws_OWN_1'))
    assert wrong.status_code == 200
    with app.app_context():
        assert PaymentRequest.query.filter_by(church_id=a_id).first().status == 'pending'
    # The platform secret cannot settle an own-church prompt either.
    assert client.post('/api/payments/stk/callback/' + PLATFORM_SECRET, json=_paid_body('ws_OWN_1')).status_code == 200
    with app.app_context():
        assert PaymentRequest.query.filter_by(church_id=a_id).first().status == 'pending'
    right = client.post('/api/payments/stk/callback/' + _token_of(app, a_id), json=_paid_body('ws_OWN_1'))
    assert right.status_code == 200
    with app.app_context():
        assert PaymentRequest.query.filter_by(church_id=a_id).first().status == 'paid'
        assert Finance.query.filter_by(church_id=a_id, mpesa_ref='OWN1234567').count() == 1
        assert Finance.query.filter_by(church_id=b_id).count() == 0


def test_unknown_callback_token_is_not_found(client, fake):
    two(client)
    assert client.post('/api/payments/stk/callback/not-a-real-token', json={}).status_code == 404


def test_paybill_notices_must_match_the_churchs_own_shortcode(app, client, fake):
    _, (a_id, a), _ = two(client)
    connect(client, a)
    token = _token_of(app, a_id)
    notice = {'TransID': 'OWNC2B0001', 'TransAmount': '300', 'BusinessShortCode': '123456', 'BillRefNumber': 'nobody',
              'MSISDN': 'x', 'FirstName': 'A', 'TransTime': '20261114120000'}
    assert client.post('/api/payments/c2b/%s/confirmation' % token, json=dict(notice, TransID='OWNC2B0002',
                       BusinessShortCode='999999')).status_code == 200
    with app.app_context():
        assert PaymentEvent.query.count() == 0                       # wrong shortcode for this token: ignored
    assert client.post('/api/payments/c2b/%s/confirmation' % token, json=notice).status_code == 200
    with app.app_context():
        ev = PaymentEvent.query.one()
        assert ev.church_id == a_id and ev.status == 'unmatched'


def test_status_check_for_an_own_prompt_uses_the_churchs_keys(app, client, fake, monkeypatch):
    from datetime import datetime, timedelta
    from routes import payments
    payments._last_query.clear()
    _, (a_id, a), _ = two(client)
    connect(client, a)
    switch_on(client, a)
    client.post('/api/payments/mpesa/stk', headers=a, json={'phone': '0712345678', 'amount': 500})
    with app.app_context():
        pr = PaymentRequest.query.filter_by(church_id=a_id).first()
        pr.created_at = datetime.utcnow() - timedelta(minutes=2)
        db.session.commit()
        pid = pr.id
    res = client.get('/api/payments/requests/%d' % pid, headers=a)
    assert res.status_code == 200 and res.get_json()['status'] == 'paid'
    assert fake['query'][-1][1]['MPESA_SHORTCODE'] == '123456'


def test_only_the_churchs_admin_can_change_it(client, fake):
    owner, (_, a), (_, b) = two(client)
    connect(client, a)
    assert client.get('/api/payments/own', headers=b).get_json()['own'] is None      # B sees nothing of A's
    assert client.delete('/api/payments/own', headers=b).status_code == 200            # B only deletes B's own (none)
    assert client.get('/api/payments/own', headers=a).get_json()['own'] is not None
    assert client.delete('/api/payments/own', headers=a).status_code == 200
    assert client.get('/api/payments/own', headers=a).get_json()['own'] is None
