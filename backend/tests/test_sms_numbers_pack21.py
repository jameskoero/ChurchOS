"""Fix Pack 21: typing phone numbers, STOP blocking for any number, and finding members by full name."""
import pytest

from conftest import ADMIN_PASSWORD
from services import sms

STAFF = 'Staff-Login-13579'
SECRET = 'callback-secret-0123456789abcdef'


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv('AT_USERNAME', 'sandbox')
    monkeypatch.setenv('AT_API_KEY', 'api-key-value-0123456789')
    monkeypatch.setenv('AT_CALLBACK_SECRET', SECRET)


@pytest.fixture()
def fake(monkeypatch):
    calls = []

    def send_batch(numbers, message):
        calls.append((list(numbers), message))
        return [{'phone': n, 'ok': True, 'code': 101, 'status': 'sent', 'detail': '',
                 'message_id': 'ATXid_%d_%s' % (len(calls), n[-3:]), 'cost': 'KES 0.8000'} for n in numbers]
    monkeypatch.setattr(sms, 'send_batch', send_batch)
    return calls


def login(client, username, password):
    res = client.post('/api/auth/login', json={'username': username, 'password': password})
    assert res.status_code == 200, res.get_json()
    return {'Authorization': 'Bearer ' + res.get_json()['access_token']}


def admin(client):
    return login(client, 'admin', ADMIN_PASSWORD)


def member(client, h, first, last, phone):
    res = client.post('/api/members/', headers=h, json={'first_name': first, 'last_name': last, 'phone': phone})
    assert res.status_code == 201, res.get_json()
    return res.get_json()['id']


def typed(numbers, message='Welcome on Sunday.', asked=True):
    return {'message': message, 'audience': 'numbers', 'numbers': numbers, 'asked': asked}


def test_members_are_found_by_full_name_first_name_or_member_number(client):
    a = admin(client)
    mid = member(client, a, 'Mercy', 'Chepkemoi', '0711000111')
    member(client, a, 'James', 'Koero', '0722000222')
    code = client.get('/api/sms/audience', headers=a).get_json()['members']
    number = next(m['member_id'] for m in code if m['id'] == mid)
    for search in ('Mercy Chepkemoi', 'chepkemoi mercy', 'merc', number):
        found = client.get('/api/sms/audience', headers=a, query_string={'search': search}).get_json()['members']
        assert [m['id'] for m in found] == [mid], search
    assert client.get('/api/sms/audience', headers=a, query_string={'search': 'Mercy Nobody'}).get_json()['members'] == []


def test_a_typed_number_can_be_messaged_once_the_sender_confirms(client, fake):
    a = admin(client)
    assert client.post('/api/sms/preview', headers=a, json=typed('0712 345 678', asked=False)).status_code == 400
    prev = client.post('/api/sms/preview', headers=a, json=typed('0712 345 678, 0722000111 abc, 0712345678'))
    assert prev.status_code == 200, prev.get_json()
    body = prev.get_json()
    assert body['recipients'] == 2 and body['typed'] is True and body['invalid_numbers'] == ['abc']
    assert body['total_parts'] == 2
    stale = client.post('/api/sms/send', headers=a, json=dict(typed('0712 345 678, 0722000111'), confirm_count=9))
    assert stale.status_code == 409 and fake == []
    sent = client.post('/api/sms/send', headers=a, json=dict(typed('0712 345 678, 0722000111'), confirm_count=2))
    assert sent.status_code == 200, sent.get_json()
    assert sent.get_json()['accepted'] == 2
    assert sorted(fake[0][0]) == ['+254712345678', '+254722000111']
    hist = client.get('/api/sms/history', headers=a).get_json()['messages']
    assert len(hist) == 2 and all(m['member_id'] is None for m in hist)
    assert all('712345678' not in m['phone'] for m in hist)


def test_typed_numbers_have_limits_and_no_names(client, fake):
    a = admin(client)
    assert client.post('/api/sms/preview', headers=a, json=typed('abc, 123')).status_code == 400
    named = client.post('/api/sms/preview', headers=a, json=typed('0712345678', message='Hi {first_name}'))
    assert named.status_code == 400 and named.get_json()['code'] == 'NO_NAMES'
    many = ','.join('07%08d' % n for n in range(10000000, 10000021))
    cap = client.post('/api/sms/preview', headers=a, json=typed(many))
    assert cap.status_code == 400 and cap.get_json()['code'] == 'TOO_MANY'
    assert fake == []


def test_a_stop_reply_blocks_any_number_even_one_that_is_not_a_member(client, fake):
    a = admin(client)
    assert client.post('/api/sms/inbound/' + SECRET, data={'from': '+254733000333', 'text': 'STOP'}).status_code == 200
    blocked = client.post('/api/sms/preview', headers=a, json=typed('0733 000 333'))
    assert blocked.status_code == 400 and 'STOP' in blocked.get_json()['error']
    both = client.post('/api/sms/preview', headers=a, json=typed('0733000333, 0744000444')).get_json()
    assert both['recipients'] == 1 and both['opted_out'] == 1


def test_a_member_who_replied_stop_is_skipped_until_staff_record_new_consent(client, fake):
    a = admin(client)
    mid = member(client, a, 'Grace', 'Otieno', '0711000111')
    client.post('/api/sms/consent', headers=a, json={'member_id': mid, 'agreed': True})
    client.post('/api/sms/inbound/' + SECRET, data={'from': '+254711000111', 'text': 'stop'})
    off = client.post('/api/sms/preview', headers=a, json=typed('0711000111'))
    assert off.status_code == 400
    assert client.post('/api/sms/consent', headers=a, json={'member_id': mid, 'agreed': True}).status_code == 200
    on = client.post('/api/sms/preview', headers=a, json=typed('0711000111'))
    assert on.status_code == 200 and on.get_json()['recipients'] == 1


def test_only_pastoral_staff_can_send_to_typed_numbers(client, fake):
    a = admin(client)
    client.post('/api/users/', headers=a, json={'username': 'view1', 'email': 'v@example.org',
                                                'password': STAFF, 'role': 'viewer'})
    viewer = login(client, 'view1', STAFF)
    res = client.post('/api/sms/send', headers=viewer, json=dict(typed('0712345678'), confirm_count=1))
    assert res.status_code == 403 and fake == []
