"""Fix Pack 18: where churches pay ChurchOS, kept apart from church money; claims and statement matching."""
import json
from datetime import date, datetime, timedelta

import models
from conftest import ADMIN_PASSWORD

B_PASS = 'Second-Church-2468'


def login(client, username, password):
    res = client.post('/api/auth/login', json={'username': username, 'password': password})
    assert res.status_code == 200, res.get_json()
    return {'Authorization': 'Bearer ' + res.get_json()['access_token']}


def owner(client):
    return login(client, 'admin', ADMIN_PASSWORD)


def second_church(client, o):
    res = client.post('/api/churches/', headers=o, json={'name': 'Second Church', 'admin_username': 'badmin',
                      'admin_email': 'b@example.org', 'admin_password': B_PASS})
    return res.get_json()['church']['id'], login(client, 'badmin', B_PASS)


def invoice(client, o, church_id, plan='seed', months=1):
    res = client.post('/api/billing/invoices', headers=o, json={'church_id': church_id, 'plan': plan, 'months': months})
    assert res.status_code == 201, res.get_json()
    return res.get_json()


def test_only_the_owner_sets_where_churches_pay(client):
    o = owner(client)
    _, b = second_church(client, o)
    assert client.get('/api/billing/settings', headers=b).status_code == 403
    assert client.put('/api/billing/settings', headers=b, json={'paybill': '123456'}).status_code == 403
    assert client.put('/api/billing/settings', headers=o, json={'paybill': '12ab'}).status_code == 400
    saved = client.put('/api/billing/settings', headers=o, json={
        'business_name': 'ChurchOS Ltd', 'paybill': '400100', 'till': '5551234',
        'bank_name': 'Bank', 'bank_account': '0011223344', 'bank_branch': 'Kisumu'})
    assert saved.status_code == 200 and saved.get_json()['paybill'] == '400100'
    log = client.get('/api/finance/audit', headers=o).get_json()['entries']
    assert '0011223344' not in json.dumps(log)


def test_church_sees_its_billing_code_and_steps_for_each_method(client):
    o = owner(client)
    church_id, b = second_church(client, o)
    body = client.get('/api/billing/pay-to', headers=b).get_json()
    assert body['configured'] is False and body['billing_code'] == 'COS-%04d' % church_id
    client.put('/api/billing/settings', headers=o, json={'business_name': 'ChurchOS Ltd', 'paybill': '400100',
                                                         'till': '5551234', 'bank_name': 'Bank', 'bank_account': '0011223344'})
    invoice(client, o, church_id, 'seed', 2)
    body = client.get('/api/billing/pay-to', headers=b).get_json()
    kinds = [m['kind'] for m in body['methods']]
    assert kinds == ['paybill', 'till', 'bank'] and body['business_name'] == 'ChurchOS Ltd'
    paybill = body['methods'][0]
    assert paybill['account'] == 'COS-%04d' % church_id
    assert any('KES 3,000' in s for s in paybill['steps'])
    assert client.get('/api/billing/status', headers=b).get_json()['billing_code'] == 'COS-%04d' % church_id


def test_church_reports_payment_and_owner_confirms(client):
    o = owner(client)
    church_id, b = second_church(client, o)
    inv = invoice(client, o, church_id)
    path = '/api/billing/invoices/%d/claim' % inv['id']
    assert client.post(path, headers=b, json={'method': 'mpesa', 'reference': 'x'}).status_code == 400
    claimed = client.post(path, headers=b, json={'method': 'mpesa', 'reference': 'skq1abc234'})
    assert claimed.status_code == 200
    assert claimed.get_json()['status'] == 'due' and claimed.get_json()['claim_reference'] == 'SKQ1ABC234'
    third = client.post('/api/churches/', headers=o, json={'name': 'Third', 'admin_username': 'cadmin',
                        'admin_email': 'c@example.org', 'admin_password': B_PASS})
    c = login(client, 'cadmin', B_PASS)
    assert client.post(path, headers=c, json={'method': 'mpesa', 'reference': 'SKQ1ABC234'}).status_code == 404
    paid = client.post('/api/billing/invoices/%d/paid' % inv['id'], headers=o, json={'method': 'mpesa', 'reference': 'SKQ1ABC234'})
    assert paid.status_code == 200
    assert client.post(path, headers=b, json={'method': 'mpesa', 'reference': 'SKQ1ABC234'}).status_code == 409


def test_business_statement_settles_invoices_by_billing_code(client):
    o = owner(client)
    church_id, b = second_church(client, o)
    inv = invoice(client, o, church_id, 'seed', 1)
    day = (date.today() - timedelta(days=1)).strftime('%d/%m/%Y')
    code = 'COS-%04d' % church_id
    text = ('Date,Receipt No.,Details,Paid In\n'
            + day + ',SKZ9QWE123,Pay Bill from JANE Acc. ' + code + ',1500\n'
            + day + ',SKZ9QWE124,Pay Bill from SOMEONE Acc. unknown,500\n')
    assert client.post('/api/billing/import-statement', headers=b, json={'csv': text}).status_code == 403
    res = client.post('/api/billing/import-statement', headers=o, json={'csv': text})
    assert res.status_code == 200, res.get_json()
    assert res.get_json() == {'matched': 1, 'unmatched': 1, 'duplicates': 0, 'skipped': 0}
    status = client.get('/api/billing/status', headers=b).get_json()
    assert status['state'] == 'active' and status['plan'] == 'seed' and status['invoices_due'] == []
    again = client.post('/api/billing/import-statement', headers=o, json={'csv': text})
    assert again.get_json()['duplicates'] == 1 and again.get_json()['matched'] == 0


def test_platform_details_never_appear_in_church_accounts(client):
    o = owner(client)
    _, b = second_church(client, o)
    client.put('/api/billing/settings', headers=o, json={'paybill': '400100'})
    assert client.get('/api/accounts/', headers=b).get_json()['accounts'] == []
    assert client.get('/api/accounts/', headers=o).get_json()['accounts'] == []
