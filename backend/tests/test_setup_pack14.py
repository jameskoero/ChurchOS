"""Fix Pack 14: the app names which M-Pesa settings are missing, and can test the keys."""
import pytest

from conftest import ADMIN_PASSWORD

NAMES = ('MPESA_CONSUMER_KEY', 'MPESA_CONSUMER_SECRET', 'MPESA_SHORTCODE',
         'MPESA_PASSKEY', 'MPESA_CALLBACK_URL', 'MPESA_CALLBACK_SECRET')
GOOD = {'MPESA_CONSUMER_KEY': 'key-value', 'MPESA_CONSUMER_SECRET': 'secret-value',
        'MPESA_SHORTCODE': '174379', 'MPESA_PASSKEY': 'passkey-value',
        'MPESA_CALLBACK_URL': 'https://churchos-yitr.onrender.com',
        'MPESA_CALLBACK_SECRET': 'callback-secret-0123456789abcdef'}


@pytest.fixture()
def env(monkeypatch):
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)

    def apply(**values):
        for name, value in values.items():
            monkeypatch.setenv(name, value)
    return apply


def admin(client):
    res = client.post('/api/auth/login', json={'username': 'admin', 'password': ADMIN_PASSWORD})
    return {'Authorization': 'Bearer ' + res.get_json()['access_token']}


def test_setup_names_what_is_missing_and_never_shows_values(client, env):
    h = admin(client)
    env(MPESA_CONSUMER_KEY='key-value', MPESA_SHORTCODE='174379')
    body = client.get('/api/payments/setup', headers=h).get_json()
    assert body['configured'] is False
    assert sorted(body['missing']) == sorted(['MPESA_CONSUMER_SECRET', 'MPESA_PASSKEY',
                                              'MPESA_CALLBACK_URL', 'MPESA_CALLBACK_SECRET'])
    assert 'key-value' not in str(body) and '174379' not in str(body)


def test_setup_is_ready_when_everything_is_present(client, env):
    env(**GOOD)
    body = client.get('/api/payments/setup', headers=admin(client)).get_json()
    assert body == {'configured': True, 'missing': [], 'problems': [], 'environment': 'sandbox'}


def test_setup_flags_bad_callback_values(client, env):
    bad = dict(GOOD, MPESA_CALLBACK_URL='http://example.org/api/mpesa/callback', MPESA_CALLBACK_SECRET='short')
    env(**bad)
    body = client.get('/api/payments/setup', headers=admin(client)).get_json()
    assert body['configured'] is False and body['missing'] == []
    joined = ' '.join(body['problems'])
    assert 'https://' in joined and 'mpesa' in joined and 'no path' in joined and '16 characters' in joined


def test_prompt_error_lists_the_missing_names(client, env):
    env(MPESA_CONSUMER_KEY='key-value')
    res = client.post('/api/payments/mpesa/stk', headers=admin(client), json={'phone': '0711000111', 'amount': 1})
    assert res.status_code == 503
    assert 'MPESA_PASSKEY' in res.get_json()['missing']


def test_key_test_reports_success_and_failure(client, env, monkeypatch):
    from services import mpesa
    h = admin(client)
    assert client.post('/api/payments/setup/test', headers=h).status_code == 400
    env(**GOOD)
    monkeypatch.setattr(mpesa, 'test_credentials', lambda: True)
    ok = client.post('/api/payments/setup/test', headers=h)
    assert ok.status_code == 200 and ok.get_json()['ok'] is True

    def refuse():
        raise mpesa.MpesaError('Safaricom answered HTTP 400')
    monkeypatch.setattr(mpesa, 'test_credentials', refuse)
    bad = client.post('/api/payments/setup/test', headers=h)
    assert bad.status_code == 502 and bad.get_json()['ok'] is False
