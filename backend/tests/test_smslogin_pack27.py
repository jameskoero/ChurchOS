"""Fix Pack 27: sign-in by SMS code. Off by default; password first; guess limits; SIM-swap cool-down; recovery.
No test touches the network: the Africa's Talking call is replaced with a fake."""
import re
from datetime import datetime, timedelta

import pytest

from conftest import ADMIN_PASSWORD
from services import sms
from test_governance_pack22 import PASS, church, login

PHONE = '0712345678'
NEW_PHONE = '0722000111'


@pytest.fixture(autouse=True)
def live_sms(monkeypatch):
    monkeypatch.setenv('AT_USERNAME', 'churchos-live')
    monkeypatch.setenv('AT_API_KEY', 'api-key-value-0123456789')
    monkeypatch.setenv('AT_CALLBACK_SECRET', 'callback-secret-0123456789abcdef')
    monkeypatch.delenv('SMS_LOGIN_FORCE_OFF', raising=False)


@pytest.fixture()
def sent(monkeypatch):
    box = []

    def send_batch(numbers, message):
        box.append((list(numbers), message))
        return [{'phone': n, 'ok': True, 'code': 101, 'status': 'sent', 'detail': '', 'message_id': 'ATX%d' % len(box),
                 'cost': ''} for n in numbers]
    monkeypatch.setattr(sms, 'send_batch', send_batch)
    return box


def code_of(box):
    return re.search(r'\b(\d{6})\b', box[-1][1]).group(1)


def password_login(client, username, password):
    return client.post('/api/auth/login', json={'username': username, 'password': password})


def setup(client, sent, on=True):
    """Owner, a church admin 'sp1', and (when on) the platform switch."""
    owner = login(client, 'admin', ADMIN_PASSWORD)
    _, sp = church(client, owner, 'Kaego Altar', 'sp1')
    if on:
        assert client.put('/api/auth/sms-login/platform', headers=owner, json={'enabled': True}).status_code == 200
    return owner, sp


def enrol(client, sp, sent, phone=PHONE):
    started = client.post('/api/auth/sms-login/start', headers=sp, json={'phone': phone, 'password': PASS})
    assert started.status_code == 200, started.get_json()
    done = client.post('/api/auth/sms-login/confirm', headers=sp,
                       json={'challenge': started.get_json()['challenge'], 'code': code_of(sent)})
    assert done.status_code == 200, done.get_json()
    return done.get_json()


def test_off_by_default_and_cannot_start_while_off(client, sent):
    owner, sp = setup(client, sent, on=False)
    assert client.get('/api/auth/sms-login/status', headers=sp).get_json()['platform_on'] is False
    assert client.post('/api/auth/sms-login/start', headers=sp, json={'phone': PHONE, 'password': PASS}).status_code == 409
    assert password_login(client, 'sp1', PASS).get_json()['access_token']
    assert sent == []


def test_platform_switch_is_owner_only_and_needs_live_sms(client, sent, monkeypatch):
    owner, sp = setup(client, sent, on=False)
    assert client.put('/api/auth/sms-login/platform', headers=sp, json={'enabled': True}).status_code == 403
    monkeypatch.setenv('AT_USERNAME', 'sandbox')
    refused = client.put('/api/auth/sms-login/platform', headers=owner, json={'enabled': True})
    assert refused.status_code == 409 and refused.get_json()['code'] == 'SMS_NOT_LIVE'
    monkeypatch.setenv('AT_USERNAME', 'churchos-live')
    assert client.put('/api/auth/sms-login/platform', headers=owner, json={'enabled': True}).status_code == 200


def test_enrol_then_sign_in_needs_the_code_and_a_code_works_once(client, sent):
    owner, sp = setup(client, sent)
    assert enrol(client, sp, sent)['enabled'] is True
    first = password_login(client, 'sp1', PASS)
    assert first.status_code == 202 and 'access_token' not in first.get_json()
    assert first.get_json()['needs_code'] and '+254712345678' in sent[-1][0]
    assert '678' in first.get_json()['phone_hint'] and '712345' not in first.get_json()['phone_hint']
    body = {'challenge': first.get_json()['challenge'], 'code': code_of(sent)}
    ok = client.post('/api/auth/login/verify', json=body)
    assert ok.status_code == 200 and ok.get_json()['access_token'] and ok.get_json()['user']['username'] == 'sp1'
    assert client.post('/api/auth/login/verify', json=body).status_code == 401          # one use only


def test_wrong_password_never_sends_a_code(client, sent):
    owner, sp = setup(client, sent)
    enrol(client, sp, sent)
    count = len(sent)
    assert password_login(client, 'sp1', 'Not-The-Password-1').status_code == 401
    assert len(sent) == count


