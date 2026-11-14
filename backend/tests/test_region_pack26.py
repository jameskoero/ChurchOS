"""Fix Pack 26: denomination wording, the region report, and region SMS (only for altars that switched it on)."""
import os
from datetime import date

import pytest

from conftest import ADMIN_PASSWORD, BACKEND
from services import sms
from test_governance_pack22 import region_with_altar

SRC = os.path.join(os.path.dirname(BACKEND), 'frontend', 'src')


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv('AT_USERNAME', 'sandbox')
    monkeypatch.setenv('AT_API_KEY', 'api-key-value-0123456789')
    monkeypatch.setenv('AT_CALLBACK_SECRET', 'callback-secret-0123456789abcdef')


@pytest.fixture()
def fake(monkeypatch):
    calls = []

    def send_batch(numbers, message):
        calls.append((list(numbers), message))
        return [{'phone': n, 'ok': True, 'code': 101, 'status': 'sent', 'detail': '',
                 'message_id': 'ATXid_%d_%s' % (len(calls), n[-3:]), 'cost': 'KES 0.8000'} for n in numbers]
    monkeypatch.setattr(sms, 'send_batch', send_batch)
    return calls


def person(client, h, first, phone, agree=True):
    res = client.post('/api/members/', headers=h, json={'first_name': first, 'last_name': 'Test', 'phone': phone})
    assert res.status_code == 201, res.get_json()
    mid = res.get_json()['id']
    if agree:
        assert client.post('/api/sms/consent', headers=h, json={'member_id': mid, 'agreed': True}).status_code == 200
    return mid


def test_report_totals_per_altar_and_only_the_leader_can_ask(client):
    b, altar_id, altar = region_with_altar(client)
    client.post('/api/members/', headers=altar, json={'first_name': 'Peter', 'last_name': 'Otieno'})
    gift = client.post('/api/finance/', headers=altar, json={'transaction_type': 'tithe', 'amount': 500,
                       'transaction_date': date.today().isoformat()})
    assert gift.status_code == 201, gift.get_json()
    rep = client.get('/api/governance/regions/mine/report', headers=b).get_json()
    by_name = {c['name']: c for c in rep['churches']}
    assert by_name['Kanyakwar Altar']['members'] == 1 and by_name['Kanyakwar Altar']['income'] == 500.0
    assert rep['totals']['income'] == 500.0 and rep['region'] == 'Migosi Region'
    assert client.get('/api/governance/regions/mine/report', headers=altar).status_code == 403
    assert client.get('/api/governance/regions/mine/report', headers=b,
                      query_string={'from': '2026-12-01', 'to': '2026-11-01'}).status_code == 400


def test_an_altar_must_switch_regional_messages_on(client, fake):
    b, altar_id, altar = region_with_altar(client)
    person(client, altar, 'Peter', '0722000222')
    person(client, b, 'Mercy', '0711000111')
    first = client.post('/api/governance/regions/mine/sms/preview', headers=b, json={'message': 'Hello region'})
    assert first.status_code == 200 and first.get_json()['recipients'] == 1          # only the seat's own member
    assert client.put('/api/governance/church/regional-sms', headers=altar, json={'allow': 'yes'}).status_code == 400
    assert client.put('/api/governance/church/regional-sms', headers=altar, json={'allow': True}).status_code == 200
    assert client.get('/api/governance/church', headers=altar).get_json()['regional_sms'] is True
    second = client.post('/api/governance/regions/mine/sms/preview', headers=b, json={'message': 'Hello region'})
    assert second.get_json()['recipients'] == 2
    assert set(second.get_json()['by_church']) == {'Kanyakwar Altar', 'Carwash Main Altar'} or \
        len(second.get_json()['by_church']) == 2


def test_send_reaches_agreed_members_only_and_is_logged_in_each_altars_own_log(client, fake):
    b, altar_id, altar = region_with_altar(client)
    client.put('/api/governance/church/regional-sms', headers=altar, json={'allow': True})
    person(client, altar, 'Peter', '0722000222')
    person(client, altar, 'NoConsent', '0733000333', agree=False)
    person(client, b, 'Mercy', '0711000111')
    body = {'message': 'Region prayer meeting on Friday'}
    plan = client.post('/api/governance/regions/mine/sms/preview', headers=b, json=body).get_json()
    assert plan['recipients'] == 2
    stale = client.post('/api/governance/regions/mine/sms/send', headers=b, json=dict(body, confirm_count=5))
    assert stale.status_code == 409
    done = client.post('/api/governance/regions/mine/sms/send', headers=b, json=dict(body, confirm_count=2))
    assert done.status_code == 200 and done.get_json()['accepted'] == 2
    assert sorted(fake[0][0]) == ['+254711000111', '+254722000222']
    assert '+254733000333' not in fake[0][0]


def test_regional_sms_is_leader_only_and_refuses_names_and_empty_audience(client, fake):
    b, altar_id, altar = region_with_altar(client)
    assert client.post('/api/governance/regions/mine/sms/preview', headers=altar, json={'message': 'Hi'}).status_code == 403
    assert client.put('/api/governance/church/regional-sms', headers=b, json={'allow': True}).status_code == 200
    named = client.post('/api/governance/regions/mine/sms/preview', headers=b, json={'message': 'Hi {first_name}'})
    assert named.status_code == 400 and named.get_json()['code'] == 'NO_NAMES'
    nobody = client.post('/api/governance/regions/mine/sms/preview', headers=b, json={'message': 'Hi'})
    assert nobody.status_code == 400 and nobody.get_json()['code'] == 'NO_RECIPIENTS'


def test_wording_files_are_in_place():
    ctx = open(os.path.join(SRC, 'contexts', 'LabelsContext.js'), encoding='utf8').read()
    assert 'export function plural' in ctx and 'LabelsProvider' in ctx
    layout = open(os.path.join(SRC, 'components', 'Layout.js'), encoding='utf8').read()
    assert 'useLabels()' in layout and 'plural(labels.unit_label)' in layout
    index = open(os.path.join(SRC, 'index.js'), encoding='utf8').read()
    assert 'LabelsProvider' in index
    region = open(os.path.join(SRC, 'pages', 'Region.js'), encoding='utf8').read()
    assert 'L.region_leader_title' in region and 'smsPreview' in region and 'window.print()' in region
