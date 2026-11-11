"""Plain, explainable insights computed from a church's own records.

Every rule here can be read and checked by a person. Nothing is sent to an
outside service, and nothing is invented: a message says when there is not
enough data yet.
"""
from collections import defaultdict
from datetime import date, timedelta
from statistics import median

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import func

from ledger import live_money
from models import Attendance, Finance, Member
from tenancy import (scoped, tquery, roles_required, can_see_personal,
                     FINANCE_READ, PERSONAL_ROLES)

insights_bp = Blueprint('insights', __name__)

INCOME = ['tithe', 'offering', 'donation', 'project_fund', 'other']
MIN_PRIOR_VISITS = 3         # attended at least this often before going quiet
LOOKBACK_WEEKS = 8
MIN_SAMPLE = 10              # amounts needed before "unusually large" means anything


def care_candidates(weeks=4):
    """Members who used to come regularly and have not been seen recently."""
    weeks = max(2, min(int(weeks), 12))
    today = date.today()
    recent_start = today - timedelta(weeks=weeks)
    window_start = recent_start - timedelta(weeks=LOOKBACK_WEEKS)
    seen_recently = {row[0] for row in tquery(Attendance)(Attendance.member_id).filter(
        Attendance.service_date >= recent_start).distinct().all()}
    before = tquery(Attendance)(
        Attendance.member_id, func.count(Attendance.id), func.max(Attendance.service_date)
    ).filter(
        Attendance.service_date >= window_start, Attendance.service_date < recent_start
    ).group_by(Attendance.member_id).all()
    quiet = {mid: (count, last) for mid, count, last in before
             if count >= MIN_PRIOR_VISITS and mid not in seen_recently}
    if not quiet:
        return []
    members = scoped(Member).filter(
        Member.id.in_(list(quiet)), Member.membership_status == 'active',
        Member.erased_at.is_(None)).all()
    found = []
    for m in members:
        count, last = quiet[m.id]
        found.append({
            'id': m.id, 'member_id': m.member_id, 'full_name': m.full_name,
            'phone': m.phone, 'last_seen': last.isoformat(),
            'weeks_absent': (today - last).days // 7, 'attended_before': count,
            'reason': 'Came %d times in the %d weeks before, and not at all in the last %d weeks'
                      % (count, LOOKBACK_WEEKS, weeks),
        })
    return sorted(found, key=lambda r: (-r['weeks_absent'], r['full_name']))


@insights_bp.route('/care', methods=['GET'])
@jwt_required()
@roles_required(*PERSONAL_ROLES)
def care():
    weeks = request.args.get('weeks', 4, type=int) or 4
    people = care_candidates(weeks)
    return jsonify({'weeks': max(2, min(weeks, 12)), 'total': len(people),
                    'members': people[:50],
                    'method': 'Rule: attended at least %d times in the %d weeks before the quiet period, '
                              'none during it. A person decides what to do; this only lists names.'
                              % (MIN_PRIOR_VISITS, LOOKBACK_WEEKS)}), 200


def _income_rows(since):
    return scoped(Finance).filter(
        live_money(), Finance.transaction_type.in_(INCOME),
        Finance.transaction_date >= since).all()


@insights_bp.route('/giving', methods=['GET'])
@jwt_required()
@roles_required(*FINANCE_READ)
def giving():
    today = date.today()
    flags = []

    seen = defaultdict(list)
    for row in _income_rows(today - timedelta(days=90)):
        if row.member_id:
            seen[(row.member_id, str(row.amount), row.transaction_date)].append(row)
    for (member_id, amount, when), rows in seen.items():
        if len(rows) > 1:
            flags.append({
                'kind': 'possible_duplicate', 'finance_ids': [r.id for r in rows],
                'amount': float(rows[0].amount), 'date': when.isoformat(),
                'reason': '%d entries for the same member, amount and day' % len(rows)})

    by_type = defaultdict(list)
    year = _income_rows(today - timedelta(days=365))
    for row in year:
        by_type[row.transaction_type].append(row)
    for kind, rows in by_type.items():
        if len(rows) < MIN_SAMPLE:
            continue
        amounts = [float(r.amount) for r in rows]
        mid = median(amounts)
        spread = median([abs(a - mid) for a in amounts])
        if spread == 0:
            continue
        for row in rows:
            if row.transaction_date >= today - timedelta(days=30) and float(row.amount) > mid + 6 * spread:
                flags.append({
                    'kind': 'unusually_large', 'finance_ids': [row.id],
                    'amount': float(row.amount), 'date': row.transaction_date.isoformat(),
                    'reason': 'Much larger than the usual %s of about KES %d' % (kind, round(mid))})
    return jsonify({'flags': flags, 'checked': len(year),
                    'method': 'Rules: same member, amount and day; or far above the usual amount for '
                              'its type (needs %d earlier entries of that type).' % MIN_SAMPLE}), 200


def _month_totals(rows):
    totals = defaultdict(float)
    for row in rows:
        totals[(row.transaction_date.year, row.transaction_date.month)] += float(row.amount)
    return totals


@insights_bp.route('/forecast', methods=['GET'])
@jwt_required()
@roles_required(*FINANCE_READ)
def forecast():
    today = date.today()
    totals = _month_totals(_income_rows(today - timedelta(days=200)))
    this_month = (today.year, today.month)
    full = sorted(k for k in totals if k < this_month)[-3:]
    if len(full) < 3:
        return jsonify({'available': False,
                        'reason': 'Needs giving recorded in at least 3 full months before a forecast is shown.'}), 200
    values = [totals[k] for k in full]
    return jsonify({
        'available': True, 'expected': round(sum(values) / 3, 2),
        'low': round(min(values), 2), 'high': round(max(values), 2),
        'method': 'Average of the last 3 full months. It is a guide, not a promise.'}), 200


def _kes(value):
    return 'KES {:,}'.format(int(round(value)))


@insights_bp.route('/summary', methods=['GET'])
@jwt_required()
@roles_required(*FINANCE_READ)
def summary():
    """A short written summary built only from the figures in the ledger."""
    today = date.today()
    first = today.replace(day=1)
    last_month_end = first - timedelta(days=1)
    totals = _month_totals(_income_rows(last_month_end.replace(day=1)))
    now = totals.get((today.year, today.month), 0.0)
    before = totals.get((last_month_end.year, last_month_end.month), 0.0)
    lines = []
    if now or before:
        line = 'Giving so far this month: %s' % _kes(now)
        if before:
            change = (now - before) / before * 100
            line += ' (last month: %s, %+.0f%%).' % (_kes(before), change)
        else:
            line += '.'
        lines.append(line)
    lines.append('Active members: %d.' % scoped(Member).filter(
        Member.membership_status == 'active').count())
    if can_see_personal():
        quiet = len(care_candidates(4))
        if quiet:
            lines.append('%d members who attended regularly have not been seen in 4 weeks.' % quiet)
    return jsonify({'lines': lines, 'generated_for': today.isoformat()}), 200
