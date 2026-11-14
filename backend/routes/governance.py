"""Denominations, regions and altars.

A denomination carries the words its churches use (Region, Altar, Bishop, Senior Pastor ...).
A region groups churches (altars) under one leader. A church joins only by accepting an invitation.
The region leader sees every altar's totals and member list, read-only, and each look is logged
in that altar's own activity log."""
import re
from datetime import date, datetime, timedelta

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from ledger import audit, live_money
from models import db, Attendance, Church, Denomination, Finance, Member, Region, RegionInvite, User
from tenancy import current_church_id, is_owner, roles_required

governance_bp = Blueprint('governance', __name__)

LABELS = ('region_label', 'unit_label', 'region_leader_title', 'unit_leader_title', 'seat_label')
GENERIC = {'region_label': 'Region', 'unit_label': 'Church', 'region_leader_title': 'Regional leader',
           'unit_leader_title': 'Pastor', 'seat_label': 'Headquarters church'}
REPENTANCE = {'region_label': 'Region', 'unit_label': 'Altar', 'region_leader_title': 'Bishop',
              'unit_leader_title': 'Senior Pastor', 'seat_label': 'Main Altar'}
# Starting list: denominations confirmed to exist in Kenya from public sources (Nov 2026).
# Their own structures are not assumed: each gets the generic wording until its leaders set theirs.
SEED = [
    ('Ministry of Repentance and Holiness', 'MRH', REPENTANCE),
    ('Power of Jesus Around the World Church', 'PJAW', GENERIC),
    ('Voice of Salvation and Healing Church', 'VOSH', GENERIC),
    ('Deliverance Church Kenya', 'DC', GENERIC),
    ('Pentecostal Assemblies of God', 'PAG', GENERIC),
    ('Kenya Assemblies of God', 'KAG', GENERIC),
    ('Full Gospel Churches of Kenya', 'FGCK', GENERIC),
    ('Redeemed Gospel Church of Kenya', 'RGC', GENERIC),
    ('Christ Is the Answer Ministries', 'CITAM', GENERIC),
    ('African Independent Pentecostal Church of Africa', 'AIPCA', GENERIC),
    ('Elim Church', '', GENERIC),
    ('Worldwide Gospel Church of Kenya', '', GENERIC),
]
APPROVED = ('listed', 'verified')
CODE = re.compile(r'^COS-(\d{4,})$', re.IGNORECASE)


def seed_denominations(database):
    """Add any missing starting denominations. Safe to run on every start, and by two workers at once."""
    try:
        have = {d.name.lower() for d in Denomination.query.all()}
        for name, short, labels in SEED:
            if name.lower() not in have:
                database.session.add(Denomination(name=name, short_name=short or None, status='listed', **labels))
        database.session.commit()
    except IntegrityError:
        database.session.rollback()


def _json():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _me():
    return db.session.get(User, int(get_jwt_identity()))


def _church():
    return db.session.get(Church, current_church_id())


def church_code(church_id):
    return 'COS-%04d' % church_id


def _leader_name(region):
    user = db.session.get(User, region.leader_user_id) if region.leader_user_id else None
    return (user.full_name or user.username) if user else ''


def _region_view(region):
    seat = db.session.get(Church, region.seat_church_id)
    return {'id': region.id, 'name': region.name, 'leader': _leader_name(region),
            'seat_church': seat.name if seat else '', 'seat_church_id': region.seat_church_id,
            'denomination_id': region.denomination_id}


@governance_bp.route('/denominations', methods=['GET'])
@jwt_required()
def denominations():
    q = request.args.get('search', '').strip()[:80]
    query = Denomination.query.filter(or_(Denomination.status.in_(APPROVED),
                                          (Denomination.status == 'pending') &
                                          (Denomination.requested_by_church_id == current_church_id())))
    for word in q.split()[:5]:
        like = '%' + word + '%'
        query = query.filter(or_(Denomination.name.ilike(like), Denomination.short_name.ilike(like)))
    rows = query.order_by(Denomination.name).limit(60).all()
    return jsonify({'denominations': [d.to_dict() for d in rows]}), 200


