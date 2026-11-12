import hmac
import logging
import os
import re
from datetime import date, datetime, timedelta

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError

from extensions import limiter, client_ip
from ledger import audit, live_money, money, new_reference
from models import (db, Church, Finance, Member, PaymentEvent, PaymentRequest,
                    TRANSACTION_TYPES)
from services import mpesa
from tenancy import (current_church_id, scoped, owned_or_404, page_size,
                     roles_required)

payments_bp = Blueprint('payments', __name__)
log = logging.getLogger('churchos.payments')

PAY_ROLES = ('admin', 'treasurer')
INCOME_TYPES = [t for t in TRANSACTION_TYPES if t != 'expense']
MAX_STK = 150000          # M-Pesa single transaction limit, in shillings
EXPIRE_AFTER = timedelta(minutes=15)
QUERY_AFTER = timedelta(seconds=20)
QUERY_EVERY = timedelta(seconds=15)
ACK = {'ResultCode': 0, 'ResultDesc': 'Accepted'}


def _json():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def normalize_phone(value):
    """Return 2547XXXXXXXX / 2541XXXXXXXX, or None."""
    digits = re.sub(r'[\s\-().]', '', str(value or ''))
    if digits.startswith('+'):
        digits = digits[1:]
    if re.fullmatch(r'0[17]\d{8}', digits):
        digits = '254' + digits[1:]
    elif re.fullmatch(r'[17]\d{8}', digits):
        digits = '254' + digits
    return digits if re.fullmatch(r'254[17]\d{8}', digits) else None


def _mask(phone):
    return phone[:5] + '****' + phone[-3:]


def _ack():
    return jsonify(ACK), 200


def _guard(secret):
    """Callbacks are unsigned, so the URL carries a long secret. None means allowed."""
    expected = os.environ.get('MPESA_CALLBACK_SECRET', '')
    if len(expected) < 16:
        return jsonify({'error': 'Payments are not configured', 'code': 'MPESA_NOT_CONFIGURED'}), 503
    if not hmac.compare_digest(str(secret), expected):
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404
    allowed = [ip.strip() for ip in os.environ.get('MPESA_ALLOWED_IPS', '').split(',') if ip.strip()]
    if allowed and client_ip() not in allowed:
        return jsonify({'error': 'Not allowed', 'code': 'FORBIDDEN'}), 403
    return None


def _new_reference():
    return new_reference()


def _already_recorded(church_id, mpesa_ref):
    return Finance.query.filter(
        Finance.church_id == church_id, Finance.mpesa_ref == mpesa_ref,
        live_money()).first() is not None


def _post_money(church_id, member_id, amount, tx_type, mpesa_ref, user_id, note, when=None):
    """Create the ledger row for a confirmed payment. None if already recorded."""
    if _already_recorded(church_id, mpesa_ref):
        return None
    row = Finance(
        church_id=church_id, reference=_new_reference(), transaction_type=tx_type,
        category='M-Pesa', amount=amount, currency='KES', member_id=member_id,
        payment_method='mpesa', mpesa_ref=mpesa_ref, transaction_date=when or date.today(),
        recorded_by=user_id, verified=False, status='posted', notes=note)
    db.session.add(row)
    db.session.flush()
    audit('finance.create', 'finance', row.id, church_id=church_id, user_id=user_id,
          after={'amount': str(amount), 'mpesa_ref': mpesa_ref, 'source': note})
    return row


