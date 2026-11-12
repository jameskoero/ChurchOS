"""Subscriptions: plans, invoices the platform owner confirms, member limits, and a pause on new
records when a subscription has ended. Reading is never blocked, so a church's data is never held back."""
import os
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity, verify_jwt_in_request

from ledger import audit
from models import db, Church, Invoice, Member, User, PLAN_LIMITS, SUBSCRIPTION_PLANS
from tenancy import current_church_id, is_owner, roles_required

billing_bp = Blueprint('billing', __name__)

TRIAL_DAYS = 30
GRACE = timedelta(days=7)
PERIOD_DAYS = 30
WRITE_METHODS = ('POST', 'PUT', 'PATCH', 'DELETE')
NEVER_PAUSED = ('/api/auth', '/api/billing', '/api/health', '/api/payments/stk/callback',
                '/api/payments/mpesa/callback', '/api/payments/c2b', '/api/payments/mpesa/c2b')


def _owner_church_ids():
    return {u.church_id for u in User.query.filter(User.is_platform_owner.is_(True)).all() if u.church_id}


def state_for(church, now=None):
    """trial | active | grace | locked | complimentary, with when the current state ends."""
    now = now or datetime.utcnow()
    if church.id in _owner_church_ids():
        return {'state': 'complimentary', 'ends': None, 'previous': None}
    if church.paid_until and church.paid_until >= now:
        return {'state': 'active', 'ends': church.paid_until, 'previous': None}
    trial_end = church.trial_ends_at or ((church.created_at or now) + timedelta(days=TRIAL_DAYS))
    if not church.paid_until and trial_end >= now:
        return {'state': 'trial', 'ends': trial_end, 'previous': None}
    ended, previous = (church.paid_until, 'paid') if church.paid_until else (trial_end, 'trial')
    if now <= ended + GRACE:
        return {'state': 'grace', 'ends': ended + GRACE, 'previous': previous}
    return {'state': 'locked', 'ends': None, 'previous': previous}


def member_limit(church):
    if church.id in _owner_church_ids():
        return None
    return PLAN_LIMITS.get(church.subscription_plan or 'trial', PLAN_LIMITS['trial'])['members']


def active_members(church_id):
    return Member.query.filter(Member.church_id == church_id, Member.erased_at.is_(None),
                               Member.membership_status != 'erased').count()


def limit_problem(church_id):
    """An error message if this church may not add another member, else None."""
    church = db.session.get(Church, church_id)
    if church is None:
        return None
    limit = member_limit(church)
    if limit is not None and active_members(church_id) >= limit:
        return ('Your %s plan allows %d members. Move to a bigger plan under Billing to add more.'
                % (church.subscription_plan or 'trial', limit))
    return None


def install_guard(app):
    @app.before_request
    def _pause_writes_when_locked():
        if request.method not in WRITE_METHODS or not request.path.startswith('/api/'):
            return None
        if any(request.path.startswith(p) for p in NEVER_PAUSED):
            return None
        try:
            verify_jwt_in_request(optional=True)
            claims = get_jwt() or {}
        except Exception:
            return None                      # the route's own sign-in check answers this
        church_id = claims.get('church_id')
        if not church_id or claims.get('owner'):
            return None
        church = db.session.get(Church, int(church_id))
        if church is not None and state_for(church)['state'] == 'locked':
            return jsonify({'error': 'The subscription for this church has ended. You can still view '
                                     'everything; renew under Billing to add or change records.',
                            'code': 'SUBSCRIPTION_LOCKED'}), 402
        return None


def _iso(value):
    return value.isoformat() if value else None


def _status_body(church):
    st = state_for(church)
    days_left = None
    if st['ends'] is not None:
        days_left = max(0, (st['ends'] - datetime.utcnow()).days)
    plan = church.subscription_plan or 'trial'
    due = Invoice.query.filter_by(church_id=church.id, status='due').order_by(Invoice.id).all()
    return {
        'church': church.name, 'plan': plan,
        'price_kes': PLAN_LIMITS.get(plan, PLAN_LIMITS['trial'])['price_kes'],
        'member_limit': member_limit(church), 'members': active_members(church.id),
        'state': st['state'], 'previous': st['previous'], 'ends': _iso(st['ends']), 'days_left': days_left,
        'paid_until': _iso(church.paid_until),
        'invoices_due': [i.to_dict() for i in due],
        'pay_instructions': os.environ.get('BILLING_INSTRUCTIONS', '').strip(),
        'billing_code': billing_code(church.id),
    }


@billing_bp.route('/status', methods=['GET'])
@jwt_required()
def status():
    church = db.session.get(Church, current_church_id())
    if church is None:
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404
    return jsonify(_status_body(church)), 200


