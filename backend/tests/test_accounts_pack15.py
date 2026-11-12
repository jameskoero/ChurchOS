"""Fix Pack 15: a church's own receiving accounts, and importing a statement."""
from datetime import date, timedelta

from conftest import ADMIN_PASSWORD

STAFF = 'Staff-Login-13579'
B_PASS = 'Second-Church-2468'
D1, D2, D3 = (date.today() - timedelta(days=n) for n in (3, 2, 1))
CSV = ("Date,Transaction ID,Details,Debit,Credit\n"
       + D1.strftime('%d/%m/%Y') + ",KB123ABC,Paybill {member} tithe,,\"1,500.00\"\n"
       + D2.strftime('%d/%m/%Y') + ",KB124,Charges,50.00,\n"
       + D3.strftime('%d/%m/%Y') + ",KB125,Someone unknown,,300\n")


def login(client, username, password):
    res = client.post('/api/auth/login', json={'username': username, 'password': password})
    assert res.status_code == 200, res.get_json()
    return {'Authorization': 'Bearer ' + res.get_json()['access_token']}


def admin(client):
    return login(client, 'admin', ADMIN_PASSWORD)


def staff(client, h, username, role):
    res = client.post('/api/users/', headers=h, json={'username': username, 'email': username + '@example.org',
                                                      'password': STAFF, 'role': role})
    assert res.status_code == 201, res.get_json()
    return login(client, username, STAFF)


def member(client, h):
    return client.post('/api/members/', headers=h, json={'first_name': 'Grace', 'last_name': 'Otieno'}).get_json()


def test_accounts_can_be_saved_listed_and_removed(client):
    a = admin(client)
    bad = client.post('/api/accounts/', headers=a, json={'kind': 'bank_paybill', 'label': 'Tithes'})
    assert bad.status_code == 400
    ok = client.post('/api/accounts/', headers=a, json={
        'kind': 'bank_paybill', 'label': 'Migosi tithes', 'business_no': '522533',
        'account_no': '12345#CHR', 'bank_name': 'KCB', 'instructions': 'Add your member number'})
    assert ok.status_code == 201, ok.get_json()
    assert client.post('/api/accounts/', headers=a, json={'kind': 'nope', 'label': 'x'}).status_code == 400
    assert client.post('/api/accounts/', headers=a, json={
        'kind': 'safaricom_till', 'label': 'x', 'business_no': 'abc'}).status_code == 400
    listed = client.get('/api/accounts/', headers=a).get_json()['accounts']
    assert [r['label'] for r in listed] == ['Migosi tithes']
    assert client.delete('/api/accounts/%d' % ok.get_json()['id'], headers=a).status_code == 200
    assert client.get('/api/accounts/', headers=a).get_json()['accounts'] == []


def test_only_admin_can_change_accounts_and_churches_stay_apart(client):
    a = admin(client)
    treasurer = staff(client, a, 'treas1', 'treasurer')
    viewer = staff(client, a, 'view1', 'viewer')
    payload = {'kind': 'bank_account', 'label': 'Main', 'account_no': '999'}
    assert client.post('/api/accounts/', headers=treasurer, json=payload).status_code == 403
    made = client.post('/api/accounts/', headers=a, json=payload)
    assert made.status_code == 201
    assert client.get('/api/accounts/', headers=treasurer).status_code == 200
    assert client.get('/api/accounts/', headers=viewer).status_code == 403
    client.post('/api/churches/', headers=a, json={'name': 'Second Church', 'admin_username': 'badmin',
                'admin_email': 'b@example.org', 'admin_password': B_PASS})
    b = login(client, 'badmin', B_PASS)
    assert client.get('/api/accounts/', headers=b).get_json()['accounts'] == []
    assert client.delete('/api/accounts/%d' % made.get_json()['id'], headers=b).status_code == 404


def test_statement_import_matches_members_and_never_double_counts(client):
    a = admin(client)
    m = member(client, a)
    text = CSV.format(member=m['member_id'])
    res = client.post('/api/accounts/import-statement', headers=a, json={'csv': text})
    assert res.status_code == 200, res.get_json()
    assert res.get_json() == {'imported': 2, 'matched': 1, 'unmatched': 1, 'duplicates': 0, 'skipped': 1}
    rows = client.get('/api/finance/', headers=a).get_json()['transactions']
    assert len(rows) == 1 and rows[0]['amount'] == 1500.0 and rows[0]['member_id'] == m['id']
    assert rows[0]['transaction_date'] == D1.isoformat() and rows[0]['mpesa_ref'] == 'KB123ABC'
    inbox = client.get('/api/payments/inbox', headers=a).get_json()
    assert inbox['unmatched'] == 1 and inbox['events'][0]['amount'] == 300.0
    again = client.post('/api/accounts/import-statement', headers=a, json={'csv': text})
    assert again.get_json() == {'imported': 0, 'matched': 0, 'unmatched': 0, 'duplicates': 2, 'skipped': 1}
    assert len(client.get('/api/finance/', headers=a).get_json()['transactions']) == 1


def test_statement_import_rejects_unreadable_files_and_wrong_roles(client):
    a = admin(client)
    assert client.post('/api/accounts/import-statement', headers=a, json={'csv': ''}).status_code == 400
    bad = client.post('/api/accounts/import-statement', headers=a, json={'csv': 'name,place\nx,y'})
    assert bad.status_code == 400 and 'amount column' in bad.get_json()['error']
    viewer = staff(client, a, 'view1', 'viewer')
    assert client.post('/api/accounts/import-statement', headers=viewer, json={'csv': CSV}).status_code == 403