@governance_bp.route('/denominations/request', methods=['POST'])
@jwt_required()
@roles_required('admin')
def request_denomination():
    """'My denomination is not listed': record the name, use it straight away, and send it for approval."""
    name = re.sub(r'\s+', ' ', str(_json().get('name') or '')).strip()
    if len(name) < 3 or len(name) > 160:
        return jsonify({'error': 'Type the full name of your denomination or ministry (3 to 160 characters)'}), 400
    church = _church()
    existing = Denomination.query.filter(func.lower(Denomination.name) == name.lower()).first()
    if existing is not None and existing.status == 'rejected':
        existing = None
    if existing is not None and existing.status == 'pending' and existing.requested_by_church_id != church.id:
        existing = None
    if existing is None:
        existing = Denomination(name=name, status='pending', requested_by_church_id=church.id, **GENERIC)
        db.session.add(existing)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            return jsonify({'error': 'That name is already waiting for approval. Search for it, or try again later.',
                            'code': 'TAKEN'}), 409
    problem = _set_denomination(church, existing)
    if problem:
        return problem
    audit('governance.denomination_request', 'denomination', existing.id, after={'name': name})
    db.session.commit()
    return jsonify({'denomination': existing.to_dict()}), 201


def _set_denomination(church, denomination):
    if church.region_id:
        region = db.session.get(Region, church.region_id)
        if region and region.denomination_id and region.denomination_id != denomination.id:
            return jsonify({'error': 'This church is in a region of another denomination. Leave the region first.',
                            'code': 'IN_REGION'}), 409
    church.denomination_id = denomination.id
    church.denomination = denomination.name[:100]
    return None


@governance_bp.route('/church', methods=['GET'])
@jwt_required()
def my_church():
    church = _church()
    denomination = db.session.get(Denomination, church.denomination_id) if church.denomination_id else None
    region = db.session.get(Region, church.region_id) if church.region_id else None
    led = Region.query.filter_by(seat_church_id=church.id).first()
    invites = RegionInvite.query.filter_by(church_id=church.id, status='pending').all()
    return jsonify({
        'church': church.name, 'church_code': church_code(church.id), 'is_seat': bool(church.is_seat),
        'regional_sms': bool(church.region_sms_ok),
        'denomination': denomination.to_dict() if denomination else None,
        'labels': denomination.labels() if denomination else dict(GENERIC),
        'region': _region_view(region) if region else None,
        'leads_region': bool(led and led.leader_user_id == int(get_jwt_identity())),
        'invites': [dict(i.to_dict(), region=_region_view(db.session.get(Region, i.region_id))) for i in invites],
    }), 200


@governance_bp.route('/church', methods=['PUT'])
@jwt_required()
@roles_required('admin')
def choose_denomination():
    church = _church()
    denomination = db.session.get(Denomination, int(_json().get('denomination_id') or 0))
    allowed = denomination is not None and (denomination.status in APPROVED or (
        denomination.status == 'pending' and denomination.requested_by_church_id == church.id))
    if not allowed:
        return jsonify({'error': 'Choose a denomination from the list', 'code': 'NOT_FOUND'}), 404
    problem = _set_denomination(church, denomination)
    if problem:
        return problem
    audit('governance.denomination_set', 'church', church.id, after={'denomination': denomination.name})
    db.session.commit()
    return jsonify({'denomination': denomination.to_dict()}), 200


# ---------- platform owner: approve "Other" requests and set wording ----------

def _owner_only():
    if not is_owner():
        return jsonify({'error': 'Only the platform owner can do this', 'code': 'FORBIDDEN'}), 403
    return None


@governance_bp.route('/denominations/pending', methods=['GET'])
@jwt_required()
def pending():
    blocked = _owner_only()
    if blocked:
        return blocked
    rows = Denomination.query.filter_by(status='pending').order_by(Denomination.id).all()
    return jsonify({'denominations': [d.to_dict() for d in rows]}), 200


@governance_bp.route('/denominations/<int:denomination_id>', methods=['PUT'])
@jwt_required()
def review(denomination_id):
    """Owner approves, verifies, rejects, renames, or sets a denomination's wording."""
    blocked = _owner_only()
    if blocked:
        return blocked
    d = db.session.get(Denomination, denomination_id)
    if d is None:
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404
    data = _json()
    status = data.get('status')
    if status is not None and status not in ('listed', 'verified', 'rejected'):
        return jsonify({'error': 'Status must be listed, verified or rejected'}), 400
    if 'name' in data:
        name = re.sub(r'\s+', ' ', str(data.get('name') or '')).strip()
        if len(name) < 3 or len(name) > 160:
            return jsonify({'error': 'Names are 3 to 160 characters'}), 400
        d.name = name
    if 'short_name' in data:
        d.short_name = (str(data.get('short_name') or '').strip()[:20]) or None
    for key in LABELS:
        if key in data:
            value = str(data.get(key) or '').strip()[:40]
            if not value:
                return jsonify({'error': 'Wording cannot be empty'}), 400
            setattr(d, key, value)
    if status:
        d.status = status
        if status == 'rejected':
            for church in Church.query.filter_by(denomination_id=d.id).all():
                church.denomination_id, church.denomination = None, None
    audit('governance.denomination_review', 'denomination', d.id, after={'status': d.status, 'name': d.name})
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Another denomination already has that name', 'code': 'TAKEN'}), 409
    return jsonify({'denomination': d.to_dict()}), 200