@billing_bp.route('/plans', methods=['GET'])
@jwt_required()
def plans():
    return jsonify([{'plan': p, 'members': PLAN_LIMITS[p]['members'], 'price_kes': PLAN_LIMITS[p]['price_kes']}
                    for p in SUBSCRIPTION_PLANS if p in PLAN_LIMITS]), 200


def _owner_only():
    if not is_owner():
        return jsonify({'error': 'Only the platform owner can do this', 'code': 'FORBIDDEN'}), 403
    return None


@billing_bp.route('/churches', methods=['GET'])
@jwt_required()
def churches():
    blocked = _owner_only()
    if blocked:
        return blocked
    rows = []
    for church in Church.query.order_by(Church.name).all():
        body = _status_body(church)
        body['id'] = church.id
        rows.append(body)
    return jsonify({'churches': rows}), 200


@billing_bp.route('/invoices', methods=['GET'])
@jwt_required()
@roles_required('admin')
def invoices():
    query = Invoice.query
    if is_owner() and request.args.get('church_id', type=int):
        query = query.filter_by(church_id=request.args.get('church_id', type=int))
    elif not is_owner():
        query = query.filter_by(church_id=current_church_id())
    rows = query.order_by(Invoice.id.desc()).limit(200).all()
    names = {c.id: c.name for c in Church.query.filter(Church.id.in_({r.church_id for r in rows} or {0})).all()}
    return jsonify({'invoices': [dict(i.to_dict(), church_name=names.get(i.church_id, '')) for i in rows]}), 200


@billing_bp.route('/invoices', methods=['POST'])
@jwt_required()
def create_invoice():
    blocked = _owner_only()
    if blocked:
        return blocked
    data = request.get_json(silent=True) or {}
    church = db.session.get(Church, int(data.get('church_id') or 0))
    if church is None:
        return jsonify({'error': 'Church not found'}), 404
    plan = data.get('plan')
    if plan not in PLAN_LIMITS or PLAN_LIMITS[plan]['price_kes'] <= 0:
        return jsonify({'error': 'Choose a paid plan'}), 400
    try:
        months = int(data.get('months') or 1)
    except (TypeError, ValueError):
        months = 0
    if months < 1 or months > 12:
        return jsonify({'error': 'Months must be from 1 to 12'}), 400
    invoice = Invoice(church_id=church.id, plan=plan, months=months,
                      amount=Decimal(PLAN_LIMITS[plan]['price_kes']) * months, status='due',
                      created_by=int(get_jwt_identity()))
    db.session.add(invoice)
    db.session.flush()
    audit('invoice.create', 'invoice', invoice.id, church_id=church.id,
          after={'plan': plan, 'months': months, 'amount': str(invoice.amount)})
    db.session.commit()
    return jsonify(invoice.to_dict()), 201


@billing_bp.route('/invoices/<int:invoice_id>/paid', methods=['POST'])
@jwt_required()
def mark_paid(invoice_id):
    blocked = _owner_only()
    if blocked:
        return blocked
    invoice = db.session.get(Invoice, invoice_id)
    if invoice is None:
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404
    if invoice.status != 'due':
        return jsonify({'error': 'Only a due invoice can be marked paid', 'code': 'HANDLED'}), 409
    data = request.get_json(silent=True) or {}
    method = data.get('method') if data.get('method') in ('mpesa', 'bank', 'cash') else None
    reference = str(data.get('reference') or '').strip()[:40]
    if method is None or not reference:
        return jsonify({'error': 'Give the payment method and its reference (for example the M-Pesa code)'}), 400
    church = db.session.get(Church, invoice.church_id)
    now = datetime.utcnow()
    start = church.paid_until if church.paid_until and church.paid_until > now else now
    end = start + timedelta(days=PERIOD_DAYS * invoice.months)
    invoice.status, invoice.method, invoice.reference = 'paid', method, reference
    invoice.paid_at, invoice.paid_by = now, int(get_jwt_identity())
    invoice.period_start, invoice.period_end = start, end
    church.paid_until, church.subscription_plan = end, invoice.plan
    audit('invoice.paid', 'invoice', invoice.id, church_id=church.id,
          after={'method': method, 'reference': reference, 'paid_until': end.isoformat()})
    db.session.commit()
    return jsonify(invoice.to_dict()), 200


