"""Fix Pack 9: the cobalt interface is in place and the old palette is gone."""
import os
import re

from conftest import BACKEND

REPO = os.path.dirname(BACKEND)
SRC = os.path.join(REPO, 'frontend', 'src')


def text(*parts):
    with open(os.path.join(REPO, *parts), encoding='utf8') as f:
        return f.read()


def test_new_shell_dashboard_and_login_use_their_styles():
    assert "import './layout.css'" in text('frontend', 'src', 'components', 'Layout.js')
    assert "import './home.css'" in text('frontend', 'src', 'pages', 'Dashboard.js')
    assert "import './login.css'" in text('frontend', 'src', 'pages', 'Login.js')
    for rel in (('components', 'layout.css'), ('pages', 'home.css'), ('pages', 'login.css')):
        assert os.path.exists(os.path.join(SRC, *rel)), rel


def test_brand_palette_and_font_are_set():
    css = text('frontend', 'src', 'index.css')
    for token in ('--navy: #0C1445;', '--cobalt: #2339F5;', '--gold: #FFD84A;', '--gray-100: #F2F4FA;', "'acumin-pro'"):
        assert token in css, token
    assert 'use.typekit.net/bdl1hjb.css' in text('frontend', 'public', 'index.html')


def test_old_palette_is_gone_from_the_source():
    old = ('#0D1B2A', '#C9A84C', '#1A2744', '#D9A441', '#E2C270', '#28A745', '#DC3545')
    for root, _, names in os.walk(SRC):
        for name in names:
            if name.endswith(('.js', '.css')):
                body = open(os.path.join(root, name), encoding='utf8').read().upper()
                for color in old:
                    assert color.upper() not in body, (name, color)


def test_dashboard_never_invents_numbers():
    source = text('frontend', 'src', 'pages', 'Dashboard.js')
    assert 'Math.random' not in source and 'placeholder' not in source.lower()
    assert 'stats.attention' in source or 'attention' in source


def test_version_marker_exists_for_deploy_checks():
    assert 'pack9' in text('frontend', 'public', 'version.txt')


def test_payments_nav_is_limited_to_admin_and_treasurer():
    layout = text('frontend', 'src', 'components', 'Layout.js')
    assert re.search(r"path: '/payments'.*only: \['admin', 'treasurer'\]", layout)
