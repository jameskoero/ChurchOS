from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token, decode_token,
    jwt_required, get_jwt_identity, get_jwt
)

from extensions import limiter
from models import db, bcrypt, User, TokenBlocklist

auth_bp = Blueprint('auth', __name__)

MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 15
MIN_PASSWORD = 10
MAX_PASSWORD_BYTES = 72   # bcrypt reads no further than this

_dummy_hash = None


def _json():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _text(value):
    return value if isinstance(value, str) else ''


def _burn_time(password):
    """Spend the same time as a real check so unknown users look the same."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = bcrypt.generate_password_hash('churchos-placeholder').decode('utf-8')
    try:
        bcrypt.check_password_hash(_dummy_hash, password)
    except ValueError:
        pass


def _password_ok(user, password):
    try:
        return bool(user.check_password(password))
    except ValueError:
        return False


def _claims(user):
    return {
        'role': user.role,
        'username': user.username or '',
        'church_id': user.church_id,
        'owner': bool(user.is_platform_owner),
        'tv': int(user.token_version or 0),
    }


def _issue(user):
    access = create_access_token(identity=str(user.id), additional_claims=_claims(user))
    refresh = create_refresh_token(
        identity=str(user.id),
        additional_claims={'tv': int(user.token_version or 0)})
    return access, refresh


def _revoke(payload):
    """Put one token on the blocklist. The caller commits."""
    jti = payload.get('jti')
    if not jti or TokenBlocklist.query.filter_by(jti=jti).first() is not None:
        return
    sub = str(payload.get('sub', ''))
    exp = payload.get('exp')
    db.session.add(TokenBlocklist(
        jti=jti,
        token_type=str(payload.get('type', 'access'))[:10],
        user_id=int(sub) if sub.isdigit() else None,
        expires_at=datetime.utcfromtimestamp(exp) if exp else None,
    ))


def password_problem(user, password):
    """Return a message when the password is not acceptable, else None."""
    if len(password) < MIN_PASSWORD:
        return f'Password must be at least {MIN_PASSWORD} characters'
    if len(password.encode('utf-8')) > MAX_PASSWORD_BYTES:
        return 'Password is too long'
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        return 'Password must contain letters and numbers'
    lowered = password.lower()
    for part in (user.username, (user.email or '').split('@')[0]):
        if part and len(part) >= 4 and part.lower() in lowered:
            return 'Password must not contain your username or email'
    return None


@auth_bp.route('/login', methods=['POST'])
@limiter.limit('10 per minute')
def login():
    data = _json()
    if data is None:
        return jsonify({'error': 'No data provided'}), 400

    username = _text(data.get('username')).strip()
    password = _text(data.get('password'))
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    user = User.query.filter(
        (User.username == username) | (User.email == username)
    ).first()
    now = datetime.utcnow()

    if user is None:
        _burn_time(password)
        return jsonify({'error': 'Invalid credentials'}), 401

    if user.locked_until and user.locked_until > now:
        return jsonify({'error': 'Too many failed attempts. Try again in a few minutes.',
                        'code': 'ACCOUNT_LOCKED'}), 429

    if not _password_ok(user, password):
        user.failed_logins = int(user.failed_logins or 0) + 1
        if user.failed_logins >= MAX_FAILED_LOGINS:
            user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
            user.failed_logins = 0
        db.session.commit()
        return jsonify({'error': 'Invalid credentials'}), 401

    if not user.is_active:
        return jsonify({'error': 'Account is deactivated. Contact administrator.'}), 403

    user.failed_logins = 0
    user.locked_until = None
    user.last_login = now
    db.session.commit()

    access_token, refresh_token = _issue(user)
    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user.to_dict()
    }), 200


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Rotate: the refresh token used here is spent and a new pair is issued."""
    user = db.session.get(User, int(get_jwt_identity()))
    if not user or not user.is_active:
        return jsonify({'error': 'User not found or inactive'}), 401
    _revoke(get_jwt())
    access_token, refresh_token = _issue(user)
    db.session.commit()
    return jsonify({'access_token': access_token, 'refresh_token': refresh_token}), 200


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Revoke this access token and, when sent, the matching refresh token."""
    _revoke(get_jwt())
    data = _json() or {}
    refresh_token = _text(data.get('refresh_token'))
    if refresh_token:
        try:
            payload = decode_token(refresh_token)
            if payload.get('type') == 'refresh' and str(payload.get('sub')) == str(get_jwt_identity()):
                _revoke(payload)
        except Exception:
            pass
    db.session.commit()
    return jsonify({'message': 'Logged out'}), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    user = db.session.get(User, int(get_jwt_identity()))
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user.to_dict()), 200


@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
@limiter.limit('5 per minute')
def change_password():
    user = db.session.get(User, int(get_jwt_identity()))
    data = _json()
    if not user or data is None:
        return jsonify({'error': 'No data provided'}), 400

    current = _text(data.get('current_password'))
    new_password = _text(data.get('new_password'))
    if not _password_ok(user, current):
        return jsonify({'error': 'Current password is incorrect'}), 400
    if new_password == current:
        return jsonify({'error': 'New password must be different'}), 400
    problem = password_problem(user, new_password)
    if problem:
        return jsonify({'error': problem}), 400

    user.set_password(new_password)
    # Every token issued before this moment stops working.
    user.token_version = int(user.token_version or 0) + 1
    db.session.commit()

    access_token, refresh_token = _issue(user)
    return jsonify({
        'message': 'Password updated successfully',
        'access_token': access_token,
        'refresh_token': refresh_token
    }), 200
