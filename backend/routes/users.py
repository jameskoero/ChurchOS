from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError

from models import db, User, ROLES
from routes.auth import password_problem
from tenancy import current_church_id, scoped, owned_or_404, roles_required, is_owner

users_bp = Blueprint('users', __name__)


def _json():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _text(value):
    return value.strip() if isinstance(value, str) else ''


def _other_active_admins(user):
    return scoped(User).filter(
        User.role == 'admin', User.is_active.is_(True), User.id != user.id).count()


def _protected(user):
    """Only the platform owner may change a platform owner."""
    return bool(user.is_platform_owner) and not is_owner()


@users_bp.route('/', methods=['GET'])
@jwt_required()
@roles_required('admin')
def get_users():
    users = scoped(User).order_by(User.created_at.desc()).all()
    return jsonify([u.to_dict() for u in users]), 200


@users_bp.route('/<int:user_id>', methods=['GET'])
@jwt_required()
@roles_required('admin')
def get_user(user_id):
    return jsonify(owned_or_404(User, user_id).to_dict()), 200


@users_bp.route('/', methods=['POST'])
@jwt_required()
@roles_required('admin')
def create_user():
    data = _json()
    if data is None:
        return jsonify({'error': 'No data provided'}), 400

    username = _text(data.get('username'))
    email = _text(data.get('email')).lower()
    password = data.get('password') if isinstance(data.get('password'), str) else ''
    role = data.get('role')
    for field, value in (('username', username), ('email', email),
                         ('password', password), ('role', role)):
        if not value:
            return jsonify({'error': f'{field} is required'}), 400
    if role not in ROLES:
        return jsonify({'error': f'Invalid role. Must be one of: {", ".join(ROLES)}'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already in use'}), 409

    user = User(
        church_id=current_church_id(),
        username=username,
        email=email,
        full_name=_text(data.get('full_name')),
        role=role,
        is_active=bool(data.get('is_active', True)),
    )
    problem = password_problem(user, password)
    if problem:
        return jsonify({'error': problem}), 400
    user.set_password(password)

    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@users_bp.route('/<int:user_id>', methods=['PUT'])
@jwt_required()
@roles_required('admin')
def update_user(user_id):
    user = owned_or_404(User, user_id)
    data = _json()
    if data is None:
        return jsonify({'error': 'No data provided'}), 400
    if _protected(user):
        return jsonify({'error': 'This account can only be changed by the platform owner'}), 403

    is_self = user.id == int(get_jwt_identity())
    end_sessions = False

    if 'full_name' in data:
        user.full_name = _text(data['full_name'])
    if 'email' in data:
        email = _text(data['email']).lower()
        if not email:
            return jsonify({'error': 'email is required'}), 400
        existing = User.query.filter_by(email=email).first()
        if existing and existing.id != user.id:
            return jsonify({'error': 'Email already in use'}), 409
        user.email = email
    if 'role' in data and data['role'] != user.role:
        if data['role'] not in ROLES:
            return jsonify({'error': 'Invalid role'}), 400
        if is_self:
            return jsonify({'error': 'You cannot change your own role'}), 400
        if user.role == 'admin' and user.is_active and _other_active_admins(user) == 0:
            return jsonify({'error': 'A church must keep at least one active admin'}), 400
        user.role = data['role']
        end_sessions = True
    if 'is_active' in data and bool(data['is_active']) != bool(user.is_active):
        if is_self:
            return jsonify({'error': 'You cannot deactivate your own account'}), 400
        if user.role == 'admin' and user.is_active and _other_active_admins(user) == 0:
            return jsonify({'error': 'A church must keep at least one active admin'}), 400
        user.is_active = bool(data['is_active'])
        end_sessions = True
    if data.get('password'):
        if not isinstance(data['password'], str):
            return jsonify({'error': 'Invalid password'}), 400
        problem = password_problem(user, data['password'])
        if problem:
            return jsonify({'error': problem}), 400
        user.set_password(data['password'])
        end_sessions = not is_self

    if end_sessions:
        # The user's old tokens carry the old role; make them stop working.
        user.token_version = int(user.token_version or 0) + 1
    db.session.commit()
    return jsonify(user.to_dict()), 200


@users_bp.route('/<int:user_id>', methods=['DELETE'])
@jwt_required()
@roles_required('admin')
def delete_user(user_id):
    if user_id == int(get_jwt_identity()):
        return jsonify({'error': 'Cannot delete your own account'}), 400
    user = owned_or_404(User, user_id)
    if _protected(user):
        return jsonify({'error': 'This account can only be changed by the platform owner'}), 403
    if user.role == 'admin' and user.is_active and _other_active_admins(user) == 0:
        return jsonify({'error': 'A church must keep at least one active admin'}), 400

    username = user.username
    db.session.delete(user)
    try:
        db.session.commit()
    except IntegrityError:
        # The user recorded data. Keep the history and switch the account off.
        db.session.rollback()
        user = owned_or_404(User, user_id)
        user.is_active = False
        user.token_version = int(user.token_version or 0) + 1
        db.session.commit()
        return jsonify({'message': f'User {username} has records and was deactivated instead'}), 200
    return jsonify({'message': f'User {username} deleted'}), 200


@users_bp.route('/roles', methods=['GET'])
@jwt_required()
def get_roles():
    return jsonify(ROLES), 200
