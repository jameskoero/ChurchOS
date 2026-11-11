"""Fix Pack 10: dependency security updates named by the CI scan, and a pinned CI runner."""
import os
import re

from conftest import BACKEND

REPO = os.path.dirname(BACKEND)
MINIMUMS = {'flask': '3.1.3', 'flask-cors': '6.0.0', 'python-dotenv': '1.2.2',
            'marshmallow': '3.26.2', 'werkzeug': '3.1.9', 'jinja2': '3.1.6'}


def version(text):
    return tuple(int(part) for part in text.split('.'))


def test_pinned_versions_meet_the_scan_minimums():
    pins = {}
    with open(os.path.join(BACKEND, 'requirements.txt'), encoding='utf8') as f:
        for line in f:
            m = re.match(r'^([A-Za-z0-9_.-]+)==([0-9.]+)\s*$', line)
            if m:
                pins[m.group(1).lower()] = m.group(2)
    for name, minimum in MINIMUMS.items():
        assert name in pins, name
        assert version(pins[name]) >= version(minimum), (name, pins[name], minimum)


def test_ci_runner_is_pinned():
    with open(os.path.join(REPO, '.github', 'workflows', 'ci.yml'), encoding='utf8') as f:
        text = f.read()
    assert 'ubuntu-24.04' in text and 'ubuntu-latest' not in text


def test_cors_pattern_matches_every_api_path():
    with open(os.path.join(BACKEND, 'app.py'), encoding='utf8') as f:
        source = f.read()
    assert 'r"/api/.*"' in source


def test_readme_no_longer_claims_offline_service_worker():
    path = os.path.join(REPO, 'README.md')
    if os.path.exists(path):
        text = open(path, encoding='utf8').read()
        assert 'offline-capable service worker' not in text