def test_five_wrong_codes_kill_the_code_and_a_wrong_format_is_refused(client, sent):
    owner, sp = setup(client, sent)
    enrol(client, sp, sent)
    first = password_login(client, 'sp1', PASS).get_json()
    right = code_of(sent)
    wrong = '000000' if right != '000000' else '111111'
    for _ in range(4):
        assert client.post('/api/auth/login/verify', json={'challenge': first['challenge'], 'code': wrong}).status_code == 401
    assert client.post('/api/auth/login/verify', json={'challenge': first['challenge'], 'code': 'abc'}).status_code == 401
    # the code was used up by wrong tries; the right one no longer works
    assert client.post('/api/auth/login/verify', json={'challenge': first['challenge'], 'code': right}).status_code == 401


def test_expired_code_is_refused(app, client, sent):
    from models import LoginChallenge, db
    owner, sp = setup(client, sent)
    enrol(client, sp, sent)
    first = password_login(client, 'sp1', PASS).get_json()
    with app.app_context():
        for row in LoginChallenge.query.all():
            row.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.session.commit()
    assert client.post('/api/auth/login/verify', json={'challenge': first['challenge'], 'code': code_of(sent)}).status_code == 401


def test_code_sends_are_capped(client, sent):
    owner, sp = setup(client, sent)
    enrol(client, sp, sent)
    statuses = [password_login(client, 'sp1', PASS).status_code for _ in range(5)]
    assert statuses.count(429) >= 1 and statuses[0] == 202


def test_sms_failure_gives_no_sign_in_and_force_off_is_the_way_out(client, sent, monkeypatch):
    owner, sp = setup(client, sent)
    enrol(client, sp, sent)

    def broken(numbers, message):
        raise sms.SmsError('down')
    monkeypatch.setattr(sms, 'send_batch', broken)
    down = password_login(client, 'sp1', PASS)
    assert down.status_code == 503 and 'access_token' not in down.get_json()
    monkeypatch.setenv('SMS_LOGIN_FORCE_OFF', '1')
    assert password_login(client, 'sp1', PASS).get_json()['access_token']


def test_changing_the_phone_waits_24_hours_and_tells_the_old_number(app, client, sent):
    from models import LoginChallenge, User, db
    owner, sp = setup(client, sent)
    enrol(client, sp, sent)
    started = client.post('/api/auth/sms-login/start', headers=sp, json={'phone': NEW_PHONE, 'password': PASS})
    done = client.post('/api/auth/sms-login/confirm', headers=sp,
                       json={'challenge': started.get_json()['challenge'], 'code': code_of(sent)})
    assert done.get_json()['pending'] is True
    notice = sent[-1]
    assert notice[0] == ['+254712345678'] and 'not you' in notice[1]                 # the OLD number is warned
    login_try = password_login(client, 'sp1', PASS)
    assert login_try.status_code == 202 and sent[-1][0] == ['+254712345678']        # still the old phone
    with app.app_context():
        user = User.query.filter_by(username='sp1').first()
        user.pending_phone_at = datetime.utcnow() - timedelta(hours=25)
        for row in LoginChallenge.query.all():
            row.created_at = datetime.utcnow() - timedelta(hours=1)
        db.session.commit()
    password_login(client, 'sp1', PASS)
    assert sent[-1][0] == ['+254722000111']                                          # now the new phone


def test_enrolling_needs_the_password_and_the_right_person(client, sent):
    owner, sp = setup(client, sent)
    bad = client.post('/api/auth/sms-login/start', headers=sp, json={'phone': PHONE, 'password': 'Wrong-Pass-123'})
    assert bad.status_code == 400
    started = client.post('/api/auth/sms-login/start', headers=sp, json={'phone': PHONE, 'password': PASS})
    stolen = client.post('/api/auth/sms-login/confirm', headers=owner,
                         json={'challenge': started.get_json()['challenge'], 'code': code_of(sent)})
    assert stolen.status_code == 400                                                  # someone else's code
    assert client.post('/api/auth/sms-login/start', headers=sp, json={'phone': '123', 'password': PASS}).status_code == 400


def test_admin_reset_clears_it_but_only_in_their_own_church(app, client, sent):
    from models import User
    owner, sp = setup(client, sent)
    enrol(client, sp, sent)
    _, other = church(client, owner, 'Other Altar', 'sp2')
    with app.app_context():
        sp1_id = User.query.filter_by(username='sp1').first().id
    assert client.post('/api/auth/sms-login/reset/%d' % sp1_id, headers=other).status_code == 404
    assert client.post('/api/auth/sms-login/reset/%d' % sp1_id, headers=sp).status_code == 200
    assert password_login(client, 'sp1', PASS).get_json()['access_token']


def test_user_can_turn_it_off_with_the_password(client, sent):
    owner, sp = setup(client, sent)
    enrol(client, sp, sent)
    assert client.post('/api/auth/sms-login/disable', headers=sp, json={'password': 'Wrong-Pass-123'}).status_code == 400
    assert client.post('/api/auth/sms-login/disable', headers=sp, json={'password': PASS}).status_code == 200
    assert password_login(client, 'sp1', PASS).get_json()['access_token']
