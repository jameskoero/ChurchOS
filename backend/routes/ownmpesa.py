"""A church connects its OWN Safaricom Paybill or Till. Only the church's admin can change it, and the keys
are write-only: once saved they are never shown again, by anyone, including the platform owner."""
import re
import secrets
from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import limiter
from ledger import audit
from models import db, ChurchMpesa
from services import churchmpesa, mpesa, vault
from tenancy import current_church_id, roles_required

ownmpesa_bp = Blueprint('ownmpesa', __name__)

SHORTCODE = re.compile(r'^\d{5,7}$')
SECRET_FIELDS = (('consumer_key', 'consumer_key_enc', 'Consumer Key'),
                 ('consumer_secret', 'consumer_secret_enc', 'Consumer Secret'),
                 ('passkey', 'passkey_enc', 'Passkey'))


def _json():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _row():
    return ChurchMpesa.query.filter_by(church_id=current_church_id()).first()


def _view(row):
    if row is None:
        return None
    return {'shortcode': row.shortcode, 'env': row.env, 'enabled': bool(row.enabled),
            'verified_at': row.verified_at.isoformat() if row.verified_at else None,
            'c2b_registered_at': row.c2b_registered_at.isoformat() if row.c2b_registered_at else None,
            'keys_saved': bool(row.consumer_key_enc and row.consumer_secret_enc and row.passkey_enc)}


def _unready():
    missing = [] if vault.ready() else ['MPESA_VAULT_KEY']
    missing += [] if churchmpesa.server_address() else ['MPESA_CALLBACK_URL']
    return missing


@ownmpesa_bp.route('/own', methods=['GET'])
@jwt_required()
@roles_required('admin', 'treasurer')
def status():
    return jsonify({'missing': _unready(), 'problems': churchmpesa.server_problems() if churchmpesa.server_address() else [],
                    'own': _view(_row())}), 200


@ownmpesa_bp.route('/own', methods=['PUT'])
@jwt_required()
@roles_required('admin')
@limiter.limit('10 per minute')
def save():
    if not vault.ready():
        return jsonify({'error': 'The server cannot keep keys safely yet', 'code': 'VAULT_NOT_READY',
                        'missing': ['MPESA_VAULT_KEY']}), 503
    data = _json()
    row = _row()
    shortcode = str(data.get('shortcode') or (row.shortcode if row else '')).strip()
    env = str(data.get('env') or (row.env if row else 'sandbox')).strip().lower()
    if not SHORTCODE.match(shortcode):
        return jsonify({'error': 'The Paybill or Till number must be 5 to 7 digits'}), 400
    if env not in ('sandbox', 'live'):
        return jsonify({'error': 'Choose sandbox (testing) or live'}), 400
    values = {}
    for field, column, label in SECRET_FIELDS:
        text = str(data.get(field) or '').strip()
        if text:
            if not 8 <= len(text) <= 300 or re.search(r'\s', text):
                return jsonify({'error': '%s does not look right. Copy it again from the Safaricom portal.' % label}), 400
            values[column] = text
        elif row is None or not getattr(row, column):
            return jsonify({'error': '%s is required' % label}), 400
    if env == 'live':
        clash = ChurchMpesa.query.filter(ChurchMpesa.shortcode == shortcode, ChurchMpesa.env == 'live',
                                         ChurchMpesa.church_id != current_church_id()).first()
        if clash is not None:
            return jsonify({'error': 'That Paybill or Till is already connected to another church'}), 409
    created = row is None
    if created:
        row = ChurchMpesa(church_id=current_church_id(), callback_token=secrets.token_hex(24))
        db.session.add(row)
    changed_target = created or row.shortcode != shortcode or row.env != env
    row.shortcode, row.env = shortcode, env
    for column, text in values.items():
        setattr(row, column, vault.encrypt(text))
    # Any change has to be tested again before it is used.
    row.enabled, row.verified_at = False, None
    if changed_target:
        row.c2b_registered_at = None
    row.updated_by, row.updated_at = int(get_jwt_identity()), datetime.utcnow()
    db.session.flush()
    audit('payments.own_saved', 'church_mpesa', row.id,
          after={'shortcode': shortcode, 'env': env, 'keys_changed': sorted(values)})
    db.session.commit()
    return jsonify({'own': _view(row)}), 200


@ownmpesa_bp.route('/own/test', methods=['POST'])
@jwt_required()
@roles_required('admin')
@limiter.limit('6 per minute')
def test():
    row = _row()
    if row is None:
        return jsonify({'error': 'Save your keys first'}), 400
    try:
        cfg = churchmpesa.cfg_for(row)
        mpesa._tokens.pop(cfg['MPESA_CONSUMER_KEY'], None)
        mpesa.access_token(cfg)
    except (vault.VaultError, mpesa.NotConfigured) as err:
        return jsonify({'ok': False, 'error': str(err)}), 503
    except mpesa.MpesaError as err:
        return jsonify({'ok': False, 'error': 'Safaricom did not accept these keys (%s)' % err}), 502
    row.verified_at = datetime.utcnow()
    audit('payments.own_verified', 'church_mpesa', row.id, after={'shortcode': row.shortcode, 'env': row.env})
    db.session.commit()
    return jsonify({'ok': True, 'message': 'Safaricom accepted your keys.', 'own': _view(row)}), 200


@ownmpesa_bp.route('/own/register-c2b', methods=['POST'])
@jwt_required()
@roles_required('admin')
@limiter.limit('4 per minute')
def register():
    row = _row()
    if row is None or row.verified_at is None:
        return jsonify({'error': 'Test your keys first'}), 400
    if churchmpesa.server_problems():
        return jsonify({'error': churchmpesa.server_problems()[0]}), 503
    if row.c2b_registered_at and row.env == 'live':
        return jsonify({'error': 'Already registered. In live mode Safaricom changes these addresses only through '
                                 'its portal.', 'code': 'ALREADY_REGISTERED'}), 409
    try:
        churchmpesa.register_c2b(row)
    except (vault.VaultError, mpesa.NotConfigured) as err:
        return jsonify({'ok': False, 'error': str(err)}), 503
    except mpesa.MpesaError as err:
        return jsonify({'ok': False, 'error': str(err)}), 502
    row.c2b_registered_at = datetime.utcnow()
    audit('payments.own_registered', 'church_mpesa', row.id, after={'shortcode': row.shortcode})
    db.session.commit()
    return jsonify({'ok': True, 'own': _view(row)}), 200


@ownmpesa_bp.route('/own/enable', methods=['POST'])
@jwt_required()
@roles_required('admin')
def enable():
    row = _row()
    wanted = _json().get('enabled')
    if row is None or not isinstance(wanted, bool):
        return jsonify({'error': 'Save your keys first'}), 400
    if wanted and (row.verified_at is None or not vault.ready()):
        return jsonify({'error': 'Test your keys first'}), 400
    row.enabled = wanted
    audit('payments.own_enabled' if wanted else 'payments.own_disabled', 'church_mpesa', row.id,
          after={'shortcode': row.shortcode})
    db.session.commit()
    return jsonify({'own': _view(row)}), 200


@ownmpesa_bp.route('/own', methods=['DELETE'])
@jwt_required()
@roles_required('admin')
def remove():
    row = _row()
    if row is None:
        return jsonify({'own': None}), 200
    audit('payments.own_removed', 'church_mpesa', row.id, after={'shortcode': row.shortcode})
    db.session.delete(row)
    db.session.commit()
    return jsonify({'own': None}), 200
