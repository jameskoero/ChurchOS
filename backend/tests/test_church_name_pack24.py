"""Fix Pack 24: the church name shown is the signed-in church, never the first one in a list."""
import os

from conftest import BACKEND

SRC = os.path.join(os.path.dirname(BACKEND), 'frontend', 'src')


def test_dashboard_and_menu_name_the_signed_in_church():
    for parts in (('pages', 'Dashboard.js'), ('components', 'Layout.js')):
        text = open(os.path.join(SRC, *parts), encoding='utf8').read()
        assert 'churches?.[0]' not in text and 'governanceAPI.church()' in text, parts


def test_church_endpoint_names_the_signed_in_church(client):
    from conftest import ADMIN_PASSWORD
    res = client.post('/api/auth/login', json={'username': 'admin', 'password': ADMIN_PASSWORD})
    h = {'Authorization': 'Bearer ' + res.get_json()['access_token']}
    mine = client.get('/api/governance/church', headers=h).get_json()['church']
    client.post('/api/churches/', headers=h, json={'name': 'Zzz Newest Church'})
    assert client.get('/api/governance/church', headers=h).get_json()['church'] == mine
