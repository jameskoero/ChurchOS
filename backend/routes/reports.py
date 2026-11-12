from collections import defaultdict
from datetime import date, datetime, timedelta

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from ledger import live_money
from models import db, Church, Finance, Member
from tenancy import current_church_id, scoped, owned_or_404, roles_required, FINANCE_READ

reports_bp = Blueprint('reports', __name__)
MAX_DAYS = 400


def _day(text, default):
    if not text:
        return default
    try:
        return date.fromisoformat(str(text))
    except ValueError:
        return None


def _church_name():
    church = db.session.get(Church, current_church_id())
    return church.name if church else ''


@reports_bp.route('/giving', methods=['GET'])
@jwt_required()
@roles_required(*FINANCE_READ)
def giving_report():
    today = date.today()
    start = _day(request.args.get('from'), today.replace(day=1))
    end = _day(request.args.get('to'), today)
    if start is None or end is None:
        return jsonify({'error': 'Use dates like 2026-11-01'}), 400
    if end < start or (end - start).days > MAX_DAYS:
        return jsonify({'error': 'Choose a period of up to %d days, ending after it starts' % MAX_DAYS}), 400
    rows = scoped(Finance).filter(live_money(), Finance.transaction_date >= start,
                                  Finance.transaction_date <= end).all()
    by_type = defaultdict(lambda: [0.0, 0])
    by_category = defaultdict(float)
    by_month = defaultdict(lambda: {'income': 0.0, 'expense': 0.0})
    income = expense = 0.0
    for r in rows:
        amount = float(r.amount)
        by_type[r.transaction_type][0] += amount
        by_type[r.transaction_type][1] += 1
        key = r.transaction_date.strftime('%Y-%m')
        if r.transaction_type == 'expense':
            expense += amount
            by_month[key]['expense'] += amount
        else:
            income += amount
            by_month[key]['income'] += amount
            by_category[r.category or 'Uncategorised'] += amount
    return jsonify({
        'church': _church_name(), 'from': start.isoformat(), 'to': end.isoformat(),
        'income_total': round(income, 2), 'expense_total': round(expense, 2), 'net': round(income - expense, 2),
        'count': len(rows),
        'by_type': sorted([{'type': k, 'total': round(v[0], 2), 'count': v[1]} for k, v in by_type.items()],
                          key=lambda x: -x['total']),
        'by_category': sorted([{'category': k, 'total': round(v, 2)} for k, v in by_category.items()],
                              key=lambda x: -x['total']),
        'by_month': [{'month': k, 'income': round(v['income'], 2), 'expense': round(v['expense'], 2)}
                     for k, v in sorted(by_month.items())],
        'generated_at': datetime.utcnow().isoformat(timespec='seconds') + 'Z',
    }), 200


@reports_bp.route('/member/<int:member_id>', methods=['GET'])
@jwt_required()
@roles_required(*FINANCE_READ)
def member_statement(member_id):
    member = owned_or_404(Member, member_id)
    year = request.args.get('year', date.today().year, type=int)
    if year < 2000 or year > date.today().year:
        return jsonify({'error': 'Choose a year from 2000 to this year'}), 400
    rows = scoped(Finance).filter(
        live_money(), Finance.member_id == member.id, Finance.transaction_type != 'expense',
        Finance.transaction_date >= date(year, 1, 1), Finance.transaction_date <= date(year, 12, 31),
    ).order_by(Finance.transaction_date, Finance.id).all()
    items = [{'date': r.transaction_date.isoformat(), 'type': r.transaction_type, 'amount': float(r.amount),
              'reference': r.reference, 'mpesa_ref': r.mpesa_ref} for r in rows]
    return jsonify({
        'church': _church_name(), 'year': year,
        'member': {'id': member.id, 'member_id': member.member_id, 'full_name': member.full_name},
        'items': items, 'total': round(sum(i['amount'] for i in items), 2),
        'generated_at': datetime.utcnow().isoformat(timespec='seconds') + 'Z',
    }), 200
