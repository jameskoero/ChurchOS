from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from tenancy import (current_church_id, scoped, owned_or_404, tquery,
                     page_size, roles_required, can_see_money, can_see_personal,
                     FINANCE_READ)
from models import db, Member, Attendance, Finance, Event, User, PaymentEvent
from datetime import date, datetime, timedelta
from sqlalchemy import func
from ledger import live_money
from routes.insights import care_candidates

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_stats():
    today = date.today()
    first_of_month = today.replace(day=1)
    first_of_year = today.replace(month=1, day=1)

    # Member stats
    total_members = scoped(Member).filter_by(membership_status='active').count()
    new_this_month = scoped(Member).filter(
        Member.date_joined >= first_of_month,
        Member.membership_status == 'active'
    ).count()

    # Attendance - last Sunday
    last_sunday = today - timedelta(days=(today.weekday() + 1) % 7)
    last_service = scoped(Attendance).filter(
        Attendance.service_date == last_sunday,
        Attendance.service_type == 'Sunday Morning'
    ).count()

    # Finance
    income_types = ['tithe', 'offering', 'donation', 'project_fund', 'other']
    monthly_income = tquery(Finance, can_see_money())(func.sum(Finance.amount)).filter(
        live_money(),
        Finance.transaction_type.in_(income_types),
        Finance.transaction_date >= first_of_month
    ).scalar() or 0

    monthly_expense = tquery(Finance, can_see_money())(func.sum(Finance.amount)).filter(
        live_money(),
        Finance.transaction_type == 'expense',
        Finance.transaction_date >= first_of_month
    ).scalar() or 0

    annual_income = tquery(Finance, can_see_money())(func.sum(Finance.amount)).filter(
        live_money(),
        Finance.transaction_type.in_(income_types),
        Finance.transaction_date >= first_of_year
    ).scalar() or 0

    # Upcoming events
    upcoming_events = scoped(Event).filter(
        Event.start_date >= datetime.utcnow(),
        Event.status != 'cancelled'
    ).order_by(Event.start_date).limit(5).all()

    # Attendance trend (last 8 Sundays)
    trend_data = tquery(Attendance)(
        Attendance.service_date,
        func.count(Attendance.id).label('count')
    ).filter(
        Attendance.service_type == 'Sunday Morning',
        Attendance.service_date >= today - timedelta(weeks=8)
    ).group_by(Attendance.service_date).order_by(Attendance.service_date).all()

    # Monthly finance chart (last 6 months)
    six_months_ago = today - timedelta(days=180)
    monthly_finance = tquery(Finance, can_see_money())(
        func.extract('year', Finance.transaction_date).label('year'),
        func.extract('month', Finance.transaction_date).label('month'),
        Finance.transaction_type,
        func.sum(Finance.amount).label('total')
    ).filter(
        live_money(),
        Finance.transaction_date >= six_months_ago
    ).group_by('year', 'month', Finance.transaction_type).all()


    # What needs a person's attention today, only for roles allowed to act on it.
    attention = []
    if can_see_money():
        waiting = scoped(Finance).filter(live_money(), Finance.verified.isnot(True)).count()
        if waiting:
            attention.append({'key': 'verify', 'count': waiting, 'tone': 'amber', 'to': '/finance',
                              'label': 'transactions are waiting for a second person to verify'})
    if get_jwt().get('role') in ('admin', 'treasurer'):
        unmatched = scoped(PaymentEvent).filter(PaymentEvent.status == 'unmatched').count()
        if unmatched:
            attention.append({'key': 'inbox', 'count': unmatched, 'tone': 'amber', 'to': '/payments',
                              'label': 'Paybill payments need a member'})
    if can_see_personal():
        quiet = len(care_candidates(4))
        if quiet:
            attention.append({'key': 'care', 'count': quiet, 'tone': 'rose', 'to': '/members',
                              'label': 'regular members have not attended in 4 weeks'})
        no_consent = scoped(Member).filter(Member.consent_at.is_(None),
                                           Member.membership_status == 'active').count()
        if no_consent:
            attention.append({'key': 'consent', 'count': no_consent, 'tone': 'blue', 'to': '/members',
                              'label': 'members have no consent on record'})

    return jsonify({
        'members': {
            'total': total_members,
            'new_this_month': new_this_month,
            'male': scoped(Member).filter_by(gender='Male', membership_status='active').count(),
            'female': scoped(Member).filter_by(gender='Female', membership_status='active').count()
        },
        'attendance': {
            'last_service': last_service,
            'this_month': scoped(Attendance).filter(
                Attendance.service_date >= first_of_month
            ).count()
        },
        'finance': {
            'monthly_income': float(monthly_income),
            'monthly_expense': float(monthly_expense),
            'monthly_net': float(monthly_income) - float(monthly_expense),
            'annual_income': float(annual_income)
        },
        'upcoming_events': [e.to_dict() for e in upcoming_events],
        'attendance_trend': [
            {'date': str(r.service_date), 'count': r.count}
            for r in trend_data
        ],
        'finance_trend': [
            {
                'year': int(r.year),
                'month': int(r.month),
                'type': r.transaction_type,
                'total': float(r.total)
            } for r in monthly_finance
        ],
        'total_users': scoped(User).filter_by(is_active=True).count(),
        'attention': attention
    }), 200
