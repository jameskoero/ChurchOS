"""Fix Pack 12: sign-in survives a sleeping server, and the browser's CORS check passes."""
import os

from conftest import BACKEND

REPO = os.path.dirname(BACKEND)
ORIGIN = 'https://churchos-app.vercel.app'


def text(*parts):
    with open(os.path.join(REPO, *parts), encoding='utf8') as f:
        return f.read()


def test_browser_preflight_for_login_is_allowed(client):
    res = client.open('/api/auth/login', method='OPTIONS', headers={
        'Origin': ORIGIN,
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'content-type'})
    assert res.status_code in (200, 204)
    assert res.headers.get('Access-Control-Allow-Origin') == ORIGIN
    assert 'POST' in res.headers.get('Access-Control-Allow-Methods', '')
    assert 'content-type' in res.headers.get('Access-Control-Allow-Headers', '').lower()


def test_login_response_carries_the_cors_header(client):
    res = client.post('/api/auth/login', headers={'Origin': ORIGIN},
                      json={'username': 'nobody', 'password': 'wrong-password-1'})
    assert res.status_code == 401
    assert res.headers.get('Access-Control-Allow-Origin') == ORIGIN


def test_frontend_waits_long_enough_for_a_cold_start():
    api = text('frontend', 'src', 'api.js')
    assert 'timeout: 60000' in api and 'healthAPI' in api
    login = text('frontend', 'src', 'pages', 'Login.js')
    assert 'healthAPI.check()' in login and 'The server did not answer' in login
