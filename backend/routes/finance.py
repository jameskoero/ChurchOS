from datetime import date, datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from sqlalchemy import func

from ledger import live_money, money, audit
from models import (db, Finance, Member, User, AuditLog,
                    TRANSACTION_TYPES, FINANCE_CATEGORIES)
from tenancy import (current_church_id, scoped, owned_or_404, tquery,
                     page_size, roles_required, FINANCE_READ)

finance_bp = Blueprint('finance', __name__)

FINANCE_WRITE = ('admin', 'treasurer')
INCOME_TYPES = ['tithe', 'offering', 'donation', 'project_fund', 'other']
# Once a second person has verified a transaction these cannot change.
LOCKED_FIELDS = ('transaction_type', 'amount', 'transaction_date', 'mpesa_ref',
                 'member_id', 'payment_method')
TEXT_FIELDS = ('category', 'description', 'payment_method', 'notes')


def _json():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _clean(value, limit=None):
    if value is None:
        return None
    text = str(value).strip()
    if limit:
        text = text[:limit]
    return text or None


def _mpesa(value):
    text = _clean(value, 30)
    return text.upper() if text else None


def _parse_date(value):
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _member(value):
    """Return (member_id or None, True when the member is not in this church)."""
    if value in (None, '', 0):
        return None, False
    try:
        member_id = int(value)
    except (TypeError, ValueError):
        return None, True
    if scoped(Member).filter(Member.id == member_id).first() is None:
        return None, True
    return member_id, False


def _same(field, old, new):
    if field == 'mpesa_ref':
        return (old or '').upper() == (new or '').upper()
    return old == new


def _new_reference():
    for _ in range(20):
        reference = Finance.generate_reference()
        if Finance.query.filter_by(reference=reference).first() is None:
            return reference
    raise RuntimeError('could not allocate a transaction reference')


def _duplicate_mpesa(mpesa_ref, ignore_id=None):
    if not mpesa_ref:
        return False
    query = scoped(Finance).filter(Finance.mpesa_ref == mpesa_ref, live_money())
    if ignore_id is not None:
        query = query.filter(Finance.id != ignore_id)
    return query.first() is not None


def _other_finance_users(user_id):
    return scoped(User).filter(
        User.role.in_(FINANCE_WRITE), User.is_active.is_(True),
        User.id != user_id).count()


def _snapshot(tx):
    return {
        'reference': tx.reference, 'transaction_type': tx.transaction_type,
        'category': tx.category, 'amount': str(tx.amount),
        'member_id': tx.member_id, 'payment_method': tx.payment_method,
        'mpesa_ref': tx.mpesa_ref,
        'transaction_date': tx.transaction_date.isoformat() if tx.transaction_date else None,
        'verified': bool(tx.verified), 'status': tx.status or 'posted',
        'description': tx.description, 'notes': tx.notes,
    }


def _verify(tx, user_id):
    """Second-person check. Returns an error response or None."""
    if tx.recorded_by == user_id and _other_finance_users(user_id) > 0:
        return jsonify({'error': 'A different admin or treasurer must verify this transaction',
                        'code': 'NEEDS_SECOND_PERSON'}), 403
    tx.verified = True
    tx.verified_by = user_id
    tx.verified_at = datetime.utcnow()
    return None


@finance_bp.route('/', methods=['GET'])
@jwt_required()
@roles_required(*FINANCE_READ)
def get_transactions():
    page = request.args.get('page', 1, type=int)
    per_page = page_size(25)
    tx_type = request.args.get('type', '')
    category = request.args.get('category', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    search = request.args.get('search', '').strip()

    query = scoped(Finance)
    if request.args.get('include_void') != '1':
        query = query.filter(live_money())

    if tx_type:
        query = query.filter_by(transaction_type=tx_type)
    if category:
        query = query.filter_by(category=category)
    if search:
        query = query.filter(
            Finance.reference.ilike(f'%{search}%') |
            Finance.description.ilike(f'%{search}%') |
            Finance.mpesa_ref.ilike(f'%{search}%')
        )
    if date_from and _parse_date(date_from):
        query = query.filter(Finance.transaction_date >= _parse_date(date_from))
    if date_to and _parse_date(date_to):
        query = query.filter(Finance.transaction_date <= _parse_date(date_to))

    total = query.count()
    records = query.order_by(Finance.transaction_date.desc(), Finance.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'transactions': [r.to_dict() for r in records.items],
        'total': total,
        'pages': records.pages,
        'current_page': page
    }), 200


