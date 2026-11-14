"""Sign-in by SMS code: a second step AFTER the password. It ships switched off.

Why it can be trusted, and where it cannot:
  * The password is still required first. A code is only ever sent after the password is right.
  * A code is 6 digits, lasts 5 minutes, works once, and allows 5 tries. Wrong codes also count toward
    the normal account lock. Codes are stored only as keyed hashes.
  * Sends are capped (3 per 15 minutes per person, 500 per day overall) so nobody can run up SMS costs.
  * SIM swap: someone who swaps a SIM AND knows the password can still pass this step. To limit the damage,
    changing the sign-in phone takes 24 hours to apply, the OLD number is told at once, the change is written
    in the church's activity log, and an admin can reset a person's SMS sign-in.
  * It switches on only when the platform owner turns it on AND live (not sandbox) SMS is set up.
  * Emergency exit: set SMS_LOGIN_FORCE_OFF=1 on the server and everyone signs in by password alone."""
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from extensions import limiter
from ledger import audit
from models import db, LoginChallenge, PlatformSetting, User
from routes.auth import LOCK_MINUTES, MAX_FAILED_LOGINS, _issue, _password_ok
from routes.payments import normalize_phone
from services import sms
from tenancy import current_church_id, is_owner, roles_required

smslogin_bp = Blueprint('smslogin', __name__)

SETTING = 'security.sms_login'
CODE_MINUTES = 5
MAX_TRIES = 5
SENDS_PER_WINDOW = 3
WINDOW_MINUTES = 15
DAILY_CAP = 500
CHANGE_DELAY_HOURS = 24


def _json():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _forced_off():
    return os.environ.get('SMS_LOGIN_FORCE_OFF', '').strip().lower() in ('1', 'true', 'yes')


def _platform_on():
    if _forced_off():
        return False
    row = PlatformSetting.query.filter_by(key=SETTING).first()
    return bool(row and row.value == 'on')


def _sms_ready():
    config = sms.setup_status()
    return bool(config['configured'] and config['environment'] == 'live')


def _hint(phone):
    return ('+254 *** *** ' + phone[-3:]) if phone else ''


