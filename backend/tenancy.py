"""Church separation. Every route reads and writes through these helpers."""
from functools import wraps

from flask import abort, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity
from sqlalchemy import false

from models import db, User

FINANCE_READ = ('admin', 'treasurer', 'pastor')
MAX_PAGE = 100


def current_church_id():
    """Church of the signed-in user. 403 when the account has no church."""
    church_id = get_jwt().get('church_id')
    if church_id is None:
        user = db.session.get(User, int(get_jwt_identity()))
        church_id = user.church_id if user else None
    if church_id is None:
        abort(403)
    return int(church_id)


def scoped(model):
    """model.query limited to the caller's church."""
    return model.query.filter(model.church_id == current_church_id())


def owned_or_404(model, object_id):
    """One row by id, only if it belongs to the caller's church."""
    return scoped(model).filter(model.id == object_id).first_or_404()


def tquery(model, allow=True):
    """db.session.query(...) limited to the caller's church.

    With allow=False the query matches nothing (used to hide money figures).
    """
    def build(*entities):
        query = db.session.query(*entities).filter(
            model.church_id == current_church_id())
        return query if allow else query.filter(false())
    return build


def can_see_money():
    return get_jwt().get('role') in FINANCE_READ


def is_owner():
    return bool(get_jwt().get('owner'))


def page_size(default):
    size = request.args.get('per_page', default, type=int) or default
    return max(1, min(size, MAX_PAGE))


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if get_jwt().get('role') not in roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            return view(*args, **kwargs)
        return wrapped
    return decorator


PERSONAL_ROLES = ('admin', 'pastor', 'secretary')
SENSITIVE_MEMBER_FIELDS = ('date_of_birth', 'address', 'marital_status', 'next_of_kin',
                           'next_of_kin_phone', 'baptism_date', 'notes')


def can_see_personal():
    """Only pastoral staff may read the sensitive parts of a member record."""
    return get_jwt().get('role') in PERSONAL_ROLES


def redact_member(data):
    """Remove sensitive fields from a member dict for roles that may not see them."""
    if can_see_personal():
        return data
    return {k: v for k, v in data.items() if k not in SENSITIVE_MEMBER_FIELDS}