@finance_bp.route('/', methods=['POST'])
@jwt_required()
@roles_required(*FINANCE_WRITE)
def create_transaction():
    user_id = int(get_jwt_identity())
    data = _json()
    if data is None:
        return jsonify({'error': 'No data provided'}), 400

    for field in ('transaction_type', 'amount', 'transaction_date'):
        if data.get(field) in (None, ''):
            return jsonify({'error': f'{field} is required'}), 400
    if data['transaction_type'] not in TRANSACTION_TYPES:
        return jsonify({'error': 'Invalid transaction_type'}), 400
    amount = money(data['amount'])
    if amount is None:
        return jsonify({'error': 'Amount must be a positive number'}), 400
    when = _parse_date(data['transaction_date'])
    if when is None:
        return jsonify({'error': 'Invalid transaction_date (use YYYY-MM-DD)'}), 400

    member_id, bad_member = _member(data.get('member_id'))
    if bad_member:
        return jsonify({'error': 'Member not found'}), 404
    mpesa_ref = _mpesa(data.get('mpesa_ref'))
    if _duplicate_mpesa(mpesa_ref):
        return jsonify({'error': 'This M-Pesa reference is already recorded',
                        'code': 'DUPLICATE_MPESA_REF'}), 409

    transaction = Finance(
        church_id=current_church_id(),
        reference=_new_reference(),
        transaction_type=data['transaction_type'],
        category=_clean(data.get('category'), 80),
        amount=amount,
        currency='KES',
        description=_clean(data.get('description')),
        member_id=member_id,
        payment_method=_clean(data.get('payment_method'), 30) or 'cash',
        mpesa_ref=mpesa_ref,
        transaction_date=when,
        recorded_by=user_id,
        verified=False,          # never trusted from the client
        status='posted',
        notes=_clean(data.get('notes'))
    )
    db.session.add(transaction)
    db.session.flush()
    audit('finance.create', 'finance', transaction.id, after=_snapshot(transaction))
    db.session.commit()
    return jsonify(transaction.to_dict()), 201


@finance_bp.route('/<int:tx_id>', methods=['PUT'])
@jwt_required()
@roles_required(*FINANCE_WRITE)
def update_transaction(tx_id):
    user_id = int(get_jwt_identity())
    tx = owned_or_404(Finance, tx_id)
    data = _json()
    if data is None:
        return jsonify({'error': 'No data provided'}), 400
    if tx.status == 'void':
        return jsonify({'error': 'A voided transaction cannot be changed', 'code': 'VOID'}), 409

    before = _snapshot(tx)
    wanted = {}
    if 'transaction_type' in data:
        if data['transaction_type'] not in TRANSACTION_TYPES:
            return jsonify({'error': 'Invalid transaction_type'}), 400
        wanted['transaction_type'] = data['transaction_type']
    if 'amount' in data:
        amount = money(data['amount'])
        if amount is None:
            return jsonify({'error': 'Invalid amount'}), 400
        wanted['amount'] = amount
    if 'transaction_date' in data:
        when = _parse_date(data['transaction_date'])
        if when is None:
            return jsonify({'error': 'Invalid transaction_date (use YYYY-MM-DD)'}), 400
        wanted['transaction_date'] = when
    if 'mpesa_ref' in data:
        wanted['mpesa_ref'] = _mpesa(data['mpesa_ref'])
    if 'member_id' in data:
        member_id, bad_member = _member(data['member_id'])
        if bad_member:
            return jsonify({'error': 'Member not found'}), 404
        wanted['member_id'] = member_id
    for field in TEXT_FIELDS:
        if field in data:
            wanted[field] = _clean(data[field], 80 if field == 'category' else None)

    changed = {k: v for k, v in wanted.items() if not _same(k, getattr(tx, k), v)}
    if tx.verified and any(k in LOCKED_FIELDS for k in changed):
        return jsonify({'error': 'Verified transactions cannot be changed. '
                                 'Void it and record a new one.', 'code': 'LOCKED'}), 409
    if 'mpesa_ref' in changed and _duplicate_mpesa(changed['mpesa_ref'], ignore_id=tx.id):
        return jsonify({'error': 'This M-Pesa reference is already recorded',
                        'code': 'DUPLICATE_MPESA_REF'}), 409
    for field, value in changed.items():
        setattr(tx, field, value)

    if 'verified' in data and bool(data['verified']) != bool(tx.verified):
        if not data['verified']:
            return jsonify({'error': 'A verified transaction cannot be un-verified. '
                                     'Void it instead.', 'code': 'LOCKED'}), 409
        problem = _verify(tx, user_id)
        if problem:
            db.session.rollback()
            return problem

    after = _snapshot(tx)
    if after != before:
        audit('finance.update', 'finance', tx.id, before=before, after=after)
    db.session.commit()
    return jsonify(tx.to_dict()), 200


