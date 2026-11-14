"""Keeps a church's Safaricom keys unreadable in the database.

The keys are encrypted with Fernet (AES-128-CBC with an HMAC check, from the `cryptography` package) using
MPESA_VAULT_KEY, which lives only in the server's settings. Without that key the saved values are useless.
If MPESA_VAULT_KEY is lost or changed, saved keys cannot be read and each church types them in again."""
import os


class VaultError(Exception):
    pass


def _fernet():
    key = os.environ.get('MPESA_VAULT_KEY', '').strip()
    if not key:
        raise VaultError('MPESA_VAULT_KEY is not set')
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        raise VaultError('The cryptography package is not installed')
    try:
        return Fernet(key.encode())
    except Exception:
        raise VaultError('MPESA_VAULT_KEY is not a valid key')


def ready():
    try:
        _fernet()
        return True
    except VaultError:
        return False


def encrypt(text):
    return _fernet().encrypt(str(text).encode()).decode()


def decrypt(token):
    from cryptography.fernet import InvalidToken
    try:
        return _fernet().decrypt(str(token).encode()).decode()
    except InvalidToken:
        raise VaultError('Saved keys cannot be read with the current MPESA_VAULT_KEY')
