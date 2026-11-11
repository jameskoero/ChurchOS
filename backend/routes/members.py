from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from tenancy import (current_church_id, scoped, owned_or_404, tquery,
                     page_size, roles_required, can_see_money, FINANCE_READ,
                     redact_member)
from datetime import datetime
from ledger import audit
from models import db, Member, Attendance
from sqlalchemy import or_, func

members_bp = Blueprint('members', __name__)
CONSENT_VERSION = 'v1'

def require_role(*roles):
    from functools import wraps
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            claims = get_jwt()
            if claims.get('role') not in roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


@members_bp.route('/', methods=['GET'])
@jwt_required()
def get_members():
    page = request.args.get('page', 1, type=int)
    per_page = page_size(20)
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '')
    gender = request.args.get('gender', '')
    cell_group = request.args.get('cell_group', '')

    query = scoped(Member)

    if search:
        query = query.filter(or_(
            Member.first_name.ilike(f'%{search}%'),
            Member.last_name.ilike(f'%{search}%'),
            Member.member_id.ilike(f'%{search}%'),
            Member.phone.ilike(f'%{search}%'),
            Member.email.ilike(f'%{search}%')
        ))
    if status:
        query = query.filter_by(membership_status=status)
    if gender:
        query = query.filter_by(gender=gender)
    if cell_group:
        query = query.filter_by(cell_group=cell_group)

    total = query.count()
    members = query.order_by(Member.first_name).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'members': [redact_member(m.to_dict()) for m in members.items],
        'total': total,
        'pages': members.pages,
        'current_page': page,
        'per_page': per_page
    }), 200


@members_bp.route('/<int:member_id>', methods=['GET'])
@jwt_required()
def get_member(member_id):
    member = owned_or_404(Member, member_id)
    return jsonify(redact_member(member.to_dict(include_stats=can_see_money()))), 200


@members_bp.route('/', methods=['POST'])
@jwt_required()
@require_role('admin', 'pastor', 'secretary')
def create_member():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    required = ['first_name', 'last_name']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    from datetime import date
    member = Member(
        church_id=current_church_id(),
        member_id=Member.generate_member_id(),
        first_name=data['first_name'].strip(),
        last_name=data['last_name'].strip(),
        email=data.get('email', '').strip() or None,
        phone=data.get('phone', '').strip() or None,
        gender=data.get('gender'),
        address=data.get('address'),
        occupation=data.get('occupation'),
        marital_status=data.get('marital_status'),
        next_of_kin=data.get('next_of_kin'),
        next_of_kin_phone=data.get('next_of_kin_phone'),
        cell_group=data.get('cell_group'),
        notes=data.get('notes'),
        membership_status=data.get('membership_status', 'active'),
    )

    if data.get('date_of_birth'):
        try:
            member.date_of_birth = date.fromisoformat(data['date_of_birth'])
        except ValueError:
            pass

    if data.get('date_joined'):
        try:
            member.date_joined = date.fromisoformat(data['date_joined'])
        except ValueError:
            pass

    if data.get('baptism_date'):
        try:
            member.baptism_date = date.fromisoformat(data['baptism_date'])
        except ValueError:
            pass

    _apply_consent(member, data)
    db.session.add(member)
    db.session.commit()
    return jsonify(member.to_dict()), 201


@members_bp.route('/<int:member_id>', methods=['PUT'])
@jwt_required()
@require_role('admin', 'pastor', 'secretary')
def update_member(member_id):
    member = owned_or_404(Member, member_id)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'No data provided'}), 400
    if member.erased_at is not None:
        return jsonify({'error': 'This member\'s data was erased', 'code': 'ERASED'}), 410

    from datetime import date
    fields = ['first_name', 'last_name', 'email', 'phone', 'gender', 'address',
              'occupation', 'marital_status', 'next_of_kin', 'next_of_kin_phone',
              'cell_group', 'notes', 'membership_status']

    for field in fields:
        if field in data:
            setattr(member, field, data[field])

    for date_field in ['date_of_birth', 'date_joined', 'baptism_date']:
        if date_field in data and data[date_field]:
            try:
                setattr(member, date_field, date.fromisoformat(data[date_field]))
            except ValueError:
                pass

    _apply_consent(member, data)
    db.session.commit()
    return jsonify(member.to_dict()), 200


