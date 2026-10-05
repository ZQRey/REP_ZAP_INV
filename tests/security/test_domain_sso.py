import base64
from unittest.mock import Mock
import pytest
from SHARED import domain_sso as sso


@pytest.fixture
def enabled_sso(client, monkeypatch, tmp_path):
    keytab = tmp_path / 'http.keytab'
    keytab.write_bytes(b'\x05\x02example')
    monkeypatch.setattr(sso, 'KEYTAB', keytab)
    values = {'sso_enabled': 'true', 'sso_hostname': 'it.example.local', 'sso_realm': 'EXAMPLE.LOCAL',
              'ad_host': 'ldaps://dc.example.local', 'ad_base_dn': 'DC=example,DC=local'}
    monkeypatch.setattr(sso.SettingsService, 'get_all', lambda db: values)
    return values


def test_disabled_sso_preserves_manual_login(client):
    assert client.get('/api/v1/auth/sso/status').json() == {'enabled': False}
    assert client.get('/api/v1/auth/sso').status_code == 404


def test_sso_requires_https_hostname_and_verified_ticket(client, enabled_sso, monkeypatch):
    assert client.get('/api/v1/auth/sso').status_code == 403
    assert client.get('/api/v1/auth/sso/status').json() == {'enabled': False}
    url = 'https://it.example.local/api/v1/auth/sso'
    result = client.get(url, headers={'X-Remote-User': 'admin@EXAMPLE.LOCAL'})
    assert result.status_code == 401
    assert result.headers['WWW-Authenticate'] == 'Negotiate'
    assert result.headers['Cache-Control'] == 'no-store'
    assert client.get(url, headers={'Authorization': 'Negotiate malformed!'}).status_code == 401
    monkeypatch.setattr(sso, 'accept_ticket', Mock(side_effect=ValueError('invalid ticket')))
    assert client.get(url, headers={'Authorization': 'Negotiate ' + base64.b64encode(b'ticket').decode()}).status_code == 401


def test_verified_sso_creates_least_privileged_user(client, enabled_sso, monkeypatch):
    monkeypatch.setattr(sso, 'accept_ticket', lambda ticket, values: ('alice@EXAMPLE.LOCAL', b'mutual'))
    result = client.get('https://it.example.local/api/v1/auth/sso', headers={'Authorization': 'Negotiate dGlja2V0'})
    assert result.status_code == 200, result.text
    assert result.headers['WWW-Authenticate'] == 'Negotiate bXV0dWFs'
    token = result.json()['access_token']
    user = client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer ' + token}).json()
    assert user['username'] == 'alice'
    assert user['role'] == 'user'
    assert user['branch_id'] is None
    assert user['auth_type'] == 'ad'


@pytest.mark.parametrize('principal', ['alice@OTHER.LOCAL', 'HTTP/it.example.local@EXAMPLE.LOCAL', 'alice'])
def test_sso_rejects_foreign_realm_and_service_principal(client, enabled_sso, monkeypatch, principal):
    monkeypatch.setattr(sso, 'accept_ticket', lambda ticket, values: (principal, None))
    assert client.get('https://it.example.local/api/v1/auth/sso', headers={'Authorization': 'Negotiate dGlja2V0'}).status_code == 403


def test_sso_cannot_take_over_local_admin(client, account, enabled_sso, monkeypatch):
    monkeypatch.setattr(sso, 'accept_ticket', lambda ticket, values: ('security-test@EXAMPLE.LOCAL', None))
    assert client.get('https://it.example.local/api/v1/auth/sso', headers={'Authorization': 'Negotiate dGlja2V0'}).status_code == 403


@pytest.mark.parametrize('active', [True, False])
def test_existing_ad_permissions_are_preserved(client, enabled_sso, monkeypatch, active):
    from SHARED.database import SessionLocal
    from SHARED.models import AppUser
    with SessionLocal() as db:
        db.add(AppUser(username='alice', full_name='Alice', auth_type='ad', role='operator', is_active=active))
        db.commit()
    monkeypatch.setattr(sso, 'accept_ticket', lambda ticket, values: ('alice@EXAMPLE.LOCAL', None))
    result = client.get('https://it.example.local/api/v1/auth/sso', headers={'Authorization': 'Negotiate dGlja2V0'})
    assert result.status_code == (200 if active else 403)
    if active:
        token = result.json()['access_token']
        assert client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer ' + token}).json()['role'] == 'operator'


def test_keytab_upload_is_superadmin_only(client, account, monkeypatch, tmp_path):
    keytab = tmp_path / 'sso' / 'http.keytab'
    monkeypatch.setattr(sso, 'KEYTAB', keytab)
    url = '/api/v1/auth/sso/keytab'
    assert client.post(url, files={'file': ('http.keytab', b'\x05\x02example')}).status_code == 401
    token = client.post('/api/v1/auth/login', json=account).json()['access_token']
    headers = {'Authorization': 'Bearer ' + token}
    assert client.post(url, headers=headers, files={'file': ('wrong.keytab', b'wrong')}).status_code == 422
    assert client.post(url, headers=headers, files={'file': ('../../http.keytab', b'\x05\x02example')}).status_code == 200
    assert keytab.read_bytes() == b'\x05\x02example'


def test_sso_enable_requires_ldap_and_keytab(client, monkeypatch, tmp_path):
    monkeypatch.setattr(sso, 'KEYTAB', tmp_path / 'missing')
    with pytest.raises(Exception) as error:
        sso.validate_settings({'sso_enabled': 'true'})
    assert error.value.status_code == 422
