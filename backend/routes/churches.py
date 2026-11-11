from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt

from models import (db, Church, User, Member, Attendance, Finance, Event,
                    KENYAN_COUNTIES, DENOMINATIONS,
                    CHURCH_SIZES, SUBSCRIPTION_PLANS, PLAN_LIMITS)
from routes.auth import password_problem
from tenancy import current_church_id, is_owner

churches_bp = Blueprint('churches', __name__)

PROFILE_FIELDS = ['name', 'county', 'sub_county', 'denomination', 'size',
                  'paybill', 'till_number', 'phone', 'email', 'address',
                  'member_prefix']
OWNER_FIELDS = ['subscription_plan', 'is_active']


def _json():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _is_admin():
    return get_jwt().get('role') == 'admin'


def _visible(cid):
    """A church the caller may see: any for the owner, else only their own."""
    if not is_owner() and cid != current_church_id():
        return None
    return db.session.get(Church, cid)


@churches_bp.route('/constants', methods=['GET'])
def get_constants():
    return jsonify({
        'counties': KENYAN_COUNTIES,
        'denominations': DENOMINATIONS,
        'sizes': CHURCH_SIZES,
        'plans': SUBSCRIPTION_PLANS,
        'plan_limits': PLAN_LIMITS
    }), 200


@churches_bp.route('/', methods=['GET'])
@jwt_required()
def list_churches():
    if not _is_admin():
        return jsonify({'error': 'Admin access required'}), 403
    query = Church.query
    if not is_owner():
        query = query.filter(Church.id == current_church_id())
    churches = query.order_by(Church.name).all()
    return jsonify({'churches': [c.to_dict() for c in churches],
                    'total': len(churches)}), 200


@churches_bp.route('/', methods=['POST'])
@jwt_required()
def create_church():
    """Platform owner only. May create the church's first admin in the same call."""
    if not is_owner():
        return jsonify({'error': 'Only the platform owner can register a church'}), 403
    data = _json()
    if not data or not isinstance(data.get('name'), str) or not data['name'].strip():
        return jsonify({'error': 'Church name required'}), 400

    church = Church(
        name=data['name'].strip(), county=data.get('county'),
        sub_county=data.get('sub_county'),
        denomination=data.get('denomination'),
        size=data.get('size'), paybill=data.get('paybill'),
        till_number=data.get('till_number'), phone=data.get('phone'),
        email=data.get('email'), address=data.get('address'),
        member_prefix=data.get('member_prefix', 'CHR'),
        subscription_plan='trial',
        trial_ends_at=datetime.utcnow() + timedelta(days=30),
        is_active=True)
    db.session.add(church)
    db.session.flush()

    admin = None
    if data.get('admin_email') or data.get('admin_username') or data.get('admin_password'):
        username = str(data.get('admin_username') or '').strip()
        email = str(data.get('admin_email') or '').strip().lower()
        password = data.get('admin_password') if isinstance(data.get('admin_password'), str) else ''
        if not username or not email or not password:
            db.session.rollback()
            return jsonify({'error': 'admin_username, admin_email and admin_password are all required'}), 400
        if User.query.filter((User.username == username) | (User.email == email)).first():
            db.session.rollback()
            return jsonify({'error': 'Admin username or email already in use'}), 409
        admin = User(church_id=church.id, username=username, email=email,
                     full_name=str(data.get('admin_full_name') or '').strip(),
                     role='admin', is_active=True)
        problem = password_problem(admin, password)
        if problem:
            db.session.rollback()
            return jsonify({'error': problem}), 400
        admin.set_password(password)
        db.session.add(admin)

    db.session.commit()
    body = {'message': 'Church registered', 'church': church.to_dict()}
    if admin is not None:
        body['admin'] = admin.to_dict()
    return jsonify(body), 201


@churches_bp.route('/<int:cid>', methods=['GET'])
@jwt_required()
def get_church(cid):
    church = _visible(cid)
    if church is None:
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404
    return jsonify(church.to_dict()), 200


@churches_bp.route('/<int:cid>', methods=['PUT'])
@jwt_required()
def update_church(cid):
    if not _is_admin():
        return jsonify({'error': 'Admin access required'}), 403
    church = _visible(cid)
    if church is None:
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404
    data = _json()
    if data is None:
        return jsonify({'error': 'No data provided'}), 400
    allowed = PROFILE_FIELDS + (OWNER_FIELDS if is_owner() else [])
    for field in allowed:
        if field in data:
            setattr(church, field, data[field])
    church.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'message': 'Church updated',
                    'church': church.to_dict()}), 200


@churches_bp.route('/<int:cid>', methods=['DELETE'])
@jwt_required()
def delete_church(cid):
    """Platform owner only, and only for a church that holds no data."""
    if not is_owner():
        return jsonify({'error': 'Only the platform owner can delete a church'}), 403
    church = db.session.get(Church, cid)
    if church is None:
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404
    if cid == current_church_id():
        return jsonify({'error': 'You cannot delete your own church'}), 400
    for model in (User, Member, Attendance, Finance, Event):
        if model.query.filter(model.church_id == cid).first() is not None:
            return jsonify({'error': 'This church has data. Deactivate it instead of deleting it.'}), 409
    db.session.delete(church)
    db.session.commit()
    return jsonify({'message': 'Church deleted'}), 200
