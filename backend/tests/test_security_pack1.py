"""Fix Pack 1: admin bootstrap, sessions, rate limit, CORS, headers."""
import os

from conftest import ADMIN_PASSWORD, BACKEND, FAST

REPO = os.path.dirname(BACKEND)
LOGIN = '/api/auth/login'
REFRESH = '/api/auth/refresh'
ME = '/api/auth/me'
CHANGE = '/api/auth/change-password'


def bearer(token):
    return {'Authorization': f'Bearer {token}'}


def login(client, username='admin', password=ADMIN_PASSWORD):
    return client.post(LOGIN, json={'username': username, 'password': password})


def tokens(client):
    res = login(client)
    assert res.status_code == 200, res.get_json()
    return res.get_json()


def test_health_and_unknown_route_is_json(client):
    assert client.get('/api/health').status_code == 200
    res = client.get('/definitely-not-a-route')
    assert res.status_code == 404 and res.is_json


def test_admin_comes_from_the_environment(client):
    assert login(client).status_code == 200
    assert login(client, password='not-the-password-1').status_code == 401


def test_startup_never_resets_a_password(app):
    from app import _bootstrap
    from models import db, User
    with app.app_context():
        user = User.query.filter_by(username='admin').first()
        user.set_password('Changed-Pass-97531')
        db.session.commit()
        assert _bootstrap() == 'exists'
        again = User.query.filter_by(username='admin').first()
        assert again.check_password('Changed-Pass-97531')
        assert not again.check_password(ADMIN_PASSWORD)


def test_no_admin_is_created_without_the_variable(monkeypatch):
    monkeypatch.delenv('ADMIN_BOOTSTRAP_PASSWORD', raising=False)
    from app import create_app
    from models import db, User
    application = create_app('testing', dict(FAST))
    with application.app_context():
        assert User.query.count() == 0
        db.session.remove()
        db.drop_all()


def test_no_hardcoded_password_and_no_public_test_page():
    source = open(os.path.join(BACKEND, 'app.py'), encoding='utf8').read()
    assert "set_password('" not in source and 'set_password("' not in source
    assert ('Adm' + 'in@2') not in source
    assert not os.path.exists(os.path.join(REPO, 'frontend', 'public', 'api-test.html'))


def test_account_locks_after_five_failures(client):
    for _ in range(5):
        assert login(client, password='wrong-password-1').status_code == 401
    res = login(client)
    assert res.status_code == 429
    assert res.get_json()['code'] == 'ACCOUNT_LOCKED'


def test_token_carries_church_role_and_version(app, client):
    from flask_jwt_extended import decode_token
    data = tokens(client)
    with app.app_context():
        claims = decode_token(data['access_token'])
    assert claims['church_id'] is not None
    assert claims['role'] == 'admin' and claims['tv'] == 0


def test_refresh_rotates_and_the_old_token_is_dead(client):
    first = tokens(client)
    res = client.post(REFRESH, headers=bearer(first['refresh_token']))
    assert res.status_code == 200
    second = res.get_json()
    assert second['refresh_token'] != first['refresh_token']
    assert client.post(REFRESH, headers=bearer(first['refresh_token'])).status_code == 401
    assert client.get(ME, headers=bearer(second['access_token'])).status_code == 200


def test_logout_revokes_both_tokens(client):
    data = tokens(client)
    res = client.post('/api/auth/logout', headers=bearer(data['access_token']),
                      json={'refresh_token': data['refresh_token']})
    assert res.status_code == 200
    after = client.get(ME, headers=bearer(data['access_token']))
    assert after.status_code == 401 and after.get_json()['code'] == 'TOKEN_REVOKED'
    assert client.post(REFRESH, headers=bearer(data['refresh_token'])).status_code == 401


def test_change_password_ends_every_old_session(client):
    old = tokens(client)
    weak = client.post(CHANGE, headers=bearer(old['access_token']),
                       json={'current_password': ADMIN_PASSWORD, 'new_password': 'short1'})
    assert weak.status_code == 400
    res = client.post(CHANGE, headers=bearer(old['access_token']),
                      json={'current_password': ADMIN_PASSWORD,
                            'new_password': 'Fresh-Pass-13579'})
    assert res.status_code == 200, res.get_json()
    new = res.get_json()
    assert client.get(ME, headers=bearer(old['access_token'])).status_code == 401
    assert client.post(REFRESH, headers=bearer(old['refresh_token'])).status_code == 401
    assert client.get(ME, headers=bearer(new['access_token'])).status_code == 200
    assert login(client).status_code == 401
    assert login(client, password='Fresh-Pass-13579').status_code == 200


def test_deactivated_user_is_cut_off_at_once(app, client):
    from models import db, User
    data = tokens(client)
    with app.app_context():
        User.query.filter_by(username='admin').first().is_active = False
        db.session.commit()
    assert client.get(ME, headers=bearer(data['access_token'])).status_code == 401


def test_cors_allows_named_origins_only(client):
    good = client.get('/api/health', headers={'Origin': 'https://churchos-app.vercel.app'})
    assert good.headers.get('Access-Control-Allow-Origin') == 'https://churchos-app.vercel.app'
    bad = client.get('/api/health', headers={'Origin': 'https://evil.example'})
    assert bad.headers.get('Access-Control-Allow-Origin') is None


def test_security_headers_are_set(client):
    headers = client.get('/api/health').headers
    assert headers['X-Content-Type-Options'] == 'nosniff'
    assert headers['X-Frame-Options'] == 'DENY'
    assert 'no-store' in headers['Cache-Control']
    assert 'max-age' in headers['Strict-Transport-Security']


def test_login_is_rate_limited(monkeypatch):
    monkeypatch.setenv('ADMIN_BOOTSTRAP_PASSWORD', ADMIN_PASSWORD)
    from app import create_app
    from extensions import limiter
    from models import db
    application = create_app('testing', {'RATELIMIT_ENABLED': True, 'BCRYPT_LOG_ROUNDS': 4})
    try:
        limiter.reset()
    except Exception:
        pass
    client = application.test_client()
    codes = [login(client, username='nobody', password='wrong-password-1').status_code
             for _ in range(11)]
    with application.app_context():
        db.session.remove()
        db.drop_all()
    assert codes[:10] == [401] * 10
    assert codes[10] == 429


def test_schema_sync_adds_a_missing_column(app):
    from sqlalchemy import inspect, text
    from models import db
    from schema_sync import sync_schema

    def columns():
        return {c['name'] for c in inspect(db.engine).get_columns('users')}

    with app.app_context():
        db.session.execute(text('ALTER TABLE users DROP COLUMN token_version'))
        db.session.commit()
        assert 'token_version' not in columns()
        assert sync_schema(db) == ['users.token_version']
        assert 'token_version' in columns()
