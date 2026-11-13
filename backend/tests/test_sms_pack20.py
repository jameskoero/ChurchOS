"""Fix Pack 20: SMS. Consent, preview-then-send, limits, delivery reports, STOP replies, and privacy.
No test touches the network: the Africa's Talking call is replaced with a fake."""
import json
import os

import pytest

from conftest import ADMIN_PASSWORD
from services import sms

STAFF = 'Staff-Login-13579'
B_PASS = 'Second-Church-2468'
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


def person(client, h, first, phone, agree=True):
    res = client.post('/api/members/', headers=h, json={'first_name': first, 'last_name': 'Test', 'phone': phone})
    assert res.status_code == 201, res.get_json()
    mid = res.get_json()['id']
    if agree:
        assert client.post('/api/sms/consent', headers=h, json={'member_id': mid, 'agreed': True}).status_code == 200
    return mid


def test_setup_names_missing_settings_without_showing_values(client, monkeypatch):
    a = admin(client)
    monkeypatch.delenv('AT_API_KEY')
    body = client.get('/api/sms/setup', headers=a).get_json()
    assert body['configured'] is False and body['missing'] == ['AT_API_KEY'] and body['environment'] == 'sandbox'
    assert 'api-key-value' not in json.dumps(body)


def test_only_members_who_agreed_and_have_a_phone_are_messaged(client, fake):
    a = admin(client)
    yes = person(client, a, 'Grace', '0711000111')
    person(client, a, 'Noagree', '0711000222', agree=False)
    person(client, a, 'Same', '+254 711 000 111')           # same number again: only one message
    nophone = client.post('/api/members/', headers=a, json={'first_name': 'Nophone', 'last_name': 'Test'}).get_json()['id']
    assert client.post('/api/sms/consent', headers=a, json={'member_id': nophone, 'agreed': True}).status_code == 400
    prev = client.post('/api/sms/preview', headers=a, json={'message': 'Service at 9am.', 'audience': 'all'}).get_json()
    assert prev['recipients'] == 1 and prev['total_parts'] == 1 and '711000111' not in json.dumps(prev)
    aud = client.get('/api/sms/audience', headers=a).get_json()
    assert aud['agreed'] == 2 and all('phone' not in m for m in aud['members'])
    sel = client.post('/api/sms/preview', headers=a, json={'message': 'Hi', 'audience': 'selected', 'member_ids': [yes]})
    assert sel.get_json()['recipients'] == 1


def test_send_needs_a_matching_preview_and_records_each_message(client, fake):
    a = admin(client)
    person(client, a, 'Grace', '0711000111')
    person(client, a, 'Peter', '0722000222')
    body = {'message': 'It\u2019s Sunday \u2013 see you!', 'audience': 'all'}
    stale = client.post('/api/sms/send', headers=a, json=dict(body, confirm_count=5))
    assert stale.status_code == 409 and stale.get_json()['code'] == 'CHANGED' and fake == []
    ok = client.post('/api/sms/send', headers=a, json=dict(body, confirm_count=2))
    assert ok.status_code == 200, ok.get_json()
    assert ok.get_json()['accepted'] == 2 and ok.get_json()['failed'] == 0
    assert len(fake) == 1 and sorted(fake[0][0]) == ['+254711000111', '+254722000222']
    assert fake[0][1] == "It's Sunday - see you!"                      # curly characters were tidied before sending
    hist = client.get('/api/sms/history', headers=a).get_json()
    assert len(hist['messages']) == 2 and hist['used'] == 2
    assert sorted(m['phone'][-3:] for m in hist['messages']) == ['111', '222']
    assert all('0711000111' not in m['phone'] and '711000111' not in m['phone'] for m in hist['messages'])


def test_first_name_personalises_one_message_per_member(client, fake):
    a = admin(client)
    person(client, a, 'Grace', '0711000111')
    person(client, a, 'Peter', '0722000222')
    res = client.post('/api/sms/send', headers=a, json={'message': 'Hello {first_name}!', 'audience': 'all', 'confirm_count': 2})
    assert res.status_code == 200
    assert sorted(m for _, m in fake) == ['Hello Grace!', 'Hello Peter!'] and all(len(n) == 1 for n, _ in fake)


def test_unconfigured_overlong_and_empty_messages_are_refused(client, fake, monkeypatch):
    a = admin(client)
    person(client, a, 'Grace', '0711000111')
    assert client.post('/api/sms/preview', headers=a, json={'message': '  ', 'audience': 'all'}).status_code == 400
    long = client.post('/api/sms/preview', headers=a, json={'message': 'x' * 500, 'audience': 'all'})
    assert long.status_code == 400 and long.get_json()['code'] == 'TOO_LONG'
    monkeypatch.delenv('AT_USERNAME')
    off = client.post('/api/sms/send', headers=a, json={'message': 'Hi', 'audience': 'all', 'confirm_count': 1})
    assert off.status_code == 503 and off.get_json()['code'] == 'SMS_NOT_CONFIGURED' and fake == []


