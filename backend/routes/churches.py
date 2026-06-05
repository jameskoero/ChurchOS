from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from models import (db, Church, KENYAN_COUNTIES, DENOMINATIONS,
                    CHURCH_SIZES, SUBSCRIPTION_PLANS, PLAN_LIMITS)
from datetime import datetime, timedelta

churches_bp = Blueprint('churches', __name__)

def _admin():
    if get_jwt().get('role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

@churches_bp.route('/constants', methods=['GET'])
def get_constants():
    return jsonify({
        'counties': KENYAN_COUNTIES,
        'denominations': DENOMINATIONS,
        'sizes': CHURCH_SIZES,
        'plans': SUBSCRIPTION_PLANS,
        'plan_limits': PLAN_LIMITS
    }), 200

@churches_bp.route('/', methods=['GET'])
@jwt_required()
def list_churches():
    err = _admin()
    if err: return err
    churches = Church.query.order_by(Church.name).all()
    return jsonify({'churches': [c.to_dict() for c in churches],
                    'total': len(churches)}), 200

@churches_bp.route('/', methods=['POST'])
@jwt_required()
def create_church():
    err = _admin()
    if err: return err
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'Church name required'}), 400
    c = Church(
        name=data['name'], county=data.get('county'),
        sub_county=data.get('sub_county'),
        denomination=data.get('denomination'),
        size=data.get('size'), paybill=data.get('paybill'),
        till_number=data.get('till_number'), phone=data.get('phone'),
        email=data.get('email'), address=data.get('address'),
        member_prefix=data.get('member_prefix', 'CHR'),
        subscription_plan='trial',
        trial_ends_at=datetime.utcnow() + timedelta(days=30),
        is_active=True)
    db.session.add(c)
    db.session.commit()
    return jsonify({'message': 'Church registered',
                    'church': c.to_dict()}), 201

@churches_bp.route('/<int:cid>', methods=['GET'])
@jwt_required()
def get_church(cid):
    return jsonify(Church.query.get_or_404(cid).to_dict()), 200

@churches_bp.route('/<int:cid>', methods=['PUT'])
@jwt_required()
def update_church(cid):
    err = _admin()
    if err: return err
    c = Church.query.get_or_404(cid)
    data = request.get_json()
    for field in ['name','county','sub_county','denomination','size',
                  'paybill','till_number','phone','email','address',
                  'member_prefix','subscription_plan','is_active']:
        if field in data: setattr(c, field, data[field])
    c.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'message': 'Church updated',
                    'church': c.to_dict()}), 200

@churches_bp.route('/<int:cid>', methods=['DELETE'])
@jwt_required()
def delete_church(cid):
    err = _admin()
    if err: return err
    c = Church.query.get_or_404(cid)
    db.session.delete(c)
    db.session.commit()
    return jsonify({'message': 'Church deleted'}), 200
