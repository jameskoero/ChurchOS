"""Fix Pack 7: the interface files are wired to the API that now exists."""
import os
import re

from conftest import BACKEND

REPO = os.path.dirname(BACKEND)


def text(*parts):
    with open(os.path.join(REPO, *parts), encoding='utf8') as f:
        return f.read()


def test_new_pages_and_styles_exist():
    for name in ('Dashboard.js', 'Payments.js', 'dashboard.css'):
        assert os.path.exists(os.path.join(REPO, 'frontend', 'src', 'pages', name)), name


def test_api_helpers_match_backend_routes():
    api = text('frontend', 'src', 'api.js')
    for path in ('/api/payments/mpesa/stk', '/api/payments/inbox', '/api/insights/care',
                 '/api/insights/summary', '/api/finance/${id}/verify'):
        assert path in api, path


def test_every_api_path_the_dashboard_and_payments_use_exists_on_the_server(app):
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    for needed in ('/api/payments/mpesa/stk', '/api/payments/inbox', '/api/payments/requests/<int:request_id>',
                   '/api/payments/inbox/<int:event_id>/match', '/api/payments/inbox/<int:event_id>/ignore',
                   '/api/insights/care', '/api/insights/summary', '/api/dashboard/stats',
                   '/api/finance/<int:tx_id>/verify'):
        assert needed in rules, needed


def test_payments_page_is_routed_and_in_the_menu():
    assert "path='payments'" in text('frontend', 'src', 'App.js')
    assert "path: '/payments'" in text('frontend', 'src', 'components', 'Layout.js')


def test_finance_page_can_verify_and_says_void():
    finance = text('frontend', 'src', 'pages', 'Finance.js')
    assert 'handleVerify' in finance and '>Void</button>' in finance


def test_member_form_asks_for_consent():
    members = text('frontend', 'src', 'pages', 'Members.js')
    assert 'consent: false' in members and 'consent_at' in members and "set('consent'" in members


def test_brand_colours_and_fonts_are_set():
    css = text('frontend', 'src', 'index.css')
    for token in ('--navy: #0C1445;', '--gold: #FFD84A;', '--gray-100: #F2F4FA;', 'acumin-pro'):
        assert token in css, token
    assert 'use.typekit.net/bdl1hjb.css' in text('frontend', 'public', 'index.html')


def test_dashboard_uses_no_invented_numbers():
    source = text('frontend', 'src', 'pages', 'Dashboard.js')
    assert 'Math.random' not in source
    assert re.search(r'stats\.attention', source)
