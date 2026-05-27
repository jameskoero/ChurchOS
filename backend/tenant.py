# tenant.py — ChurchOS multi-tenant isolation
# James Koero · 2026
from functools import wraps
from datetime import datetime
from flask import jsonify
from flask_jwt_extended import get_jwt

def get_current_church_id():
    cid = get_jwt().get("church_id")
    if not cid:
        raise ValueError("JWT missing church_id claim")
    return int(cid)

def tenant_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        from models import Church
        try:
            cid = get_current_church_id()
        except ValueError:
            return jsonify(error="Token missing church_id"), 401
        church = Church.query.get(cid)
        if not church:
            return jsonify(error="Church not found"), 404
        if church.plan == "trial" and church.trial_ends < datetime.utcnow():
            return jsonify(error="Trial expired. Upgrade to continue."), 402
        if church.plan == "paid" and not getattr(
                church, "subscription_active", True):
            return jsonify(error="Subscription inactive."), 402
        return fn(*args, **kwargs)
    return wrapper

def tenant_query(model, church_id=None):
    if church_id is None:
        church_id = get_current_church_id()
    return model.query.filter_by(church_id=church_id)
