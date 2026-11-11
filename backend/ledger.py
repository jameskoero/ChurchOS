"""Money rules: exact amounts, live (not void) rows, and the audit trail."""
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import request
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import or_

from models import db, Finance, AuditLog
from tenancy import current_church_id

MAX_AMOUNT = Decimal('9999999999.99')
CENT = Decimal('0.01')


def live_money():
    """SQL filter: transactions that have not been voided."""
    return or_(Finance.status.is_(None), Finance.status != 'void')


def money(value):
    """Return an exact positive amount with 2 decimals, or None if invalid."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    # Check the size first: rounding a huge number raises instead of failing quietly.
    if not amount.is_finite() or amount <= 0 or amount > MAX_AMOUNT:
        return None
    try:
        return amount.quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def audit(action, entity, entity_id, before=None, after=None,
          church_id=None, user_id=None):
    """Add one audit row to the session. The caller commits.

    Inside a signed-in request the church and user come from the token.
    System actions (such as a payment callback) pass them explicitly.
    """
    forwarded = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
    if church_id is None:
        church_id = current_church_id()
    if user_id is None:
        # System actions (a Paybill payment arriving) have no signed-in user.
        try:
            user_id = int(get_jwt_identity())
        except (RuntimeError, TypeError, ValueError):
            user_id = None
    db.session.add(AuditLog(
        church_id=church_id,
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        before=json.dumps(before, default=str, sort_keys=True) if before is not None else None,
        after=json.dumps(after, default=str, sort_keys=True) if after is not None else None,
        ip=(forwarded or request.remote_addr or '')[:64],
    ))


def new_reference():
    """A transaction reference not used by any church (references are unique)."""
    for _ in range(20):
        reference = Finance.generate_reference()
        if Finance.query.filter_by(reference=reference).first() is None:
            return reference
    raise RuntimeError('could not allocate a transaction reference')