# ---------- regions ----------

def _led_region():
    """The region the signed-in user leads from this church, or None."""
    region = Region.query.filter_by(seat_church_id=current_church_id()).first()
    if region is None or region.leader_user_id != int(get_jwt_identity()):
        return None
    return region


@governance_bp.route('/regions', methods=['POST'])
@jwt_required()
@roles_required('admin')
def create_region():
    """Create a region seated at this church, led by the signed-in admin (for example the Bishop)."""
    church = _church()
    if not church.denomination_id:
        return jsonify({'error': 'Choose your denomination first', 'code': 'NO_DENOMINATION'}), 400
    if church.region_id or Region.query.filter_by(seat_church_id=church.id).first():
        return jsonify({'error': 'This church is already in a region', 'code': 'IN_REGION'}), 409
    name = re.sub(r'\s+', ' ', str(_json().get('name') or '')).strip()
    if len(name) < 3 or len(name) > 120:
        return jsonify({'error': 'Give the region a name, for example Migosi Region'}), 400
    region = Region(name=name, denomination_id=church.denomination_id, seat_church_id=church.id,
                    leader_user_id=int(get_jwt_identity()))
    db.session.add(region)
    db.session.flush()
    church.region_id, church.is_seat = region.id, True
    audit('governance.region_create', 'region', region.id, after={'name': name})
    db.session.commit()
    return jsonify({'region': _region_view(region)}), 201


@governance_bp.route('/regions/mine', methods=['GET'])
@jwt_required()
def my_region():
    """For the region leader: every church in the region with its totals, and the invitations sent."""
    region = _led_region()
    if region is None:
        return jsonify({'error': 'You do not lead a region', 'code': 'NOT_LEADER'}), 403
    since = date.today() - timedelta(days=30)
    churches = Church.query.filter_by(region_id=region.id).order_by(Church.name).all()
    rows = []
    for c in churches:
        active = Member.query.filter(Member.church_id == c.id, Member.membership_status == 'active',
                                     Member.erased_at.is_(None))
        attended = Attendance.query.filter(Attendance.church_id == c.id, Attendance.service_date >= since)
        giving = Finance.query.filter(Finance.church_id == c.id, live_money(), Finance.transaction_type != 'expense',
                                      Finance.transaction_date >= since).all()
        rows.append({'id': c.id, 'name': c.name, 'code': church_code(c.id), 'is_seat': bool(c.is_seat),
                     'members': active.count(),
                     'new_members_30d': active.filter(Member.date_joined >= since).count(),
                     'attendance_30d': attended.count(),
                     'people_attending_30d': attended.with_entities(Attendance.member_id).distinct().count(),
                     'giving_30d': round(sum(float(f.amount) for f in giving), 2),
                     'regional_sms': bool(c.region_sms_ok)})
    invites = RegionInvite.query.filter_by(region_id=region.id).order_by(RegionInvite.id.desc()).limit(50).all()
    return jsonify({
        'region': _region_view(region), 'churches': rows,
        'totals': {k: round(sum(r[k] for r in rows), 2) for k in
                   ('members', 'new_members_30d', 'attendance_30d', 'people_attending_30d', 'giving_30d')},
        'invites': [dict(i.to_dict(), church=(db.session.get(Church, i.church_id).name
                                               if db.session.get(Church, i.church_id) else '')) for i in invites],
    }), 200


@governance_bp.route('/regions/mine/invites', methods=['POST'])
@jwt_required()
def invite():
    region = _led_region()
    if region is None:
        return jsonify({'error': 'You do not lead a region', 'code': 'NOT_LEADER'}), 403
    found = CODE.match(str(_json().get('code') or '').strip())
    target = db.session.get(Church, int(found.group(1))) if found else None
    if target is None:
        return jsonify({'error': 'No church has that code. Ask its admin for the code shown on their Structure page.',
                        'code': 'NOT_FOUND'}), 404
    if target.region_id:
        return jsonify({'error': 'That church is already in a region', 'code': 'IN_REGION'}), 409
    if target.denomination_id and target.denomination_id != region.denomination_id:
        return jsonify({'error': 'That church belongs to another denomination', 'code': 'OTHER_DENOMINATION'}), 409
    if RegionInvite.query.filter_by(region_id=region.id, church_id=target.id, status='pending').first():
        return jsonify({'error': 'An invitation is already waiting for that church', 'code': 'PENDING'}), 409
    row = RegionInvite(region_id=region.id, church_id=target.id, status='pending', invited_by=int(get_jwt_identity()))
    db.session.add(row)
    db.session.flush()
    audit('governance.invite', 'region', region.id, after={'church': target.name})
    audit('governance.invited', 'region', region.id, church_id=target.id, after={'region': region.name})
    db.session.commit()
    return jsonify({'invite': row.to_dict(), 'church': target.name}), 201