# ── Staff starts a payment prompt ────────────────────────────────────────────
@payments_bp.route('/mpesa/stk', methods=['POST'])
@jwt_required()
@roles_required(*PAY_ROLES)
@limiter.limit('10 per minute')
def start_stk():
    data = _json()
    if data is None:
        return jsonify({'error': 'No data provided'}), 400
    phone = normalize_phone(data.get('phone'))
    if phone is None:
        return jsonify({'error': 'Enter a Safaricom number like 0712345678'}), 400
    amount = money(data.get('amount'))
    if amount is None or amount != amount.to_integral_value() or amount > MAX_STK:
        return jsonify({'error': 'Amount must be a whole number from 1 to %d' % MAX_STK}), 400
    tx_type = data.get('transaction_type') or 'tithe'
    if tx_type not in INCOME_TYPES:
        return jsonify({'error': 'Invalid transaction_type'}), 400

    member = None
    if data.get('member_id') not in (None, '', 0):
        try:
            member = scoped(Member).filter(Member.id == int(data['member_id'])).first()
        except (TypeError, ValueError):
            member = None
        if member is None:
            return jsonify({'error': 'Member not found'}), 404

    try:
        sent = mpesa.stk_push(phone, amount, member.member_id if member else 'CHURCH',
                              'Church giving')
    except mpesa.NotConfigured:
        return jsonify({'error': 'M-Pesa is not set up yet', 'code': 'MPESA_NOT_CONFIGURED',
                        'missing': mpesa.setup_status()['missing']}), 503
    except mpesa.MpesaError as err:
        log.warning('stk push failed: %s', err)
        return jsonify({'error': 'Safaricom could not send the prompt. Try again.',
                        'code': 'MPESA_ERROR'}), 502

    user_id = int(get_jwt_identity())
    pr = PaymentRequest(
        church_id=current_church_id(), member_id=member.id if member else None,
        phone_masked=_mask(phone), amount=amount, transaction_type=tx_type,
        status='pending', checkout_request_id=sent['checkout_request_id'],
        merchant_request_id=sent.get('merchant_request_id'), requested_by=user_id)
    db.session.add(pr)
    db.session.flush()
    audit('payment.request', 'payment', pr.id, after={'amount': str(amount), 'phone': pr.phone_masked})
    db.session.commit()
    return jsonify(pr.to_dict()), 202


@payments_bp.route('/setup', methods=['GET'])
@jwt_required()
@roles_required(*PAY_ROLES)
def setup_status():
    """Tells staff which M-Pesa settings are missing. Never returns a secret."""
    return jsonify(mpesa.setup_status()), 200


@payments_bp.route('/setup/test', methods=['POST'])
@jwt_required()
@roles_required('admin')
@limiter.limit('6 per minute')
def setup_test():
    status = mpesa.setup_status()
    if status['missing']:
        return jsonify({'ok': False, 'error': 'Add the missing settings first',
                        'missing': status['missing']}), 400
    try:
        mpesa.test_credentials()
    except mpesa.MpesaError as err:
        return jsonify({'ok': False,
                        'error': 'Safaricom did not accept the Consumer Key and Secret (%s)' % err}), 502
    return jsonify({'ok': True, 'message': 'Safaricom accepted your Consumer Key and Secret.'}), 200


@payments_bp.route('/requests', methods=['GET'])
@jwt_required()
@roles_required(*PAY_ROLES)
def list_requests():
    rows = scoped(PaymentRequest).order_by(PaymentRequest.id.desc()).limit(page_size(25)).all()
    return jsonify({'requests': [r.to_dict() for r in rows]}), 200


@payments_bp.route('/requests/<int:request_id>', methods=['GET'])
@jwt_required()
@roles_required(*PAY_ROLES)
def get_request(request_id):
    pr = owned_or_404(PaymentRequest, request_id)
    if pr.status == 'pending':
        _resolve_by_query(pr)
    if pr.status == 'pending' and pr.created_at < datetime.utcnow() - EXPIRE_AFTER:
        pr.status = 'expired'
        db.session.commit()
    return jsonify(pr.to_dict()), 200


_last_query = {}


def _resolve_by_query(pr):
    """If Safaricom's callback has not arrived, ask Safaricom for the result directly."""
    now = datetime.utcnow()
    if pr.created_at > now - QUERY_AFTER:
        return
    last = _last_query.get(pr.id)
    if last and now - last < QUERY_EVERY:
        return
    _last_query[pr.id] = now
    try:
        code, desc = mpesa.stk_query(pr.checkout_request_id)
    except mpesa.MpesaError:
        return                      # still processing, or Safaricom unreachable: ask again later
    pr.result_code = code[:10]
    pr.result_desc = desc[:255]
    pr.completed_at = now
    if code == '0':
        row = _post_money(pr.church_id, pr.member_id, pr.amount, pr.transaction_type,
                          None, pr.requested_by,
                          'Recorded from M-Pesa status check (receipt follows if Safaricom sends it)')
        pr.status = 'paid'
        pr.finance_id = row.id if row else None
        audit('payment.paid', 'payment', pr.id, church_id=pr.church_id, user_id=pr.requested_by,
              after={'source': 'status query', 'amount': str(pr.amount)})
    else:
        pr.status = 'cancelled' if code == '1032' else 'failed'
    db.session.commit()


