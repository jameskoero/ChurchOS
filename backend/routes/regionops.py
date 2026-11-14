"""What a region leader (for example a Bishop) can do across the altars that accepted the invitation:
a printable report of totals, and SMS to members.

SMS reaches an altar's members only when that altar's own admin has switched on "regional messages".
It is off by default, and members who did not agree to SMS, or who replied STOP, are never messaged."""
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import limiter
from ledger import audit, live_money
from models import db, Attendance, Church, Finance, Member, SmsMessage
from routes.governance import _led_region, _leader_name, church_code
from routes.payments import normalize_phone
from services import sms
from tenancy import current_church_id, roles_required

regionops_bp = Blueprint('regionops', __name__)

MAX_DAYS = 400
MAX_RECIPIENTS = 300
CHUNK = 100


def _json():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _day(text, default):
    if not text:
        return default
    try:
        return date.fromisoformat(str(text))
    except ValueError:
        return None


@regionops_bp.route('/church/regional-sms', methods=['PUT'])
@jwt_required()
@roles_required('admin')
def set_regional_sms():
    """An altar's admin decides whether the regional leader may text its members."""
    allow = _json().get('allow')
    if not isinstance(allow, bool):
        return jsonify({'error': 'Say yes or no'}), 400
    church = db.session.get(Church, current_church_id())
    church.region_sms_ok = allow
    audit('governance.regional_sms', 'church', church.id, after={'allowed': allow})
    db.session.commit()
    return jsonify({'regional_sms': allow}), 200


@regionops_bp.route('/regions/mine/report', methods=['GET'])
@jwt_required()
def region_report():
    region = _led_region()
    if region is None:
        return jsonify({'error': 'You do not lead a region', 'code': 'NOT_LEADER'}), 403
    today = date.today()
    start = _day(request.args.get('from'), today - timedelta(days=30))
    end = _day(request.args.get('to'), today)
    if start is None or end is None:
        return jsonify({'error': 'Use dates like 2026-11-01'}), 400
    if end < start or (end - start).days > MAX_DAYS:
        return jsonify({'error': 'Choose a period of up to %d days, ending after it starts' % MAX_DAYS}), 400
    rows = []
    for c in Church.query.filter_by(region_id=region.id).order_by(Church.name).all():
        active = Member.query.filter(Member.church_id == c.id, Member.membership_status == 'active',
                                     Member.erased_at.is_(None))
        attended = Attendance.query.filter(Attendance.church_id == c.id, Attendance.service_date >= start,
                                           Attendance.service_date <= end)
        money = Finance.query.filter(Finance.church_id == c.id, live_money(),
                                     Finance.transaction_date >= start, Finance.transaction_date <= end).all()
        income = sum(float(f.amount) for f in money if f.transaction_type != 'expense')
        expense = sum(float(f.amount) for f in money if f.transaction_type == 'expense')
        rows.append({'id': c.id, 'name': c.name, 'code': church_code(c.id), 'is_seat': bool(c.is_seat),
                     'members': active.count(),
                     'new_members': active.filter(Member.date_joined >= start, Member.date_joined <= end).count(),
                     'attendance': attended.count(),
                     'people_attending': attended.with_entities(Attendance.member_id).distinct().count(),
                     'income': round(income, 2), 'expense': round(expense, 2), 'net': round(income - expense, 2)})
    keys = ('members', 'new_members', 'attendance', 'people_attending', 'income', 'expense', 'net')
    audit('governance.region_report', 'region', region.id,
          after={'from': start.isoformat(), 'to': end.isoformat(), 'churches': len(rows)})
    db.session.commit()
    return jsonify({'region': region.name, 'leader': _leader_name(region), 'from': start.isoformat(),
                    'to': end.isoformat(), 'churches': rows,
                    'totals': {k: round(sum(r[k] for r in rows), 2) for k in keys},
                    'generated_at': datetime.utcnow().isoformat(timespec='seconds') + 'Z'}), 200


def _audience(region):
    """Members the leader may text: agreed to SMS, active, valid number, not STOP, in an altar that allows it."""
    from routes.sms import _opted_out
    churches = {c.id: c for c in Church.query.filter_by(region_id=region.id).all()
                if c.is_seat or c.region_sms_ok}
    if not churches:
        return [], {}, 0
    members = Member.query.filter(Member.church_id.in_(list(churches)), Member.membership_status == 'active',
                                  Member.erased_at.is_(None), Member.sms_ok.is_(True)).order_by(Member.id).all()
    candidates = [(m, normalize_phone(m.phone)) for m in members]
    blocked = _opted_out({p for _, p in candidates})
    seen, out, per, no_phone = set(), [], defaultdict(int), 0
    for member, phone in candidates:
        if not phone:
            no_phone += 1
        elif phone in blocked or phone in seen:
            continue
        else:
            seen.add(phone)
            out.append((member, '+' + phone))
            per[member.church_id] += 1
    return out, {churches[k].name: v for k, v in per.items()}, no_phone