def _sha(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


def _code_hash(token_hash, code):
    key = str(current_app.config['SECRET_KEY']).encode()
    return hmac.new(key, ('%s:%s' % (token_hash, code)).encode(), hashlib.sha256).hexdigest()


def _unavailable():
    return jsonify({'error': 'SMS sign-in is on but SMS is not available right now. Ask your administrator.',
                    'code': 'SMS_UNAVAILABLE'}), 503


def _deliver(phone, text):
    results = sms.send_batch([phone], text)
    if not results or results[0].get('status') != 'sent':
        raise sms.SmsError('The code could not be sent')


def _fail(user, now):
    """A wrong password or code counts toward the same lock as a wrong password at sign-in."""
    user.failed_logins = int(user.failed_logins or 0) + 1
    if user.failed_logins >= MAX_FAILED_LOGINS:
        user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
        user.failed_logins = 0


def _promote_pending(user, now):
    """A changed phone becomes the sign-in phone once its waiting period has passed."""
    if user.pending_phone and user.pending_phone_at and now >= user.pending_phone_at + timedelta(hours=CHANGE_DELAY_HOURS):
        user.phone, user.pending_phone, user.pending_phone_at = user.pending_phone, None, None
        audit('auth.sms_phone_active', 'user', user.id, church_id=user.church_id, user_id=user.id)
        db.session.commit()


def _new_challenge(user, purpose, phone=None):
    """Make a code. Returns (token, row, code, None) or (None, None, None, error response)."""
    now = datetime.utcnow()
    LoginChallenge.query.filter(LoginChallenge.created_at < now - timedelta(hours=24)).delete(synchronize_session=False)
    recent = LoginChallenge.query.filter(LoginChallenge.user_id == user.id,
                                         LoginChallenge.created_at >= now - timedelta(minutes=WINDOW_MINUTES)).count()
    today = LoginChallenge.query.filter(LoginChallenge.created_at >= now - timedelta(hours=24)).count()
    if recent >= SENDS_PER_WINDOW or today >= DAILY_CAP:
        db.session.commit()
        return None, None, None, (jsonify({'error': 'Too many codes asked for. Wait 15 minutes and try again.',
                                           'code': 'CODE_LIMIT'}), 429)
    # An older code of the same kind stops working now; the row stays for 24 hours so sends can be counted.
    LoginChallenge.query.filter_by(user_id=user.id, purpose=purpose).update({'expires_at': now}, synchronize_session=False)
    token = secrets.token_urlsafe(32)
    token_hash = _sha(token)
    code = '%06d' % secrets.randbelow(1000000)
    row = LoginChallenge(token_hash=token_hash, user_id=user.id, purpose=purpose, phone=phone,
                         code_hash=_code_hash(token_hash, code), attempts=0,
                         expires_at=now + timedelta(minutes=CODE_MINUTES), created_at=now,
                         ip=(request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
                             or request.remote_addr or '')[:45])
    db.session.add(row)
    db.session.commit()
    return token, row, code, None


def _send_code(user, row, code, phone, purpose):
    try:
        _deliver(phone, 'ChurchOS code: %s. Valid %d minutes. Never share it.' % (code, CODE_MINUTES))
    except sms.SmsError:
        db.session.delete(row)
        db.session.commit()
        return _unavailable()
    audit('auth.sms_code_sent', 'user', user.id, church_id=user.church_id, user_id=user.id,
          after={'purpose': purpose})
    db.session.commit()
    return None


def second_step(user, now):
    """Called by sign-in after the password is right. None means: carry on and sign in."""
    if not _platform_on():
        return None
    _promote_pending(user, now)
    if not (user.sms_login and user.phone):
        return None
    if not _sms_ready():
        return _unavailable()
    token, row, code, error = _new_challenge(user, 'login')
    if error:
        return error
    failed = _send_code(user, row, code, user.phone, 'login')
    if failed:
        return failed
    return jsonify({'needs_code': True, 'challenge': token, 'phone_hint': _hint(user.phone),
                    'expires_in': CODE_MINUTES * 60}), 202


def _check(token, code, purpose, user_id=None):
    """Check a code. Returns (row, user, None) or (None, None, error response)."""
    status = 401 if purpose == 'login' else 400     # 401 on a signed-in call would make the app sign out
    invalid = (jsonify({'error': 'That code is wrong or has expired. Start again.', 'code': 'CODE_INVALID'}), status)
    token, code = str(token or ''), str(code or '').strip()
    row = LoginChallenge.query.filter_by(token_hash=_sha(token)).first() if token else None
    now = datetime.utcnow()
    if row is None or row.purpose != purpose or (user_id is not None and row.user_id != user_id):
        return None, None, invalid
    if row.expires_at < now:
        db.session.delete(row)
        db.session.commit()
        return None, None, invalid
    user = db.session.get(User, row.user_id)
    if user is None or not user.is_active:
        db.session.delete(row)
        db.session.commit()
        return None, None, invalid
    if user.locked_until and user.locked_until > now:
        return None, None, (jsonify({'error': 'Too many failed attempts. Try again in a few minutes.',
                                     'code': 'ACCOUNT_LOCKED'}), 429)
    if not re.fullmatch(r'\d{6}', code) or not hmac.compare_digest(row.code_hash, _code_hash(row.token_hash, code)):
        row.attempts = int(row.attempts or 0) + 1
        _fail(user, now)
        if row.attempts >= MAX_TRIES:
            db.session.delete(row)
        db.session.commit()
        return None, None, (jsonify({'error': 'That code is wrong.', 'code': 'CODE_WRONG'}), status)
    return row, user, None


@smslogin_bp.route('/login/verify', methods=['POST'])
@limiter.limit('10 per minute')
def verify_login():
    data = _json()
    row, user, bad = _check(data.get('challenge'), data.get('code'), 'login')
    if bad:
        return bad
    db.session.delete(row)
    user.failed_logins, user.locked_until, user.last_login = 0, None, datetime.utcnow()
    db.session.commit()
    access_token, refresh_token = _issue(user)
    return jsonify({'access_token': access_token, 'refresh_token': refresh_token, 'user': user.to_dict()}), 200


def _me():
    return db.session.get(User, int(get_jwt_identity()))


@smslogin_bp.route('/sms-login/status', methods=['GET'])
@jwt_required()
def status():
    user = _me()
    _promote_pending(user, datetime.utcnow())
    until = user.pending_phone_at + timedelta(hours=CHANGE_DELAY_HOURS) if user.pending_phone_at else None
    return jsonify({'platform_on': _platform_on(), 'sms_ready': _sms_ready(), 'forced_off': _forced_off(),
                    'mine': {'enabled': bool(user.sms_login and user.phone), 'phone_hint': _hint(user.phone),
                             'pending_phone_hint': _hint(user.pending_phone),
                             'pending_until': until.isoformat() if until else None}}), 200


@smslogin_bp.route('/sms-login/platform', methods=['PUT'])
@jwt_required()
def set_platform():
    if not is_owner():
        return jsonify({'error': 'Only the platform owner can do this', 'code': 'FORBIDDEN'}), 403
    enabled = _json().get('enabled')
    if not isinstance(enabled, bool):
        return jsonify({'error': 'Say on or off'}), 400
    if enabled and not _sms_ready():
        return jsonify({'error': 'Live SMS is not set up yet. SMS sign-in stays off until it is.',
                        'code': 'SMS_NOT_LIVE'}), 409
    row = PlatformSetting.query.filter_by(key=SETTING).first()
    if row is None:
        row = PlatformSetting(key=SETTING)
        db.session.add(row)
    row.value, row.updated_by, row.updated_at = ('on' if enabled else 'off'), int(get_jwt_identity()), datetime.utcnow()
    audit('auth.sms_login_platform', 'platform_setting', None, after={'enabled': enabled})
    db.session.commit()
    return jsonify({'platform_on': _platform_on()}), 200


def _password_gate(user, password):
    """Re-check the password before a security change. Returns an error response or None."""
    if _password_ok(user, str(password or '')):
        return None
    _fail(user, datetime.utcnow())
    db.session.commit()
    return jsonify({'error': 'Password is incorrect'}), 400


@smslogin_bp.route('/sms-login/start', methods=['POST'])
@jwt_required()
@limiter.limit('5 per minute')
def start():
    user = _me()
    if not _platform_on() or not _sms_ready():
        return jsonify({'error': 'SMS sign-in is not switched on yet', 'code': 'NOT_ON'}), 409
    data = _json()
    wrong = _password_gate(user, data.get('password'))
    if wrong:
        return wrong
    phone = normalize_phone(data.get('phone'))
    if not phone:
        return jsonify({'error': 'Type a Kenyan mobile number, for example 0712 345 678'}), 400
    phone = '+' + phone
    if user.sms_login and user.phone == phone:
        return jsonify({'error': 'That is already your sign-in phone'}), 400
    token, row, code, error = _new_challenge(user, 'enroll', phone)
    if error:
        return error
    failed = _send_code(user, row, code, phone, 'enroll')
    if failed:
        return failed
    return jsonify({'challenge': token, 'phone_hint': _hint(phone)}), 200


@smslogin_bp.route('/sms-login/confirm', methods=['POST'])
@jwt_required()
@limiter.limit('10 per minute')
def confirm():
    me = _me()
    data = _json()
    row, user, bad = _check(data.get('challenge'), data.get('code'), 'enroll', user_id=me.id)
    if bad:
        return bad
    phone, now = row.phone, datetime.utcnow()
    db.session.delete(row)
    if user.sms_login and user.phone and user.phone != phone:
        user.pending_phone, user.pending_phone_at = phone, now
        audit('auth.sms_phone_change', 'user', user.id, church_id=user.church_id, user_id=user.id,
              after={'to': _hint(phone), 'active_after_hours': CHANGE_DELAY_HOURS})
        db.session.commit()
        try:   # the old number is told at once, so a stolen phone change is noticed
            _deliver(user.phone, 'ChurchOS: a change of your sign-in phone to %s was asked for. It starts in %d '
                                 'hours. If this was not you, tell your administrator now.' % (_hint(phone), CHANGE_DELAY_HOURS))
        except sms.SmsError:
            pass
        return jsonify({'pending': True, 'active_after': (now + timedelta(hours=CHANGE_DELAY_HOURS)).isoformat()}), 200
    user.phone, user.sms_login, user.pending_phone, user.pending_phone_at = phone, True, None, None
    audit('auth.sms_login_on', 'user', user.id, church_id=user.church_id, user_id=user.id)
    db.session.commit()
    return jsonify({'enabled': True, 'phone_hint': _hint(phone)}), 200


@smslogin_bp.route('/sms-login/disable', methods=['POST'])
@jwt_required()
@limiter.limit('5 per minute')
def disable():
    user = _me()
    wrong = _password_gate(user, _json().get('password'))
    if wrong:
        return wrong
    user.phone, user.sms_login, user.pending_phone, user.pending_phone_at = None, False, None, None
    audit('auth.sms_login_off', 'user', user.id, church_id=user.church_id, user_id=user.id)
    db.session.commit()
    return jsonify({'enabled': False}), 200


@smslogin_bp.route('/sms-login/reset/<int:user_id>', methods=['POST'])
@jwt_required()
@roles_required('admin')
def reset(user_id):
    """Recovery: an admin clears someone's SMS sign-in so they can sign in with the password again."""
    target = db.session.get(User, user_id)
    if target is None or not (is_owner() or target.church_id == current_church_id()):
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404
    target.phone, target.sms_login, target.pending_phone, target.pending_phone_at = None, False, None, None
    target.token_version = int(target.token_version or 0) + 1
    LoginChallenge.query.filter_by(user_id=target.id).delete(synchronize_session=False)
    audit('auth.sms_login_reset', 'user', target.id, church_id=target.church_id, after={'by': int(get_jwt_identity())})
    db.session.commit()
    return jsonify({'enabled': False}), 200