def test_monthly_limit_by_plan_is_enforced(client, fake, monkeypatch):
    a = admin(client)
    client.post('/api/churches/', headers=a, json={'name': 'Second Church', 'admin_username': 'badmin',
                'admin_email': 'b@example.org', 'admin_password': B_PASS})
    b = login(client, 'badmin', B_PASS)
    person(client, b, 'One', '0711000111')
    person(client, b, 'Two', '0722000222')
    person(client, b, 'Three', '0733000333')
    monkeypatch.setitem(sms.MONTHLY_PARTS, 'trial', 4)
    first = client.post('/api/sms/send', headers=b, json={'message': 'Hi', 'audience': 'all', 'confirm_count': 3})
    assert first.status_code == 200 and first.get_json()['remaining'] == 1
    second = client.post('/api/sms/send', headers=b, json={'message': 'Hi again', 'audience': 'all', 'confirm_count': 3})
    assert second.status_code == 402 and second.get_json()['code'] == 'SMS_LIMIT'
    assert len(fake) == 1


def test_delivery_reports_update_status_and_need_the_secret(app, client, fake):
    a = admin(client)
    person(client, a, 'Grace', '0711000111')
    client.post('/api/sms/send', headers=a, json={'message': 'Hi', 'audience': 'all', 'confirm_count': 1})
    mid = client.get('/api/sms/history', headers=a).get_json()['messages'][0]['id']
    from models import SmsMessage, db
    with app.app_context():
        pid = db.session.get(SmsMessage, mid).provider_id
    assert client.post('/api/sms/delivery/wrong-secret-value-0123', data={'id': pid, 'status': 'Success'}).status_code == 404
    assert client.post('/api/sms/delivery/' + SECRET, data={'id': pid, 'status': 'Success'}).status_code == 200
    assert client.get('/api/sms/history', headers=a).get_json()['messages'][0]['status'] == 'delivered'
    client.post('/api/sms/delivery/' + SECRET, data={'id': pid, 'status': 'Failed', 'failureReason': 'UserInBlacklist'})
    top = client.get('/api/sms/history', headers=a).get_json()['messages'][0]
    assert top['status'] == 'failed' and top['detail'] == 'UserInBlacklist'


def test_a_stop_reply_removes_consent_in_every_church(client, fake):
    a = admin(client)
    mid = person(client, a, 'Grace', '0711000111')
    client.post('/api/churches/', headers=a, json={'name': 'Second Church', 'admin_username': 'badmin',
                'admin_email': 'b@example.org', 'admin_password': B_PASS})
    b = login(client, 'badmin', B_PASS)
    other = person(client, b, 'Grace', '+254711000111')
    assert client.post('/api/sms/inbound/not-the-secret-0123456789', data={'from': '+254711000111', 'text': 'STOP'}).status_code == 404
    assert client.post('/api/sms/inbound/' + SECRET, data={'from': '+254711000111', 'text': 'Hello there'}).status_code == 200
    assert client.get('/api/sms/audience', headers=a).get_json()['agreed'] == 1
    assert client.post('/api/sms/inbound/' + SECRET, data={'from': '+254711000111', 'text': ' stop please'}).status_code == 200
    assert client.get('/api/sms/audience', headers=a).get_json()['agreed'] == 0
    assert client.get('/api/sms/audience', headers=b).get_json()['agreed'] == 0


def test_erasing_a_member_clears_consent_and_their_number_from_history(client, fake):
    a = admin(client)
    mid = person(client, a, 'Grace', '0711000111')
    client.post('/api/sms/send', headers=a, json={'message': 'Hi', 'audience': 'all', 'confirm_count': 1})
    assert client.post('/api/members/%d/erase' % mid, headers=a).status_code == 200
    hist = client.get('/api/sms/history', headers=a).get_json()['messages']
    assert hist[0]['phone'] == 'erased'
    assert client.get('/api/sms/audience', headers=a).get_json()['agreed'] == 0


def test_roles_and_church_separation(client, fake):
    a = admin(client)
    mid = person(client, a, 'Grace', '0711000111')
    client.post('/api/users/', headers=a, json={'username': 'view1', 'email': 'v@example.org', 'password': STAFF, 'role': 'viewer'})
    viewer = login(client, 'view1', STAFF)
    for path in ('/api/sms/setup', '/api/sms/audience', '/api/sms/history'):
        assert client.get(path, headers=viewer).status_code == 403
    assert client.post('/api/sms/send', headers=viewer, json={'message': 'Hi', 'audience': 'all', 'confirm_count': 1}).status_code == 403
    client.post('/api/churches/', headers=a, json={'name': 'Second Church', 'admin_username': 'badmin',
                'admin_email': 'b@example.org', 'admin_password': B_PASS})
    b = login(client, 'badmin', B_PASS)
    assert client.post('/api/sms/consent', headers=b, json={'member_id': mid, 'agreed': True}).status_code == 404
    assert client.get('/api/sms/audience', headers=b).get_json()['members'] == []
    assert client.get('/api/sms/history', headers=b).get_json()['messages'] == []
