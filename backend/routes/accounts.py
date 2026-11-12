import re
from datetime import date

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError

from extensions import limiter
from ledger import audit
from models import db, PaymentAccount, PaymentEvent
from routes.payments import _post_money, _match_member, _already_recorded
from services import statement
from tenancy import current_church_id, scoped, owned_or_404, roles_required, FINANCE_READ

accounts_bp = Blueprint('accounts', __name__)

KINDS = ('bank_paybill', 'bank_till', 'safaricom_paybill', 'safaricom_till', 'bank_account')
NEEDS_NUMBER = ('bank_paybill', 'bank_till', 'safaricom_paybill', 'safaricom_till')
TOKEN = re.compile(r'\b[A-Za-z]{2,6}-\d{6}\b')
PHONE = re.compile(r'(?:\+?254|0)[17]\d{8}')


def _json():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _text(value, limit):
    return value.strip()[:limit] if isinstance(value, str) else ''


def _fields(data, partial=False):
    """Validated account fields, or (None, error message)."""
    out = {}
    if 'kind' in data or not partial:
        if data.get('kind') not in KINDS:
            return None, 'Choose what kind of account this is'
        out['kind'] = data['kind']
    for key, limit in (('label', 120), ('bank_name', 80), ('instructions', 500)):
        if key in data or (not partial and key == 'label'):
            out[key] = _text(data.get(key), limit)
    if not partial and not out.get('label'):
        return None, 'Give the account a name, for example Migosi tithes'
    if 'business_no' in data or not partial:
        number = _text(data.get('business_no'), 12)
        if number and not re.fullmatch(r'\d{3,10}', number):
            return None, 'The business or till number must be 3 to 10 digits'
        out['business_no'] = number
    if 'account_no' in data or not partial:
        account = _text(data.get('account_no'), 40)
        if account and not re.fullmatch(r'[A-Za-z0-9#\-/ ]+', account):
            return None, 'The account number can only have letters, digits, # - and /'
        out['account_no'] = account
    kind = out.get('kind')
    if kind in NEEDS_NUMBER and 'business_no' in out and not out['business_no']:
        return None, 'Enter the Paybill or Till number'
    return out, None


def _mask(value):
    return ('*' * max(0, len(value) - 3) + value[-3:]) if value else ''


@accounts_bp.route('/', methods=['GET'])
@jwt_required()
@roles_required(*FINANCE_READ)
def list_accounts():
    rows = scoped(PaymentAccount).filter(PaymentAccount.is_active.is_(True)).order_by(PaymentAccount.id).all()
    return jsonify({'accounts': [r.to_dict() for r in rows]}), 200


@accounts_bp.route('/', methods=['POST'])
@jwt_required()
@roles_required('admin')
def create_account():
    data = _json()
    if data is None:
        return jsonify({'error': 'No data provided'}), 400
    fields, problem = _fields(data)
    if problem:
        return jsonify({'error': problem}), 400
    row = PaymentAccount(church_id=current_church_id(), **fields)
    db.session.add(row)
    db.session.flush()
    audit('account.create', 'payment_account', row.id,
          after={'kind': row.kind, 'label': row.label, 'business_no': row.business_no,
                 'account_no': _mask(row.account_no)})
    db.session.commit()
    return jsonify(row.to_dict()), 201


@accounts_bp.route('/<int:account_id>', methods=['PUT'])
@jwt_required()
@roles_required('admin')
def update_account(account_id):
    row = owned_or_404(PaymentAccount, account_id)
    data = _json()
    if data is None:
        return jsonify({'error': 'No data provided'}), 400
    fields, problem = _fields(dict(data, kind=data.get('kind', row.kind)), partial=True)
    if problem:
        return jsonify({'error': problem}), 400
    for key, value in fields.items():
        setattr(row, key, value)
    audit('account.update', 'payment_account', row.id, after={'label': row.label, 'business_no': row.business_no,
                                                              'account_no': _mask(row.account_no)})
    db.session.commit()
    return jsonify(row.to_dict()), 200


@accounts_bp.route('/<int:account_id>', methods=['DELETE'])
@jwt_required()
@roles_required('admin')
def remove_account(account_id):
    row = owned_or_404(PaymentAccount, account_id)
    row.is_active = False
    audit('account.remove', 'payment_account', row.id, after={'label': row.label})
    db.session.commit()
    return jsonify({'message': 'Account removed'}), 200


def _member_from_text(church_id, text):
    for token in TOKEN.findall(text or ''):
        member = _match_member(church_id, token)
        if member is not None:
            return member
    for token in PHONE.findall(text or ''):
        member = _match_member(church_id, token)
        if member is not None:
            return member
    return None


@accounts_bp.route('/import-statement', methods=['POST'])
@jwt_required()
@roles_required('admin', 'treasurer')
@limiter.limit('10 per minute')
def import_statement():
    """Read a bank or M-Pesa statement CSV. Money with a member number in its details is recorded;
    the rest waits in the Paybill inbox. Importing the same file twice records nothing twice."""
    data = _json() or {}
    text = data.get('csv')
    if not isinstance(text, str) or not text.strip():
        return jsonify({'error': 'No statement text received'}), 400
    try:
        rows, skipped = statement.parse(text)
    except statement.StatementError as err:
        return jsonify({'error': str(err)}), 400
    church_id = current_church_id()
    user_id = int(get_jwt_identity())
    counts = {'imported': 0, 'matched': 0, 'unmatched': 0, 'duplicates': 0, 'skipped': skipped}
    for r in rows:
        trans_id = ('B%d-%s' % (church_id, r['reference']))[:30]
        ref = r['reference'][:30]
        if PaymentEvent.query.filter_by(trans_id=trans_id).first() is not None or _already_recorded(church_id, ref):
            counts['duplicates'] += 1
            continue
        event = PaymentEvent(
            church_id=church_id, trans_id=trans_id, amount=r['amount'], payer_name=r['details'][:120],
            bill_ref=r['details'][:60], trans_time=(r['date'].isoformat() if r['date'] else '')[:20],
            status='unmatched', note='Imported from statement')
        db.session.add(event)
        db.session.flush()
        member = _member_from_text(church_id, r['details'])
        row = None
        if member is not None:
            row = _post_money(church_id, member.id, r['amount'], 'other', ref, user_id,
                              'Matched from statement import', when=r['date'])
        if row is not None:
            event.status, event.member_id, event.finance_id = 'matched', member.id, row.id
            counts['matched'] += 1
        else:
            counts['unmatched'] += 1
        counts['imported'] += 1
    audit('statement.import', 'payment_event', None, after=counts)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'The same statement was imported at the same moment. Try again.'}), 409
    return jsonify(counts), 200