@billing_bp.route('/invoices/<int:invoice_id>/void', methods=['POST'])
@jwt_required()
def void_invoice(invoice_id):
    blocked = _owner_only()
    if blocked:
        return blocked
    invoice = db.session.get(Invoice, invoice_id)
    if invoice is None:
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404
    if invoice.status != 'due':
        return jsonify({'error': 'Only a due invoice can be voided', 'code': 'HANDLED'}), 409
    invoice.status = 'void'
    audit('invoice.void', 'invoice', invoice.id, church_id=invoice.church_id, after={'status': 'void'})
    db.session.commit()
    return jsonify(invoice.to_dict()), 200


@billing_bp.route('/revenue', methods=['GET'])
@jwt_required()
def revenue():
    blocked = _owner_only()
    if blocked:
        return blocked
    by_month = defaultdict(float)
    for inv in Invoice.query.filter_by(status='paid').all():
        by_month[inv.paid_at.strftime('%Y-%m')] += float(inv.amount)
    states = defaultdict(int)
    for church in Church.query.all():
        states[state_for(church)['state']] += 1
    return jsonify({
        'by_month': [{'month': k, 'total': round(v, 2)} for k, v in sorted(by_month.items())],
        'total_paid': round(sum(by_month.values()), 2),
        'due_total': round(sum(float(i.amount) for i in Invoice.query.filter_by(status='due').all()), 2),
        'churches_by_state': dict(states),
    }), 200


# ---- Fix Pack 18: where churches pay ChurchOS (kept apart from every church's own accounts) ----
import re as _re

from models import PlatformSetting
from services import statement as _statement

SETTING_KEYS = {'business_name': 80, 'paybill': 10, 'till': 10, 'bank_name': 80,
                'bank_account': 30, 'bank_branch': 80, 'notes': 300}
DIGIT_KEYS = ('paybill', 'till')
BILLING_CODE = _re.compile(r'\bCOS-(\d{4,})\b', _re.IGNORECASE)
CLAIM_REF = _re.compile(r'[A-Za-z0-9\-]{6,40}')


def billing_code(church_id):
    """A church's permanent account number when paying ChurchOS, for example COS-0002."""
    return 'COS-%04d' % church_id


def _settings():
    rows = {r.key: r.value for r in PlatformSetting.query.filter(PlatformSetting.key.like('billing.%')).all()}
    return {key: rows.get('billing.' + key) or '' for key in SETTING_KEYS}


@billing_bp.route('/settings', methods=['GET'])
@jwt_required()
def get_settings():
    blocked = _owner_only()
    if blocked:
        return blocked
    return jsonify(_settings()), 200


@billing_bp.route('/settings', methods=['PUT'])
@jwt_required()
def put_settings():
    blocked = _owner_only()
    if blocked:
        return blocked
    data = request.get_json(silent=True) or {}
    clean = {}
    for key, limit in SETTING_KEYS.items():
        if key not in data:
            continue
        value = str(data.get(key) or '').strip()[:limit]
        if key in DIGIT_KEYS and value and not _re.fullmatch(r'\d{4,10}', value):
            return jsonify({'error': 'The %s number must be 4 to 10 digits'
                                     % ('Paybill' if key == 'paybill' else 'Till')}), 400
        clean[key] = value
    for key, value in clean.items():
        row = PlatformSetting.query.filter_by(key='billing.' + key).first()
        if row is None:
            row = PlatformSetting(key='billing.' + key)
            db.session.add(row)
        row.value = value
        row.updated_by = int(get_jwt_identity())
        row.updated_at = datetime.utcnow()
    # The log records which fields changed, never their values.
    audit('billing.settings', 'platform_setting', None,
          after={k: ('set' if v else 'cleared') for k, v in clean.items()})
    db.session.commit()
    return jsonify(_settings()), 200


def pay_methods(church, amount=None):
    s = _settings()
    code = billing_code(church.id)
    amt = 'KES {:,}'.format(int(amount)) if amount else 'the amount on your invoice'
    methods = []
    if s['paybill']:
        methods.append({'kind': 'paybill', 'title': 'M-Pesa Paybill (recommended)',
                        'business_no': s['paybill'], 'account': code, 'steps': [
                            'Open M-PESA, then Lipa na M-PESA, then Pay Bill.',
                            'Business number: %s' % s['paybill'],
                            'Account number: %s (your church billing code)' % code,
                            'Amount: %s' % amt,
                            'Enter your M-PESA PIN and send.',
                            'Then tap I have paid and enter the M-Pesa code from the SMS.']})
    if s['till']:
        methods.append({'kind': 'till', 'title': 'M-Pesa Till (Buy Goods)', 'till_no': s['till'], 'steps': [
            'Open M-PESA, then Lipa na M-PESA, then Buy Goods and Services.',
            'Till number: %s' % s['till'],
            'Amount: %s' % amt,
            'Enter your M-PESA PIN and send.',
            'Buy Goods has no account number, so tap I have paid and enter the M-Pesa code. '
            'That code is how your payment is matched.']})
    if s['bank_name'] and s['bank_account']:
        methods.append({'kind': 'bank', 'title': 'Bank transfer', 'reference': code, 'steps': [
            'Bank: %s%s' % (s['bank_name'], (', ' + s['bank_branch']) if s['bank_branch'] else ''),
            'Account name: %s' % (s['business_name'] or 'ChurchOS'),
            'Account number: %s' % s['bank_account'],
            'Reference: %s (your church billing code)' % code,
            'Amount: %s' % amt,
            'Then tap I have paid and enter the bank reference.']})
    return {'configured': bool(methods), 'business_name': s['business_name'] or 'ChurchOS',
            'billing_code': code, 'methods': methods, 'notes': s['notes']}


