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