# ── Safaricom calls back ─────────────────────────────────────────────────────
@payments_bp.route('/stk/callback/<secret>', methods=['POST'])
@payments_bp.route('/mpesa/callback/<secret>', methods=['POST'])
@limiter.limit('120 per minute')
def stk_callback(secret):
    blocked = _guard(secret)
    if blocked:
        return blocked
    body = _json() or {}
    cb = (body.get('Body') or {}).get('stkCallback') or {}
    checkout = str(cb.get('CheckoutRequestID') or '')
    pr = PaymentRequest.query.filter_by(checkout_request_id=checkout).first() if checkout else None
    if pr is None:
        log.warning('callback for an unknown checkout id')
        return _ack()
    if pr.status == 'paid' and not pr.mpesa_receipt and str(cb.get('ResultCode')) == '0':
        # Paid via the status check first; the late callback supplies the receipt.
        meta = (cb.get('CallbackMetadata') or {}).get('Item') or []
        items = {i.get('Name'): i.get('Value') for i in meta if isinstance(i, dict)}
        receipt = str(items.get('MpesaReceiptNumber') or '').strip().upper()[:30]
        if receipt and money(items.get('Amount')) == pr.amount:
            pr.mpesa_receipt = receipt
            if pr.finance_id:
                row = db.session.get(Finance, pr.finance_id)
                if row is not None and not row.mpesa_ref:
                    row.mpesa_ref = receipt
            db.session.commit()
        return _ack()
    if pr.status != 'pending':
        return _ack()                       # already handled: nothing to do twice

    code = str(cb.get('ResultCode'))
    pr.result_code = code[:10]
    pr.result_desc = str(cb.get('ResultDesc') or '')[:255]
    pr.completed_at = datetime.utcnow()

    if code != '0':
        pr.status = 'cancelled' if code == '1032' else 'failed'
        db.session.commit()
        return _ack()

    meta = (cb.get('CallbackMetadata') or {}).get('Item') or []
    items = {i.get('Name'): i.get('Value') for i in meta if isinstance(i, dict)}
    receipt = str(items.get('MpesaReceiptNumber') or '').strip().upper()[:30]
    paid = money(items.get('Amount'))
    if not receipt or paid is None or paid != pr.amount:
        pr.status = 'review'                # money moved but the details do not agree
        pr.result_desc = 'Needs review: amount or receipt did not match the request'
        db.session.commit()
        return _ack()

    pr.mpesa_receipt = receipt
    row = _post_money(pr.church_id, pr.member_id, pr.amount, pr.transaction_type,
                      receipt, pr.requested_by, 'Recorded automatically from M-Pesa')
    pr.status = 'paid'
    pr.finance_id = row.id if row else None
    audit('payment.paid', 'payment', pr.id, church_id=pr.church_id, user_id=pr.requested_by,
          after={'receipt': receipt, 'amount': str(pr.amount)})
    db.session.commit()
    return _ack()


@payments_bp.route('/c2b/<secret>/validation', methods=['POST'])
@payments_bp.route('/mpesa/c2b/<secret>/validation', methods=['POST'])
def c2b_validation(secret):
    blocked = _guard(secret)
    return blocked if blocked else _ack()


def _match_member(church_id, bill_ref):
    """The one member this Paybill account text points to, or None."""
    ref = re.sub(r'\s', '', str(bill_ref or '')).upper()
    if not ref:
        return None
    base = Member.query.filter(Member.church_id == church_id,
                               Member.erased_at.is_(None))
    found = base.filter(Member.member_id == ref).all()
    if not found and ref.isdigit() and len(ref) == 6:
        found = base.filter(Member.member_id.like('%-' + ref)).all()
    if not found:
        phone = normalize_phone(ref)
        if phone:
            found = [m for m in base.filter(Member.phone.like('%' + phone[-9:])).all()
                     if normalize_phone(m.phone) == phone]
    return found[0] if len(found) == 1 else None


