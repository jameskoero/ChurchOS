"""Shared extensions. Only objects that routes need to import live here."""
from flask import request
from flask_limiter import Limiter


def client_ip():
    """Best-effort client address behind the hosting proxy."""
    forwarded = request.headers.get('X-Forwarded-For', '')
    first = forwarded.split(',')[0].strip()
    return first or request.remote_addr or 'unknown'


limiter = Limiter(key_func=client_ip, storage_uri='memory://')
