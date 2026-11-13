"""Africa's Talking SMS client. Standard library only, so it can be tested without a network.
Facts used (from Africa's Talking's documentation): live and sandbox addresses, the apiKey header,
status codes 100/101/102 = accepted and 401-404/500-502 = refused, one charge per message part."""
import json
import math
import os
import re
import urllib.error
import urllib.parse
import urllib.request

LIVE = 'https://api.africastalking.com/version1/messaging'
SANDBOX = 'https://api.sandbox.africastalking.com/version1/messaging'
REQUIRED = ('AT_USERNAME', 'AT_API_KEY')
ACCEPTED = (100, 101, 102)
CODE_NAMES = {401: 'RiskHold', 402: 'InvalidSenderId', 403: 'InvalidPhoneNumber', 404: 'UnsupportedNumberType',
              500: 'InternalServerError', 501: 'GatewayError', 502: 'RejectedByGateway'}
MAX_PARTS = 3

# Product limits chosen for ChurchOS (message parts a month). Adjust once your real SMS price is known.
MONTHLY_PARTS = {'trial': 30, 'seed': 300, 'growth': 1500, 'parish': 6000, 'cathedral': 30000}
COMPLIMENTARY_PARTS = 3000

_REPLACE = {'\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"', '\u2013': '-', '\u2014': '-',
            '\u2026': '...', '\u00a0': ' ', '\u200b': ''}
_PLAIN = re.compile(r'^[A-Za-z0-9 \n.,!?:;\'"()\-/+&%@#*=<>_]*$')


class SmsError(Exception):
    pass


def clean_text(text):
    """Typing apostrophes and dashes on a phone keyboard can silently triple the price; fix them first."""
    out = str(text or '')
    for old, new in _REPLACE.items():
        out = out.replace(old, new)
    return out.replace('\r\n', '\n').strip()


def parts(text):
    """How many message parts the text will be billed as."""
    n = len(text)
    if n == 0:
        return 0
    if _PLAIN.match(text):
        return 1 if n <= 160 else int(math.ceil(n / 153.0))
    return 1 if n <= 70 else int(math.ceil(n / 67.0))


def setup_status():
    """Which settings are present. Names only, never values."""
    values = {name: os.environ.get(name, '').strip() for name in REQUIRED}
    missing = [name for name, value in values.items() if not value]
    username = values['AT_USERNAME'].lower()
    secret = os.environ.get('AT_CALLBACK_SECRET', '').strip()
    problems = []
    if len(secret) < 16:
        problems.append('AT_CALLBACK_SECRET (16 or more characters) is needed for delivery reports and STOP replies')
    return {'configured': not missing, 'missing': missing,
            'environment': 'sandbox' if username == 'sandbox' else 'live',
            'sender_id_set': bool(os.environ.get('AT_SENDER_ID', '').strip()),
            'callbacks_ready': len(secret) >= 16, 'problems': problems}


def _post(url, form, key):
    data = urllib.parse.urlencode(form).encode()
    request = urllib.request.Request(url, data=data, headers={
        'apiKey': key, 'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.loads(response.read().decode() or '{}')
    except urllib.error.HTTPError as err:
        raise SmsError("Africa's Talking answered HTTP %s" % err.code)
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise SmsError("Could not reach Africa's Talking")


def send_batch(numbers, message):
    """Send one message to up to 100 numbers (+254...). Returns one dict per recipient."""
    cfg = setup_status()
    if not cfg['configured']:
        raise SmsError('SMS is not set up yet')
    username = os.environ['AT_USERNAME'].strip()
    form = {'username': username, 'to': ','.join(numbers), 'message': message}
    sender = os.environ.get('AT_SENDER_ID', '').strip()
    if sender:
        form['from'] = sender
    body = _post(SANDBOX if cfg['environment'] == 'sandbox' else LIVE, form, os.environ['AT_API_KEY'].strip())
    data = body.get('SMSMessageData', body) if isinstance(body, dict) else {}
    recipients = data.get('Recipients')
    if not isinstance(recipients, list):
        raise SmsError("Africa's Talking gave no recipient results")
    out = []
    for r in recipients:
        try:
            code = int(r.get('statusCode'))
        except (TypeError, ValueError):
            code = 0
        out.append({'phone': str(r.get('number') or ''), 'ok': code in ACCEPTED, 'code': code,
                    'status': 'sent' if code in ACCEPTED else 'failed',
                    'detail': '' if code in ACCEPTED else CODE_NAMES.get(code, 'Rejected (code %s)' % code),
                    'message_id': str(r.get('messageId') or '')[:60], 'cost': str(r.get('cost') or '')[:20]})
    return out