@payments_bp.route('/c2b/<secret>/confirmation', methods=['POST'])
@payments_bp.route('/mpesa/c2b/<secret>/confirmation', methods=['POST'])
@limiter.limit('120 per minute')
def c2b_confirmation(secret):
    blocked = _guard(secret)
    if blocked:
        return blocked
    p = _json() or {}
    trans_id = str(p.get('TransID') or '').strip().upper()[:30]
    amount = money(p.get('TransAmount'))
    shortcode = str(p.get('BusinessShortCode') or '').strip()
    if not trans_id or amount is None or not shortcode:
        return _ack()
    if PaymentEvent.query.filter_by(trans_id=trans_id).first() is not None:
        return _ack()                       # Safaricom resends; keep it to one record
    churches = Church.query.filter(Church.paybill == shortcode).all()
    if len(churches) != 1:
        log.warning('paybill payment for an unknown or shared shortcode')
        return _ack()
    church = churches[0]
    bill_ref = str(p.get('BillRefNumber') or '').strip()[:60]
    member = _match_member(church.id, bill_ref)
    event = PaymentEvent(
        church_id=church.id, trans_id=trans_id, amount=amount,
        msisdn=str(p.get('MSISDN') or '')[:64], bill_ref=bill_ref,
        payer_name=' '.join(str(p.get(k) or '') for k in ('FirstName', 'MiddleName', 'LastName')).strip()[:120],
        trans_time=str(p.get('TransTime') or '')[:20], status='unmatched')
    db.session.add(event)
    try:
        db.session.flush()
        if member is not None:
            row = _post_money(church.id, member.id, amount, 'other', trans_id, None,
                              'Recorded automatically from Paybill')
            if row is not None:
                event.status = 'matched'
                event.member_id = member.id
                event.finance_id = row.id
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
    return _ack()


# ── Treasurer works the inbox ────────────────────────────────────────────────
@payments_bp.route('/inbox', methods=['GET'])
@jwt_required()
@roles_required(*PAY_ROLES)
def inbox():
    status = request.args.get('status', 'unmatched')
    query = scoped(PaymentEvent)
    if status != 'all':
        query = query.filter(PaymentEvent.status == status)
    rows = query.order_by(PaymentEvent.id.desc()).limit(page_size(50)).all()
    return jsonify({'events': [e.to_dict() for e in rows],
                    'unmatched': scoped(PaymentEvent).filter(
                        PaymentEvent.status == 'unmatched').count()}), 200


@payments_bp.route('/inbox/<int:event_id>/match', methods=['POST'])
@jwt_required()
@roles_required(*PAY_ROLES)
def match_event(event_id):
    event = owned_or_404(PaymentEvent, event_id)
    data = _json() or {}
    if event.status != 'unmatched':
        return jsonify({'error': 'This payment is already handled', 'code': 'HANDLED'}), 409
    try:
        member = scoped(Member).filter(Member.id == int(data.get('member_id'))).first()
    except (TypeError, ValueError):
        member = None
    if member is None or member.erased_at is not None:
        return jsonify({'error': 'Member not found'}), 404
    tx_type = data.get('transaction_type') or 'tithe'
    if tx_type not in INCOME_TYPES:
        return jsonify({'error': 'Invalid transaction_type'}), 400
    user_id = int(get_jwt_identity())
    row = _post_money(event.church_id, member.id, event.amount, tx_type, event.trans_id,
                      user_id, 'Matched by hand from the Paybill inbox')
    if row is None:
        return jsonify({'error': 'This M-Pesa reference is already recorded',
                        'code': 'DUPLICATE_MPESA_REF'}), 409
    event.status = 'matched'
    event.member_id = member.id
    event.finance_id = row.id
    audit('payment.match', 'payment_event', event.id, after={'member_id': member.id})
    db.session.commit()
    return jsonify(event.to_dict()), 200


@payments_bp.route('/inbox/<int:event_id>/ignore', methods=['POST'])
@jwt_required()
@roles_required(*PAY_ROLES)
def ignore_event(event_id):
    event = owned_or_404(PaymentEvent, event_id)
    if event.status != 'unmatched':
        return jsonify({'error': 'This payment is already handled', 'code': 'HANDLED'}), 409
    reason = str((_json() or {}).get('reason') or '').strip()[:200]
    if not reason:
        return jsonify({'error': 'Give a reason (for example: not a church payment)'}), 400
    event.status = 'ignored'
    event.note = reason
    audit('payment.ignore', 'payment_event', event.id, after={'reason': reason})
    db.session.commit()
    return jsonify(event.to_dict()), 200
