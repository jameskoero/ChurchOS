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
    if not amount.is_finite():
        return None
    amount = amount.quantize(CENT, rounding=ROUND_HALF_UP)
    if amount <= 0 or amount > MAX_AMOUNT:
        return None
    return amount


def audit(action, entity, entity_id, before=None, after=None,
          church_id=None, user_id=None):
    """Add one audit row to the session. The caller commits.

    Inside a signed-in request the church and user come from the token.
    System actions (such as a payment callback) pass them explicitly.
    """
    forwarded = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
    db.session.add(AuditLog(
        church_id=church_id if church_id is not None else current_church_id(),
        user_id=user_id if user_id is not None else int(get_jwt_identity()),
        action=action,
        entity=entity,
        entity_id=entity_id,
        before=json.dumps(before, default=str, sort_keys=True) if before is not None else None,
        after=json.dumps(after, default=str, sort_keys=True) if after is not None else None,
        ip=(forwarded or request.remote_addr or '')[:64],
    ))
