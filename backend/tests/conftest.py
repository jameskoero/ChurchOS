import os
import sys

# config.py reads these at import time, so they are set before any import.
os.environ.setdefault('SECRET_KEY', 'ci-only-secret-key-0123456789abcdef')
os.environ.setdefault('JWT_SECRET_KEY', 'ci-only-jwt-key-0123456789abcdef')
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

import pytest  # noqa: E402

ADMIN_PASSWORD = 'Bootstrap-Pass-2468'
FAST = {'RATELIMIT_ENABLED': False, 'BCRYPT_LOG_ROUNDS': 4}


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setenv('ADMIN_BOOTSTRAP_PASSWORD', ADMIN_PASSWORD)
    from app import create_app
    from models import db
    application = create_app('testing', dict(FAST))
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
