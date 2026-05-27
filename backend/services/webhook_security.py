# services/webhook_security.py — Payment webhook verification
# James Koero · 2026
import os
from functools import wraps
from flask import request, jsonify

def verify_flutterwave_signature(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = os.environ.get("FLW_SECRET_HASH", "")
        received = request.headers.get("verif-hash", "")
        if not expected or received != expected:
            return jsonify(error="Invalid webhook signature"), 401
        return fn(*args, **kwargs)
    return wrapper

SAFARICOM_IPS = ("196.201.214.", "196.201.216.", "196.201.213.")

def verify_mpesa_source(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if os.environ.get("FLASK_ENV") == "development":
            return fn(*args, **kwargs)
        ip = request.remote_addr
        if not any(ip.startswith(p) for p in SAFARICOM_IPS):
            print(f"[WARNING] M-Pesa callback from unknown IP: {ip}")
        return fn(*args, **kwargs)
    return wrapper