@billing_bp.route('/pay-to', methods=['GET'])
@jwt_required()
@roles_required('admin')
def pay_to():
    church = db.session.get(Church, current_church_id())
    if church is None:
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404
    due = Invoice.query.filter_by(church_id=church.id, status='due').order_by(Invoice.id).first()
    return jsonify(pay_methods(church, due.amount if due else None)), 200


@billing_bp.route('/invoices/<int:invoice_id>/claim', methods=['POST'])
@jwt_required()
@roles_required('admin')
def claim_paid(invoice_id):
    """A church admin says they have paid, with the M-Pesa or bank reference, for the owner to confirm."""
    invoice = db.session.get(Invoice, invoice_id)
    if invoice is None or invoice.church_id != current_church_id():
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404
    if invoice.status != 'due':
        return jsonify({'error': 'This invoice is already settled', 'code': 'HANDLED'}), 409
    data = request.get_json(silent=True) or {}
    method = data.get('method') if data.get('method') in ('mpesa', 'bank') else None
    reference = str(data.get('reference') or '').strip()
    if method is None or not CLAIM_REF.fullmatch(reference):
        return jsonify({'error': 'Choose M-Pesa or bank and enter the payment code (6 to 40 letters or digits)'}), 400
    invoice.claim_method, invoice.claim_reference, invoice.claimed_at = method, reference.upper(), datetime.utcnow()
    audit('invoice.claim', 'invoice', invoice.id, church_id=invoice.church_id,
          after={'method': method, 'reference': invoice.claim_reference})
    db.session.commit()
    return jsonify(invoice.to_dict()), 200


def _settle(invoice, method, reference):
    church = db.session.get(Church, invoice.church_id)
    now = datetime.utcnow()
    start = church.paid_until if church.paid_until and church.paid_until > now else now
    end = start + timedelta(days=PERIOD_DAYS * invoice.months)
    invoice.status, invoice.method, invoice.reference = 'paid', method, reference
    invoice.paid_at, invoice.paid_by = now, int(get_jwt_identity())
    invoice.period_start, invoice.period_end = start, end
    church.paid_until, church.subscription_plan = end, invoice.plan
    audit('invoice.paid', 'invoice', invoice.id, church_id=church.id,
          after={'method': method, 'reference': reference, 'paid_until': end.isoformat(), 'source': 'statement'})


@billing_bp.route('/import-statement', methods=['POST'])
@jwt_required()
def import_business_statement():
    """Owner uploads the ChurchOS business statement; payments carrying a billing code settle invoices."""
    blocked = _owner_only()
    if blocked:
        return blocked
    text = (request.get_json(silent=True) or {}).get('csv')
    if not isinstance(text, str) or not text.strip():
        return jsonify({'error': 'No statement text received'}), 400
    try:
        rows, skipped = _statement.parse(text)
    except _statement.StatementError as err:
        return jsonify({'error': str(err)}), 400
    counts = {'matched': 0, 'unmatched': 0, 'duplicates': 0, 'skipped': skipped}
    for r in rows:
        ref = r['reference'][:40]
        if Invoice.query.filter_by(reference=ref, status='paid').first() is not None:
            counts['duplicates'] += 1
            continue
        found = BILLING_CODE.search('%s %s' % (r['details'], r['reference']))
        church = db.session.get(Church, int(found.group(1))) if found else None
        due = (Invoice.query.filter_by(church_id=church.id, status='due').order_by(Invoice.id).all()
               if church is not None else [])
        target = next((i for i in due if Decimal(str(i.amount)) <= r['amount']), None)
        if target is None:
            counts['unmatched'] += 1
            continue
        method = 'mpesa' if _re.fullmatch(r'[A-Z0-9]{10}', ref) else 'bank'
        _settle(target, method, ref)
        counts['matched'] += 1
    db.session.commit()
    return jsonify(counts), 200