@finance_bp.route('/<int:tx_id>/verify', methods=['POST'])
@jwt_required()
@roles_required(*FINANCE_WRITE)
def verify_transaction(tx_id):
    tx = owned_or_404(Finance, tx_id)
    if tx.status == 'void':
        return jsonify({'error': 'A voided transaction cannot be verified', 'code': 'VOID'}), 409
    if not tx.verified:
        before = _snapshot(tx)
        problem = _verify(tx, int(get_jwt_identity()))
        if problem:
            return problem
        audit('finance.verify', 'finance', tx.id, before=before, after=_snapshot(tx))
        db.session.commit()
    return jsonify(tx.to_dict()), 200


@finance_bp.route('/<int:tx_id>', methods=['DELETE'])
@jwt_required()
@roles_required(*FINANCE_WRITE)
def delete_transaction(tx_id):
    """Money is never erased. 'Delete' marks the row void and keeps it."""
    if get_jwt().get('role') != 'admin':
        return jsonify({'error': 'Only admin can delete transactions'}), 403
    tx = owned_or_404(Finance, tx_id)
    if tx.status == 'void':
        return jsonify({'error': 'Transaction is already void', 'code': 'VOID'}), 409
    data = _json() or {}
    before = _snapshot(tx)
    tx.status = 'void'
    tx.voided_by = int(get_jwt_identity())
    tx.voided_at = datetime.utcnow()
    tx.void_reason = _clean(data.get('reason') or request.args.get('reason')) or 'Voided'
    audit('finance.void', 'finance', tx.id, before=before, after=_snapshot(tx))
    db.session.commit()
    return jsonify({'message': 'Transaction voided', 'transaction': tx.to_dict()}), 200


@finance_bp.route('/audit', methods=['GET'])
@jwt_required()
@roles_required('admin')
def audit_trail():
    page = request.args.get('page', 1, type=int)
    query = AuditLog.query.filter(AuditLog.church_id == current_church_id())
    entity_id = request.args.get('entity_id', type=int)
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)
    records = query.order_by(AuditLog.id.desc()).paginate(
        page=page, per_page=page_size(50), error_out=False)
    return jsonify({
        'entries': [r.to_dict() for r in records.items],
        'total': records.total,
        'pages': records.pages,
        'current_page': page
    }), 200


@finance_bp.route('/summary', methods=['GET'])
@jwt_required()
@roles_required(*FINANCE_READ)
def finance_summary():
    year = request.args.get('year', date.today().year, type=int)
    month = request.args.get('month', type=int)

    def in_period(query):
        query = query.filter(live_money(),
                             func.extract('year', Finance.transaction_date) == year)
        if month:
            query = query.filter(func.extract('month', Finance.transaction_date) == month)
        return query

    total_income = in_period(tquery(Finance)(func.sum(Finance.amount)).filter(
        Finance.transaction_type.in_(INCOME_TYPES))).scalar() or 0
    total_expense = in_period(tquery(Finance)(func.sum(Finance.amount)).filter(
        Finance.transaction_type == 'expense')).scalar() or 0

    monthly = tquery(Finance)(
        func.extract('month', Finance.transaction_date).label('month'),
        Finance.transaction_type,
        func.sum(Finance.amount).label('total')
    ).filter(
        live_money(),
        func.extract('year', Finance.transaction_date) == year
    ).group_by('month', Finance.transaction_type).all()

    by_category = tquery(Finance)(
        Finance.category,
        func.sum(Finance.amount).label('total')
    ).filter(
        live_money(),
        func.extract('year', Finance.transaction_date) == year
    ).group_by(Finance.category).all()

    return jsonify({
        'total_income': float(total_income),
        'total_expense': float(total_expense),
        'net': float(total_income) - float(total_expense),
        'year': year,
        'monthly_breakdown': [
            {
                'month': int(r.month),
                'transaction_type': r.transaction_type,
                'total': float(r.total)
            } for r in monthly
        ],
        'by_category': [
            {'category': r.category or 'Uncategorized', 'total': float(r.total)}
            for r in by_category
        ]
    }), 200


@finance_bp.route('/transaction-types', methods=['GET'])
@jwt_required()
def get_transaction_types():
    return jsonify(TRANSACTION_TYPES), 200


@finance_bp.route('/categories', methods=['GET'])
@jwt_required()
def get_categories():
    return jsonify(FINANCE_CATEGORIES), 200
