"""Safaricom Daraja client (STK push). Standard library only.

Nothing here runs unless the MPESA_* variables are set. Use MPESA_ENV=sandbox
until you have tested with Safaricom's sandbox credentials.
"""
import base64
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime

SANDBOX = 'https://sandbox.safaricom.co.ke'
LIVE = 'https://api.safaricom.co.ke'
_REQUIRED = ('MPESA_CONSUMER_KEY', 'MPESA_CONSUMER_SECRET', 'MPESA_SHORTCODE',
             'MPESA_PASSKEY', 'MPESA_CALLBACK_URL', 'MPESA_CALLBACK_SECRET')
_token = {'value': None, 'expires': 0.0}


class MpesaError(Exception):
    pass


class NotConfigured(MpesaError):
    pass


def settings():
    values = {name: os.environ.get(name, '').strip() for name in _REQUIRED}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise NotConfigured('Missing settings: ' + ', '.join(missing))
    live = os.environ.get('MPESA_ENV', 'sandbox').strip().lower() in ('live', 'production')
    values['base'] = LIVE if live else SANDBOX
    return values


def callback_url(cfg):
    return '%s/api/payments/mpesa/callback/%s' % (
        cfg['MPESA_CALLBACK_URL'].rstrip('/'), cfg['MPESA_CALLBACK_SECRET'])


def _call(url, payload=None, headers=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode() or '{}')
    except urllib.error.HTTPError as err:
        raise MpesaError('Safaricom answered HTTP %s' % err.code)
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise MpesaError('Could not reach Safaricom')


def access_token(cfg):
    if _token['value'] and time.time() < _token['expires']:
        return _token['value']
    pair = ('%s:%s' % (cfg['MPESA_CONSUMER_KEY'], cfg['MPESA_CONSUMER_SECRET'])).encode()
    body = _call(cfg['base'] + '/oauth/v1/generate?grant_type=client_credentials',
                 headers={'Authorization': 'Basic ' + base64.b64encode(pair).decode()})
    token = body.get('access_token')
    if not token:
        raise MpesaError('Safaricom sent no access token')
    _token['value'] = token
    _token['expires'] = time.time() + max(60, int(body.get('expires_in', 3599)) - 60)
    return token


def stk_push(phone, amount, account_ref, description):
    """Ask Safaricom to show the payment prompt on this phone.

    phone is 2547XXXXXXXX, amount a whole number of shillings.
    Returns {'merchant_request_id': ..., 'checkout_request_id': ...}.
    """
    cfg = settings()
    stamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    password = base64.b64encode(
        (cfg['MPESA_SHORTCODE'] + cfg['MPESA_PASSKEY'] + stamp).encode()).decode()
    body = _call(
        cfg['base'] + '/mpesa/stkpush/v1/processrequest',
        payload={
            'BusinessShortCode': cfg['MPESA_SHORTCODE'],
            'Password': password,
            'Timestamp': stamp,
            'TransactionType': 'CustomerPayBillOnline',
            'Amount': int(amount),
            'PartyA': phone,
            'PartyB': cfg['MPESA_SHORTCODE'],
            'PhoneNumber': phone,
            'CallBackURL': callback_url(cfg),
            'AccountReference': str(account_ref)[:12],
            'TransactionDesc': str(description)[:13],
        },
        headers={'Authorization': 'Bearer ' + access_token(cfg),
                 'Content-Type': 'application/json'})
    if str(body.get('ResponseCode')) != '0' or not body.get('CheckoutRequestID'):
        raise MpesaError('Safaricom did not accept the request')
    return {'merchant_request_id': body.get('MerchantRequestID'),
            'checkout_request_id': body['CheckoutRequestID']}
