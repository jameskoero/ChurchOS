import hmac
import os
import re
import uuid
from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_

from extensions import limiter
from ledger import audit
from models import db, Church, Member, SmsMessage, SmsOptOut
from routes.payments import normalize_phone
from services import sms
from tenancy import current_church_id, scoped, owned_or_404, roles_required

sms_bp = Blueprint('sms', __name__)

STAFF = ('admin', 'pastor', 'secretary')
MAX_RECIPIENTS = 300
MAX_PERSONAL = 40
MAX_TYPED = 20
PIECES = re.compile(r'[,;\n]+')
CHUNK = 100
STOP_WORDS = ('STOP', 'UNSUBSCRIBE', 'OPTOUT', 'CANCEL')


def _json():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _mask(phone):
    if not phone or phone == 'erased':
        return phone or ''
    return phone[:4] + ' *** ***' + phone[-3:]


def _month_start():
    now = datetime.utcnow()
    return datetime(now.year, now.month, 1)


def _used(church_id):
    rows = SmsMessage.query.filter(SmsMessage.church_id == church_id, SmsMessage.created_at >= _month_start(),
                                   SmsMessage.status != 'failed').all()
    return sum(r.segments or 0 for r in rows)


def _limit(church):
    from routes.billing import _owner_church_ids
    if church.id in _owner_church_ids():
        return sms.COMPLIMENTARY_PARTS
    return sms.MONTHLY_PARTS.get(church.subscription_plan or 'trial', sms.MONTHLY_PARTS['trial'])


def _opted_out(phones):
    """Which of these numbers (2547..., no plus) replied STOP."""
    phones = {p for p in phones if p}
    if not phones:
        return set()
    return {r.phone for r in SmsOptOut.query.filter(SmsOptOut.phone.in_(list(phones))).all()}


def _recipients(church_id, audience, member_ids):
    query = scoped(Member).filter(Member.membership_status == 'active', Member.erased_at.is_(None),
                                  Member.sms_ok.is_(True))
    if audience == 'selected':
        query = query.filter(Member.id.in_(list(member_ids) or [0]))
    candidates = [(m, normalize_phone(m.phone)) for m in query.order_by(Member.id).all()]
    blocked = _opted_out({p for _, p in candidates})
    seen, out, no_phone = set(), [], 0
    for member, phone in candidates:
        if not phone:
            no_phone += 1
        elif phone in blocked or phone in seen:
            continue
        else:
            seen.add(phone)
            out.append((member, '+' + phone))
    return out, no_phone


def _typed(raw):
    """Numbers keyed in by hand. Returns (people, unreadable entries, how many replied STOP)."""
    pieces = raw if isinstance(raw, list) else PIECES.split(str(raw or ''))
    valid, bad, seen = [], [], set()
    for piece in [str(p).strip() for p in pieces][:100]:
        if not piece:
            continue
        tokens = [piece] if (normalize_phone(piece) or len(piece.split()) < 2) else piece.split()
        for token in tokens:
            got = normalize_phone(token)
            if got is None:
                bad.append(token[:20])
            elif got not in seen:
                seen.add(got)
                valid.append(got)
    blocked = _opted_out(set(valid))
    people = [(None, '+' + p) for p in valid if p not in blocked]
    return people, bad[:10], len(valid) - len(people)