@governance_bp.route('/invites/<int:invite_id>/<action>', methods=['POST'])
@jwt_required()
@roles_required('admin')
def answer_invite(invite_id, action):
    """The invited church's admin accepts or declines. Accepting gives the region leader read access."""
    row = db.session.get(RegionInvite, invite_id)
    church = _church()
    if row is None or row.church_id != church.id or action not in ('accept', 'decline'):
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404
    if row.status != 'pending':
        return jsonify({'error': 'This invitation was already answered', 'code': 'HANDLED'}), 409
    region = db.session.get(Region, row.region_id)
    if action == 'accept':
        if church.region_id:
            return jsonify({'error': 'This church is already in a region', 'code': 'IN_REGION'}), 409
        if church.denomination_id and church.denomination_id != region.denomination_id:
            return jsonify({'error': 'This church belongs to another denomination', 'code': 'OTHER_DENOMINATION'}), 409
        church.region_id = region.id
        if not church.denomination_id and region.denomination_id:
            d = db.session.get(Denomination, region.denomination_id)
            church.denomination_id, church.denomination = d.id, d.name[:100]
    row.status = 'accepted' if action == 'accept' else 'declined'
    row.responded_by, row.responded_at = int(get_jwt_identity()), datetime.utcnow()
    audit('governance.invite_' + row.status, 'region', region.id, after={'region': region.name})
    audit('governance.invite_' + row.status, 'region', region.id, church_id=region.seat_church_id,
          after={'church': church.name})
    db.session.commit()
    return jsonify({'invite': row.to_dict()}), 200


@governance_bp.route('/church/leave', methods=['POST'])
@jwt_required()
@roles_required('admin')
def leave_region():
    church = _church()
    if not church.region_id:
        return jsonify({'error': 'This church is not in a region'}), 400
    if church.is_seat:
        return jsonify({'error': 'The seat of a region cannot leave its own region', 'code': 'SEAT'}), 409
    region = db.session.get(Region, church.region_id)
    church.region_id = None
    audit('governance.leave', 'region', region.id, after={'region': region.name})
    audit('governance.leave', 'region', region.id, church_id=region.seat_church_id, after={'church': church.name})
    db.session.commit()
    return jsonify({'message': 'Left the region'}), 200


@governance_bp.route('/regions/mine/churches/<int:church_id>/remove', methods=['POST'])
@jwt_required()
def remove_church(church_id):
    region = _led_region()
    church = db.session.get(Church, church_id)
    if region is None or church is None or church.region_id != region.id:
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404
    if church.is_seat:
        return jsonify({'error': 'The seat stays in its region', 'code': 'SEAT'}), 409
    church.region_id = None
    audit('governance.removed', 'region', region.id, church_id=church.id, after={'region': region.name})
    audit('governance.remove', 'region', region.id, after={'church': church.name})
    db.session.commit()
    return jsonify({'message': 'Removed from the region'}), 200


@governance_bp.route('/regions/mine/churches/<int:church_id>/members', methods=['GET'])
@jwt_required()
def region_members(church_id):
    """Read-only member list of one church in the leader's region. Logged in that church's activity log."""
    region = _led_region()
    church = db.session.get(Church, church_id)
    if region is None or church is None or church.region_id != region.id:
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404
    page = max(1, request.args.get('page', 1, type=int))
    query = Member.query.filter(Member.church_id == church.id, Member.erased_at.is_(None))
    for word in request.args.get('search', '').strip()[:60].split()[:4]:
        like = '%' + word + '%'
        query = query.filter(or_(Member.first_name.ilike(like), Member.last_name.ilike(like),
                                 Member.member_id.ilike(like)))
    total = query.count()
    rows = query.order_by(Member.first_name, Member.last_name).offset((page - 1) * 50).limit(50).all()
    audit('governance.view_members', 'church', church.id, church_id=church.id,
          after={'by': _leader_name(region), 'page': page})
    db.session.commit()
    return jsonify({'church': church.name, 'total': total, 'page': page, 'members': [{
        'member_id': m.member_id, 'full_name': m.full_name, 'phone': m.phone, 'email': m.email,
        'gender': m.gender, 'cell_group': m.cell_group, 'membership_status': m.membership_status,
        'date_joined': m.date_joined.isoformat() if m.date_joined else None} for m in rows]}), 200