def _sms_plan():
    region = _led_region()
    if region is None:
        return None, (jsonify({'error': 'You do not lead a region', 'code': 'NOT_LEADER'}), 403)
    text = sms.clean_text(_json().get('message'))
    if not text:
        return None, (jsonify({'error': 'Write a message first'}), 400)
    if '{first_name}' in text:
        return None, (jsonify({'error': 'Regional messages go to many churches and cannot use {first_name}.',
                               'code': 'NO_NAMES'}), 400)
    if sms.parts(text) > sms.MAX_PARTS:
        return None, (jsonify({'error': 'That message is longer than %d SMS parts. Shorten it.' % sms.MAX_PARTS,
                               'code': 'TOO_LONG'}), 400)
    people, per, no_phone = _audience(region)
    if not people:
        return None, (jsonify({'error': 'Nobody to send to yet. An altar must switch on regional messages on its '
                                        'Structure page, and its members must have agreed to SMS.',
                               'code': 'NO_RECIPIENTS'}), 400)
    if len(people) > MAX_RECIPIENTS:
        return None, (jsonify({'error': 'More than %d members would receive this. Regional messages are limited '
                                        'to %d at a time for now.' % (MAX_RECIPIENTS, MAX_RECIPIENTS),
                               'code': 'TOO_MANY', 'recipients': len(people)}), 400)
    from routes.sms import _used, _limit
    seat = db.session.get(Church, current_church_id())
    used, limit_total = _used(seat.id), _limit(seat)
    each = sms.parts(text)
    return {'region': region, 'text': text, 'people': people, 'per': per, 'each': each,
            'need': each * len(people), 'used': used, 'limit': limit_total, 'no_phone': no_phone}, None


@regionops_bp.route('/regions/mine/sms/preview', methods=['POST'])
@jwt_required()
def region_sms_preview():
    plan, problem = _sms_plan()
    if problem:
        return problem
    return jsonify({'recipients': len(plan['people']), 'by_church': plan['per'], 'parts_each': plan['each'],
                    'total_parts': plan['need'], 'used': plan['used'], 'limit': plan['limit'],
                    'remaining_after': plan['limit'] - plan['used'] - plan['need'],
                    'skipped_no_phone': plan['no_phone'], 'sample': plan['text']}), 200


@regionops_bp.route('/regions/mine/sms/send', methods=['POST'])
@jwt_required()
@limiter.limit('5 per minute')
def region_sms_send():
    config = sms.setup_status()
    if not config['configured']:
        return jsonify({'error': 'SMS is not set up yet', 'code': 'SMS_NOT_CONFIGURED',
                        'missing': config['missing']}), 503
    plan, problem = _sms_plan()
    if problem:
        return problem
    people = plan['people']
    if _json().get('confirm_count') != len(people):
        return jsonify({'error': 'The audience changed. Preview again before sending.', 'code': 'CHANGED',
                        'recipients': len(people)}), 409
    if plan['used'] + plan['need'] > plan['limit']:
        return jsonify({'error': "This would pass your plan's SMS limit for the month (%d of %d used)."
                                 % (plan['used'], plan['limit']), 'code': 'SMS_LIMIT'}), 402
    seat_id, user_id, batch = current_church_id(), int(get_jwt_identity()), uuid.uuid4().hex
    accepted = failed = 0
    for n in range(0, len(people), CHUNK):
        group = people[n:n + CHUNK]
        try:
            results = sms.send_batch([p for _, p in group], plan['text'])
        except sms.SmsError as err:
            results = [{'phone': p, 'status': 'failed', 'detail': str(err)[:120], 'message_id': '', 'cost': ''}
                       for _, p in group]
        by_phone = {r['phone']: r for r in results}
        for _, phone in group:
            r = by_phone.get(phone) or {'status': 'failed', 'detail': 'No result for this number',
                                        'message_id': '', 'cost': ''}
            # Paid for by the seat church; the member link is left empty so other altars' members stay private there.
            db.session.add(SmsMessage(church_id=seat_id, member_id=None, batch_id=batch, phone=phone,
                                      body=plan['text'][:480], status=r['status'],
                                      provider_id=r.get('message_id') or None, detail=r.get('detail') or None,
                                      segments=plan['each'], cost=r.get('cost') or None, created_by=user_id))
            accepted, failed = (accepted + 1, failed) if r['status'] == 'sent' else (accepted, failed + 1)
        db.session.commit()
    region = plan['region']
    audit('governance.region_sms', 'region', region.id,
          after={'batch': batch, 'recipients': len(people), 'accepted': accepted, 'failed': failed,
                 'parts': plan['need']})
    # Each altar's own log shows that its members were messaged by the leader.
    for church in Church.query.filter_by(region_id=region.id).all():
        count = plan['per'].get(church.name)
        if count:
            audit('governance.region_sms_to_members', 'region', region.id, church_id=church.id,
                  after={'by': _leader_name(region), 'members': count, 'batch': batch})
    db.session.commit()
    from routes.sms import _used
    return jsonify({'batch_id': batch, 'accepted': accepted, 'failed': failed, 'parts': plan['need'],
                    'remaining': plan['limit'] - _used(seat_id)}), 200