def _plan(data):
    """Validate the request and work out exactly who gets what. Returns (plan, error response)."""
    text = sms.clean_text(data.get('message'))
    if not text:
        return None, (jsonify({'error': 'Write a message first'}), 400)
    audience = data.get('audience')
    if audience not in ('all', 'selected', 'numbers'):
        return None, (jsonify({'error': 'Choose who should receive it'}), 400)
    personal = '{first_name}' in text
    invalid, opted_out = [], 0
    if audience == 'numbers':
        if personal:
            return None, (jsonify({'error': 'Typed numbers have no names. Remove {first_name} from the message.',
                                   'code': 'NO_NAMES'}), 400)
        if data.get('asked') is not True:
            return None, (jsonify({'error': 'Tick the box to confirm these people asked to receive your message.',
                                   'code': 'NEEDS_CONFIRMATION'}), 400)
        people, invalid, opted_out = _typed(data.get('numbers'))
        no_phone = 0
        if not people:
            return None, (jsonify({'error': 'No valid number to send to. Use Kenyan numbers like 0712 345 678.'
                                            + (' Some numbers replied STOP and are blocked.' if opted_out else ''),
                                   'code': 'NO_RECIPIENTS', 'invalid_numbers': invalid}), 400)
        if len(people) > MAX_TYPED:
            return None, (jsonify({'error': 'Type at most %d numbers at a time' % MAX_TYPED, 'code': 'TOO_MANY'}), 400)
    else:
        ids = data.get('member_ids') if isinstance(data.get('member_ids'), list) else []
        ids = [i for i in ids if isinstance(i, int)][:2000]
        if audience == 'selected' and not ids:
            return None, (jsonify({'error': 'Choose at least one member'}), 400)
        people, no_phone = _recipients(current_church_id(), audience, ids)
        if not people:
            return None, (jsonify({'error': 'Nobody to send to. Members must have a valid phone number and have '
                                            'agreed to SMS.', 'code': 'NO_RECIPIENTS'}), 400)
    if len(people) > MAX_RECIPIENTS or (personal and len(people) > MAX_PERSONAL):
        limit = MAX_PERSONAL if personal else MAX_RECIPIENTS
        return None, (jsonify({'error': 'Send to at most %d members at a time%s' % (
            limit, ' (remove {first_name} to send to more)' if personal else ''), 'code': 'TOO_MANY'}), 400)
    items = []
    for member, phone in people:
        body = text.replace('{first_name}', (member.first_name or '').strip()[:30]) if personal and member else text
        if sms.parts(body) > sms.MAX_PARTS:
            return None, (jsonify({'error': 'That message is longer than %d SMS parts. Shorten it.' % sms.MAX_PARTS,
                                   'code': 'TOO_LONG'}), 400)
        items.append({'member': member, 'phone': phone, 'body': body, 'parts': sms.parts(body)})
    church = db.session.get(Church, current_church_id())
    used, limit_total = _used(church.id), _limit(church)
    need = sum(i['parts'] for i in items)
    return {'items': items, 'personal': personal, 'need': need, 'used': used, 'limit': limit_total,
            'no_phone': no_phone, 'text': text, 'invalid': invalid, 'opted_out': opted_out,
            'typed': audience == 'numbers'}, None


@sms_bp.route('/setup', methods=['GET'])
@jwt_required()
@roles_required(*STAFF)
def setup():
    return jsonify(sms.setup_status()), 200


@sms_bp.route('/audience', methods=['GET'])
@jwt_required()
@roles_required(*STAFF)
def audience():
    """Members and whether each has agreed to SMS. Phone numbers are never returned."""
    q = request.args.get('search', '').strip()[:60]
    base = scoped(Member).filter(Member.membership_status == 'active', Member.erased_at.is_(None))
    query = base
    for word in q.split()[:4]:
        like = '%' + word + '%'
        query = query.filter(or_(Member.first_name.ilike(like), Member.last_name.ilike(like),
                                 Member.member_id.ilike(like)))
    rows = query.order_by(Member.first_name, Member.last_name).limit(50).all()
    agreed = base.filter(Member.sms_ok.is_(True)).count()
    return jsonify({
        'members': [{'id': m.id, 'member_id': m.member_id, 'full_name': m.full_name,
                     'has_phone': normalize_phone(m.phone) is not None, 'sms_ok': bool(m.sms_ok)} for m in rows],
        'agreed': agreed, 'total': base.count(),
    }), 200


@sms_bp.route('/consent', methods=['POST'])
@jwt_required()
@roles_required(*STAFF)
def consent():
    data = _json()
    member = owned_or_404(Member, int(data.get('member_id') or 0))
    agreed = data.get('agreed')
    if not isinstance(agreed, bool) or member.erased_at is not None:
        return jsonify({'error': 'Say whether the member agreed'}), 400
    if agreed and normalize_phone(member.phone) is None:
        return jsonify({'error': 'Add a valid Kenyan phone number to this member first', 'code': 'NO_PHONE'}), 400
    member.sms_ok, member.sms_ok_at = agreed, (datetime.utcnow() if agreed else None)
    if agreed:
        SmsOptOut.query.filter_by(phone=normalize_phone(member.phone)).delete()
    audit('sms.consent', 'member', member.id, after={'agreed': agreed})
    db.session.commit()
    return jsonify({'id': member.id, 'sms_ok': agreed}), 200


@sms_bp.route('/preview', methods=['POST'])
@jwt_required()
@roles_required(*STAFF)
def preview():
    plan, problem = _plan(_json())
    if problem:
        return problem
    return jsonify({'recipients': len(plan['items']), 'parts_each': max(i['parts'] for i in plan['items']),
                    'total_parts': plan['need'], 'used': plan['used'], 'limit': plan['limit'],
                    'remaining_after': plan['limit'] - plan['used'] - plan['need'],
                    'skipped_no_phone': plan['no_phone'], 'personalised': plan['personal'],
                    'invalid_numbers': plan['invalid'], 'opted_out': plan['opted_out'], 'typed': plan['typed'],
                    'sample': plan['items'][0]['body']}), 200


