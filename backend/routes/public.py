"""Asking for ChurchOS, and the platform owner's review of those requests.

Nothing here creates a church by itself. A visitor sends a request; the platform owner reads it,
confirms with the contact by phone, and only then approves. Approving makes the church (30-day trial);
the owner then adds the church's first admin from the Churches page."""
import re
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import limiter
from ledger import audit
from models import db, Church, ChurchRequest, KENYAN_COUNTIES
from tenancy import is_owner

public_bp = Blueprint('public', __name__)

TERMS_VERSION = '2026-11'
MAX_PENDING = 200
PHONE = re.compile(r'^(?:\+?254|0)([17]\d{8})$')
EMAIL = re.compile(r'^[^@\s]{1,64}@[^@\s]{1,120}\.[^@\s]{2,}$')


def _clean(value, limit):
    return re.sub(r'\s+', ' ', str(value or '')).strip()[:limit]


def _phone(raw):
    found = PHONE.match(re.sub(r'[\s\-()]', '', str(raw or '')))
    return '+254' + found.group(1) if found else None


@public_bp.route('/request', methods=['POST'])
@limiter.limit('5 per hour')
def ask_for_churchos():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Send the form as JSON'}), 400
    # A hidden field real people never fill in. Bots do. Answer as if it worked.
    if _clean(data.get('website'), 50):
        return jsonify({'message': 'Request received'}), 201

    church_name = _clean(data.get('church_name'), 120)
    contact_name = _clean(data.get('contact_name'), 80)
    phone = _phone(data.get('phone'))
    email = _clean(data.get('email'), 120).lower()
    county = _clean(data.get('county'), 80)
    denomination = _clean(data.get('denomination'), 160)
    note = _clean(data.get('note'), 500)
    if len(church_name) < 3:
        return jsonify({'error': 'Type the full name of the church (at least 3 letters)'}), 400
    if len(contact_name) < 2:
        return jsonify({'error': 'Type your name'}), 400
    if phone is None:
        return jsonify({'error': 'Type a Kenyan mobile number, for example 0712 345 678'}), 400
    if email and not EMAIL.match(email):
        return jsonify({'error': 'That email address does not look right. Leave it empty if you prefer.'}), 400
    if county and county not in KENYAN_COUNTIES:
        return jsonify({'error': 'Choose your county from the list'}), 400
    if data.get('agree') is not True:
        return jsonify({'error': 'Please tick the box to accept the Terms and Privacy Policy'}), 400
    try:
        members = int(data.get('members_estimate') or 0)
    except (TypeError, ValueError):
        return jsonify({'error': 'Members must be a number'}), 400
    members = max(0, min(members, 1000000))

    # The same person pressing twice must not create two requests.
    same = ChurchRequest.query.filter_by(status='pending', phone=phone).filter(
        db.func.lower(ChurchRequest.church_name) == church_name.lower()).first()
    if same is not None:
        return jsonify({'message': 'Request received'}), 200
    if ChurchRequest.query.filter_by(status='pending').count() >= MAX_PENDING:
        return jsonify({'error': 'We are not taking new requests right now. Try again later.'}), 503

    db.session.add(ChurchRequest(
        church_name=church_name, contact_name=contact_name, phone=phone, email=email or None,
        county=county or None, denomination_text=denomination or None, members_estimate=members or None,
        note=note or None, status='pending', accepted_terms_at=datetime.utcnow(),
        terms_version=TERMS_VERSION))
    db.session.commit()
    return jsonify({'message': 'Request received'}), 201


def _owner_only():
    if not is_owner():
        return jsonify({'error': 'Only the platform owner can do this', 'code': 'FORBIDDEN'}), 403
    return None


@public_bp.route('/requests', methods=['GET'])
@jwt_required()
def list_requests():
    blocked = _owner_only()
    if blocked:
        return blocked
    status = request.args.get('status', 'pending')
    if status not in ('pending', 'approved', 'declined'):
        status = 'pending'
    rows = ChurchRequest.query.filter_by(status=status).order_by(ChurchRequest.id.desc()).limit(100).all()
    return jsonify({'requests': [r.to_dict() for r in rows], 'status': status}), 200


@public_bp.route('/requests/<int:rid>', methods=['PUT'])
@jwt_required()
def decide(rid):
    blocked = _owner_only()
    if blocked:
        return blocked
    row = db.session.get(ChurchRequest, rid)
    if row is None:
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404
    if row.status != 'pending':
        return jsonify({'error': 'This request was already %s' % row.status}), 409
    data = request.get_json(silent=True) or {}
    action = data.get('action')
    if action not in ('approve', 'decline'):
        return jsonify({'error': 'action must be approve or decline'}), 400
    row.decision_note = _clean(data.get('note'), 300) or None
    row.decided_by = int(get_jwt_identity())
    row.decided_at = datetime.utcnow()
    if action == 'decline':
        row.status = 'declined'
        audit('request.decline', 'church_request', row.id, after={'church': row.church_name})
        db.session.commit()
        return jsonify({'request': row.to_dict()}), 200

    church = Church(name=row.church_name, county=row.county, phone=row.phone, email=row.email,
                    member_prefix='CHR', subscription_plan='trial',
                    trial_ends_at=datetime.utcnow() + timedelta(days=30), is_active=True)
    db.session.add(church)
    db.session.flush()
    if row.denomination_text and len(row.denomination_text) >= 3:
        from routes.churches import _link_denomination
        problem = _link_denomination(church, {'denomination_other': row.denomination_text})
        if problem is not None:
            # A rejected denomination name must not block the church. The owner fixes it later.
            church.denomination_id, church.denomination = None, None
    row.status = 'approved'
    row.church_id = church.id
    audit('request.approve', 'church_request', row.id, after={'church_id': church.id})
    db.session.commit()
    return jsonify({'request': row.to_dict(), 'church': church.to_dict(),
                    'next': 'Open Churches and tap Add first admin to give the senior pastor a login.'}), 200
