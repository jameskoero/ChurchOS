from datetime import date, timedelta

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import limiter
from ledger import audit
from models import db, Attendance, Member, SERVICE_TYPES
from tenancy import current_church_id, scoped, roles_required

checkin_bp = Blueprint('checkin', __name__)

STAFF = ('admin', 'pastor', 'secretary')
ROSTER_MAX = 5000
BATCH_MAX = 500


def _day(text):
    try:
        return date.fromisoformat(str(text))
    except (TypeError, ValueError):
        return None


@checkin_bp.route('/roster', methods=['GET'])
@jwt_required()
@roles_required(*STAFF)
def roster():
    """Active members (name and number only) for the offline check-in, plus who is already recorded."""
    church_id = current_church_id()
    members = scoped(Member).filter(Member.membership_status == 'active', Member.erased_at.is_(None)) \
        .order_by(Member.first_name, Member.last_name).limit(ROSTER_MAX + 1).all()
    truncated = len(members) > ROSTER_MAX
    members = members[:ROSTER_MAX]
    day = _day(request.args.get('service_date')) or date.today()
    service = request.args.get('service_type', '')
    query = scoped(Attendance).filter(Attendance.service_date == day)
    if service:
        query = query.filter(Attendance.service_type == service)
    already = sorted({row.member_id for row in query.all()})
    return jsonify({
        'members': [{'id': m.id, 'member_id': m.member_id, 'full_name': m.full_name} for m in members],
        'already': already, 'truncated': truncated, 'service_types': SERVICE_TYPES, 'church_id': church_id,
    }), 200


@checkin_bp.route('/sync', methods=['POST'])
@jwt_required()
@roles_required(*STAFF)
@limiter.limit('30 per minute')
def sync():
    """Save marks made offline. Safe to repeat: a mark already recorded is never saved twice."""
    data = request.get_json(silent=True)
    items = data.get('records') if isinstance(data, dict) else None
    if not isinstance(items, list) or not items:
        return jsonify({'error': 'No marks to save'}), 400
    if len(items) > BATCH_MAX:
        return jsonify({'error': 'Send at most %d marks at a time' % BATCH_MAX}), 400
    church_id = current_church_id()
    user_id = int(get_jwt_identity())

    ids = set()
    for item in items:
        if isinstance(item, dict) and isinstance(item.get('member_id'), int):
            ids.add(item['member_id'])
    valid = {m.id for m in scoped(Member).filter(Member.id.in_(list(ids) or [0]),
                                                 Member.erased_at.is_(None)).all()}
    latest = date.today() + timedelta(days=1)
    seen, done, rejected = set(), [], []
    created = duplicates = 0
    for item in items:
        item = item if isinstance(item, dict) else {}
        cid = str(item.get('client_id') or '')[:40]
        member_id, service, day = item.get('member_id'), item.get('service_type'), _day(item.get('service_date'))
        if not cid:
            rejected.append({'client_id': '', 'reason': 'missing id'})
            continue
        if member_id not in valid:
            rejected.append({'client_id': cid, 'reason': 'member not found'})
        elif service not in SERVICE_TYPES:
            rejected.append({'client_id': cid, 'reason': 'unknown service'})
        elif day is None or day > latest:
            rejected.append({'client_id': cid, 'reason': 'invalid date'})
        else:
            key = (member_id, service, day)
            exists = key in seen or scoped(Attendance).filter(
                Attendance.member_id == member_id, Attendance.service_type == service,
                Attendance.service_date == day).first() is not None
            if exists:
                duplicates += 1
            else:
                db.session.add(Attendance(church_id=church_id, member_id=member_id, service_type=service,
                                          service_date=day, recorded_by=user_id,
                                          notes='Marked offline and synced'))
                created += 1
            seen.add(key)
            done.append(cid)
    audit('checkin.sync', 'attendance', None,
          after={'created': created, 'duplicates': duplicates, 'rejected': len(rejected)})
    db.session.commit()
    return jsonify({'created': created, 'duplicates': duplicates, 'done': done, 'rejected': rejected}), 200