@sms_bp.route('/send', methods=['POST'])
@jwt_required()
@roles_required(*STAFF)
@limiter.limit('10 per minute')
def send():
    data = _json()
    config = sms.setup_status()
    if not config['configured']:
        return jsonify({'error': 'SMS is not set up yet', 'code': 'SMS_NOT_CONFIGURED',
                        'missing': config['missing']}), 503
    plan, problem = _plan(data)
    if problem:
        return problem
    items = plan['items']
    if data.get('confirm_count') != len(items):
        return jsonify({'error': 'The audience changed. Preview again before sending.', 'code': 'CHANGED',
                        'recipients': len(items)}), 409
    if plan['used'] + plan['need'] > plan['limit']:
        return jsonify({'error': 'This would pass your plan\'s SMS limit for the month (%d of %d used). '
                                 'Send fewer messages or move to a bigger plan.' % (plan['used'], plan['limit']),
                        'code': 'SMS_LIMIT'}), 402
    church_id, user_id, batch = current_church_id(), int(get_jwt_identity()), uuid.uuid4().hex
    groups = [[i] for i in items] if plan['personal'] else [items[n:n + CHUNK] for n in range(0, len(items), CHUNK)]
    accepted = failed = 0
    for group in groups:
        try:
            results = sms.send_batch([i['phone'] for i in group], group[0]['body'])
        except sms.SmsError as err:
            results = [{'phone': i['phone'], 'status': 'failed', 'detail': str(err)[:120], 'message_id': '',
                        'cost': ''} for i in group]
        by_phone = {r['phone']: r for r in results}
        for item in group:
            r = by_phone.get(item['phone']) or {'status': 'failed', 'detail': 'No result for this number',
                                                'message_id': '', 'cost': ''}
            db.session.add(SmsMessage(church_id=church_id, member_id=item['member'].id if item['member'] else None, batch_id=batch,
                                      phone=item['phone'], body=item['body'][:480], status=r['status'],
                                      provider_id=r.get('message_id') or None, detail=r.get('detail') or None,
                                      segments=item['parts'], cost=r.get('cost') or None, created_by=user_id))
            accepted, failed = (accepted + 1, failed) if r['status'] == 'sent' else (accepted, failed + 1)
        db.session.commit()
    audit('sms.send', 'sms', None, after={'batch': batch, 'recipients': len(items), 'accepted': accepted,
                                          'failed': failed, 'parts': plan['need'], 'typed_numbers': plan['typed']})
    db.session.commit()
    return jsonify({'batch_id': batch, 'accepted': accepted, 'failed': failed, 'parts': plan['need'],
                    'remaining': plan['limit'] - _used(church_id)}), 200


@sms_bp.route('/history', methods=['GET'])
@jwt_required()
@roles_required(*STAFF)
def history():
    church = db.session.get(Church, current_church_id())
    rows = scoped(SmsMessage).order_by(SmsMessage.id.desc()).limit(100).all()
    return jsonify({'messages': [dict(r.to_dict(), phone=_mask(r.phone)) for r in rows],
                    'used': _used(church.id), 'limit': _limit(church)}), 200


def _secret_ok(secret):
    expected = os.environ.get('AT_CALLBACK_SECRET', '').strip()
    return len(expected) >= 16 and hmac.compare_digest(secret, expected)


def _field(name):
    return (request.form.get(name) or (request.get_json(silent=True) or {}).get(name) or '').strip()


@sms_bp.route('/delivery/<secret>', methods=['POST'])
@limiter.limit('300 per minute')
def delivery(secret):
    """Africa's Talking reports whether a message reached the phone."""
    if not _secret_ok(secret):
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404
    row = SmsMessage.query.filter_by(provider_id=_field('id')[:60]).first() if _field('id') else None
    status = _field('status').lower()
    if row is not None:
        if status in ('success', 'delivered'):
            row.status, row.detail = 'delivered', None
        elif status in ('failed', 'rejected'):
            row.status, row.detail = 'failed', (_field('failureReason') or 'Not delivered')[:120]
        row.updated_at = datetime.utcnow()
        db.session.commit()
    return jsonify({'ok': True}), 200


@sms_bp.route('/inbound/<secret>', methods=['POST'])
@limiter.limit('300 per minute')
def inbound(secret):
    """A member replied. STOP removes their number everywhere ChurchOS sends from this sender."""
    if not _secret_ok(secret):
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404
    words = _field('text').upper().split()
    phone = normalize_phone(_field('from'))
    if phone and words and words[0] in STOP_WORDS:
        if SmsOptOut.query.filter_by(phone=phone).first() is None:
            db.session.add(SmsOptOut(phone=phone))
        rows = Member.query.filter(Member.sms_ok.is_(True), Member.phone.isnot(None)).limit(50000).all()
        changed = [m for m in rows if normalize_phone(m.phone) == phone]
        for member in changed:
            member.sms_ok, member.sms_ok_at = False, None
            audit('sms.optout', 'member', member.id, church_id=member.church_id, after={'agreed': False})
        db.session.commit()
    return jsonify({'ok': True}), 200