@members_bp.route('/<int:member_id>', methods=['DELETE'])
@jwt_required()
@require_role('admin')
def delete_member(member_id):
    member = owned_or_404(Member, member_id)
    if member.finance_records.first() is not None or member.attendance_records.first() is not None:
        return jsonify({'error': 'This member has giving or attendance records. '
                                 'Erase their personal data instead of deleting.',
                        'code': 'HAS_RECORDS'}), 409
    db.session.delete(member)
    db.session.commit()
    return jsonify({'message': f'Member {member.member_id} deleted'}), 200


@members_bp.route('/stats/summary', methods=['GET'])
@jwt_required()
def members_summary():
    total = scoped(Member).count()
    active = scoped(Member).filter_by(membership_status='active').count()
    inactive = scoped(Member).filter_by(membership_status='inactive').count()
    male = scoped(Member).filter_by(gender='Male', membership_status='active').count()
    female = scoped(Member).filter_by(gender='Female', membership_status='active').count()

    # Cell group breakdown
    cell_groups = tquery(Member)(
        Member.cell_group, func.count(Member.id)
    ).filter(Member.membership_status == 'active', Member.cell_group != None).group_by(Member.cell_group).all()

    return jsonify({
        'total': total,
        'active': active,
        'inactive': inactive,
        'male': male,
        'female': female,
        'cell_groups': [{'name': cg, 'count': count} for cg, count in cell_groups]
    }), 200


@members_bp.route('/cell-groups', methods=['GET'])
@jwt_required()
def get_cell_groups():
    groups = tquery(Member)(Member.cell_group).filter(
        Member.cell_group != None, Member.cell_group != ''
    ).distinct().all()
    return jsonify([g[0] for g in groups]), 200


def _apply_consent(member, data):
    """Record that the member agreed to the church holding their details."""
    if 'consent' in data and bool(data['consent']) and member.consent_at is None:
        member.consent_at = datetime.utcnow()
        member.consent_version = CONSENT_VERSION
    elif 'consent' in data and not data['consent']:
        member.consent_at = None
        member.consent_version = None


@members_bp.route('/<int:member_id>/export', methods=['GET'])
@jwt_required()
@require_role('admin', 'pastor', 'secretary')
def export_member(member_id):
    """Everything held about one member, for a data-access request."""
    member = owned_or_404(Member, member_id)
    if member.erased_at is not None:
        return jsonify({'error': 'This member\'s data was erased', 'code': 'ERASED'}), 410
    attendance = [a.to_dict() for a in member.attendance_records.order_by(
        Attendance.service_date.desc())]
    giving = []
    if can_see_money():
        giving = [f.to_dict() for f in member.finance_records
                  if f.status != 'void']
    audit('member.export', 'member', member.id)
    db.session.commit()
    return jsonify({
        'exported_at': datetime.utcnow().isoformat(),
        'member': member.to_dict(),
        'attendance': attendance,
        'giving': giving,
    }), 200


@members_bp.route('/<int:member_id>/erase', methods=['POST'])
@jwt_required()
@require_role('admin')
def erase_member(member_id):
    """Remove a member's personal details but keep the ledger and counts intact."""
    member = owned_or_404(Member, member_id)
    if member.erased_at is not None:
        return jsonify({'error': 'Already erased', 'code': 'ERASED'}), 409
    member.first_name = 'Erased'
    member.last_name = 'Member'
    for field in ('email', 'phone', 'date_of_birth', 'gender', 'county', 'sub_county',
                  'address', 'occupation', 'marital_status', 'next_of_kin',
                  'next_of_kin_phone', 'cell_group', 'baptism_date', 'notes',
                  'consent_at', 'consent_version'):
        setattr(member, field, None)
    member.membership_status = 'erased'
    member.erased_at = datetime.utcnow()
    # The audit row records that an erase happened, never what was erased.
    audit('member.erase', 'member', member.id)
    db.session.commit()
    return jsonify({'message': 'Member data erased', 'member': member.to_dict()}), 200
