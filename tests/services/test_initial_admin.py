import sys
from unittest.mock import patch
from SHARED.database import SessionLocal
from SHARED.models import AppUser
from SHARED.bootstrap_admin import main


def initialize():
    with patch.object(sys, 'argv', ['bootstrap_admin', '--initialize-default']):
        main()


def test_first_login_requires_password_replacement_and_restart_preserves_it(client):
    initialize()
    initialize()
    credentials = {'username': 'admin', 'password': 'admin123', 'auth_type': 'local'}
    login = client.post('/api/v1/auth/login', json=credentials)
    assert login.status_code == 200
    assert login.json()['user']['must_change_password'] is True
    headers = {'Authorization': 'Bearer ' + login.json()['access_token']}
    assert client.get('/api/v1/auth/me', headers=headers).json()['must_change_password'] is True
    for path in ('/api/branches', '/api/v1/location/stats', '/api/cartridges', '/api/v1/repair/equipment'):
        response = client.get(path, headers=headers)
        assert response.status_code == 403, response.text
        assert response.json()['detail'] == 'password_change_required'
    assert client.post('/api/v1/auth/change-password', headers=headers, json={
        'current_password': 'incorrect', 'new_password': 'changed-password-2026'
    }).status_code == 400
    assert client.post('/api/v1/auth/change-password', headers=headers, json={
        'current_password': 'admin123', 'new_password': 'admin123'
    }).status_code == 422
    assert client.post('/api/v1/auth/change-password', headers=headers, json={
        'current_password': 'admin123', 'new_password': 'changed-password-2026'
    }).status_code == 200
    assert client.get('/api/branches', headers=headers).status_code == 200
    initialize()
    assert client.post('/api/v1/auth/login', json=credentials).status_code == 401
    credentials['password'] = 'changed-password-2026'
    assert client.post('/api/v1/auth/login', json=credentials).json()['user']['must_change_password'] is False
    with SessionLocal() as db:
        assert db.query(AppUser).count() == 1


def test_existing_accounts_are_not_reset_or_given_another_admin(client, account):
    initialize()
    with SessionLocal() as db:
        assert db.query(AppUser).count() == 1
        assert db.query(AppUser).filter_by(username='admin').first() is None
    assert client.post('/api/v1/auth/login', json=account).status_code == 200
