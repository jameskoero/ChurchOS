from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from tenancy import (current_church_id, scoped, owned_or_404, tquery,
                     page_size, roles_required, can_see_money, FINANCE_READ)
from models import db, Event
from datetime import datetime

events_bp = Blueprint('events', __name__)


@events_bp.route('/', methods=['GET'])
@jwt_required()
def get_events():
    page = request.args.get('page', 1, type=int)
    per_page = page_size(20)
    status = request.args.get('status', '')
    event_type = request.args.get('event_type', '')

    query = scoped(Event)
    if status:
        query = query.filter_by(status=status)
    if event_type:
        query = query.filter_by(event_type=event_type)

    total = query.count()
    events = query.order_by(Event.start_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'events': [e.to_dict() for e in events.items],
        'total': total,
        'pages': events.pages,
        'current_page': page
    }), 200


@events_bp.route('/upcoming', methods=['GET'])
@jwt_required()
def get_upcoming():
    today = datetime.utcnow()
    events = scoped(Event).filter(
        Event.start_date >= today,
        Event.status != 'cancelled'
    ).order_by(Event.start_date).limit(10).all()
    return jsonify([e.to_dict() for e in events]), 200


@events_bp.route('/<int:event_id>', methods=['GET'])
@jwt_required()
def get_event(event_id):
    event = owned_or_404(Event, event_id)
    return jsonify(event.to_dict()), 200


@events_bp.route('/', methods=['POST'])
@jwt_required()
def create_event():
    claims = get_jwt()
    if claims.get('role') not in ['admin', 'pastor', 'secretary']:
        return jsonify({'error': 'Insufficient permissions'}), 403

    user_id = get_jwt_identity()
    data = request.get_json()

    required = ['title', 'start_date']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    try:
        start_date = datetime.fromisoformat(data['start_date'])
    except ValueError:
        return jsonify({'error': 'Invalid start_date format (use ISO 8601)'}), 400

    end_date = None
    if data.get('end_date'):
        try:
            end_date = datetime.fromisoformat(data['end_date'])
        except ValueError:
            pass

    event = Event(
        church_id=current_church_id(),
        title=data['title'],
        description=data.get('description'),
        event_type=data.get('event_type', 'service'),
        location=data.get('location'),
        start_date=start_date,
        end_date=end_date,
        is_recurring=data.get('is_recurring', False),
        recurrence_pattern=data.get('recurrence_pattern'),
        max_attendees=data.get('max_attendees'),
        status=data.get('status', 'upcoming'),
        created_by=int(user_id)
    )

    db.session.add(event)
    db.session.commit()
    return jsonify(event.to_dict()), 201


@events_bp.route('/<int:event_id>', methods=['PUT'])
@jwt_required()
def update_event(event_id):
    claims = get_jwt()
    if claims.get('role') not in ['admin', 'pastor', 'secretary']:
        return jsonify({'error': 'Insufficient permissions'}), 403

    event = owned_or_404(Event, event_id)
    data = request.get_json()

    fields = ['title', 'description', 'event_type', 'location', 'is_recurring',
              'recurrence_pattern', 'max_attendees', 'status']
    for field in fields:
        if field in data:
            setattr(event, field, data[field])

    if 'start_date' in data:
        try:
            event.start_date = datetime.fromisoformat(data['start_date'])
        except ValueError:
            pass
    if 'end_date' in data:
        try:
            event.end_date = datetime.fromisoformat(data['end_date'])
        except ValueError:
            pass

    db.session.commit()
    return jsonify(event.to_dict()), 200


@events_bp.route('/<int:event_id>', methods=['DELETE'])
@jwt_required()
def delete_event(event_id):
    claims = get_jwt()
    if claims.get('role') not in ['admin', 'pastor']:
        return jsonify({'error': 'Insufficient permissions'}), 403
    event = owned_or_404(Event, event_id)
    db.session.delete(event)
    db.session.commit()
    return jsonify({'message': 'Event deleted'}), 200
