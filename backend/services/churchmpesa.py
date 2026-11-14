"""A church's OWN Safaricom setup (its own Paybill or Till with its own Daraja keys).

Money then goes straight from the member to the church's own shortcode. ChurchOS never receives it.
Facts used (Safaricom Daraja documentation): C2B Register URL is POST /mpesa/c2b/v1/registerurl with ShortCode,
ResponseType, ConfirmationURL and ValidationURL; callback addresses must be public and must not contain words
such as mpesa, safaricom, exec or query; in production the URLs are registered once and later changed only through
Safaricom's portal."""
import os

from services import mpesa, vault

FORBIDDEN = ('mpesa', 'm-pesa', 'safaricom', 'exec', 'cmd', 'sql', 'query')


def server_address():
    return os.environ.get('MPESA_CALLBACK_URL', '').strip().rstrip('/')


def server_problems():
    url = server_address().lower()
    problems = []
    if not url:
        return ['MPESA_CALLBACK_URL is not set']
    if not url.startswith('https://'):
        problems.append('MPESA_CALLBACK_URL must start with https://')
    if any(word in url for word in FORBIDDEN):
        problems.append('MPESA_CALLBACK_URL must not contain words Safaricom blocks (mpesa, safaricom, query ...)')
    if url.count('/') > 2:
        problems.append('MPESA_CALLBACK_URL must be only the server address, with no path after it')
    return problems


def cfg_for(row):
    """Settings for one church, in the same shape services.mpesa uses. Raises VaultError or NotConfigured."""
    if not server_address():
        raise mpesa.NotConfigured('Missing settings: MPESA_CALLBACK_URL')
    return {
        'MPESA_CONSUMER_KEY': vault.decrypt(row.consumer_key_enc),
        'MPESA_CONSUMER_SECRET': vault.decrypt(row.consumer_secret_enc),
        'MPESA_PASSKEY': vault.decrypt(row.passkey_enc),
        'MPESA_SHORTCODE': row.shortcode,
        'MPESA_CALLBACK_URL': server_address(),
        'MPESA_CALLBACK_SECRET': row.callback_token,
        'base': mpesa.LIVE if row.env == 'live' else mpesa.SANDBOX,
    }


def c2b_urls(row):
    base = '%s/api/payments/c2b/%s' % (server_address(), row.callback_token)
    return base + '/confirmation', base + '/validation'


def register_c2b(row):
    """Tell Safaricom where to send this shortcode's payment notices."""
    cfg = cfg_for(row)
    confirmation, validation = c2b_urls(row)
    body = mpesa._call(
        cfg['base'] + '/mpesa/c2b/v1/registerurl',
        payload={'ShortCode': row.shortcode, 'ResponseType': 'Completed',
                 'ConfirmationURL': confirmation, 'ValidationURL': validation},
        headers={'Authorization': 'Bearer ' + mpesa.access_token(cfg), 'Content-Type': 'application/json'})
    if str(body.get('ResponseCode')) != '0':
        detail = str(body.get('ResponseDescription') or body.get('errorMessage') or '')[:120]
        raise mpesa.MpesaError('Safaricom did not accept the addresses' + (': ' + detail if detail else ''))
    return True
