import os
import secrets
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("path", ["/api/v1/auth/login", "/api/auth/login", "/cartridges/api/auth/login"])
def test_login_and_strict_token(client, account, path):
    from SHARED.tokens import decode_access_token
    result = client.post(path, json=account)
    assert result.status_code == 200, result.text
    assert result.headers["Cache-Control"] == "no-store"
    token = result.json()["access_token"]
    claims = decode_access_token(token)
    assert claims["exp"] - claims["iat"] == 1800
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token}).status_code == 200
    assert client.get("/api/v1/auth/me", params={"token": token}).status_code == 400


def test_no_implicit_admin(client):
    from SHARED.database import SessionLocal
    from SHARED.models import AppUser
    with SessionLocal() as db:
        assert db.query(AppUser).count() == 0


def test_login_rate_limit_shared_across_aliases(client):
    for n in range(10):
        path = ["/api/v1/auth/login", "/api/auth/login", "/cartridges/api/auth/login"][n % 3]
        assert client.post(path, json={"username": "unknown", "password": "invalid"}).status_code == 401
    result = client.post("/api/auth/login", json={"username": "UNKNOWN", "password": "invalid"})
    assert result.status_code == 429
    assert result.headers["Retry-After"] == "300"


def test_inactive_and_provider_collision(client, account):
    from SHARED.database import SessionLocal
    from SHARED.models import AppUser
    with SessionLocal() as db:
        user = db.query(AppUser).first()
        user.is_active = False
        db.commit()
    for path in ("/api/auth/login", "/api/v1/auth/login"):
        assert client.post(path, json=account).status_code == 401


def test_jwt_rejects_legacy_and_invalid_tokens():
    import jwt
    from SHARED.tokens import create_access_token, decode_access_token
    from SHARED.security_config import SECRET_KEY
    assert decode_access_token(jwt.encode({"sub": "test"}, SECRET_KEY, algorithm="HS256")) is None
    assert decode_access_token("bad-token") is None
    with pytest.raises(ValueError):
        create_access_token({"sub": "test"}, timedelta(days=1))


def test_missing_production_secrets_fail_without_exposure():
    env = {k: v for k, v in os.environ.items() if k not in ("SECRET_KEY", "DATABASE_URL", "REDIS_URL")}
    env["APP_ENV"] = "production"
    result = subprocess.run([sys.executable, "-c", "import SHARED.security_config"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "Required configuration missing: SECRET_KEY" in result.stderr


def test_settings_never_return_secrets(client, account):
    secret = secrets.token_urlsafe(24)
    assert client.get("/api/settings").status_code == 401
    token = client.post("/api/v1/auth/login", json=account).json()["access_token"]
    headers = {"Authorization": "Bearer " + token}
    response = client.put("/api/settings", headers=headers, json={"settings": {
        "ad_bind_password": secret, "wa_api_key": secret, "unknown_private_key": secret}})
    assert response.status_code == 200, response.text
    assert secret not in response.text
    assert secret not in client.get("/api/settings", headers=headers).text


def test_validation_does_not_echo_password(client):
    secret = secrets.token_urlsafe(24)
    response = client.post("/api/auth/login", json={"username": "test", "password": {"secret": secret}})
    assert response.status_code == 422
    assert secret not in response.text


def test_switch_response_models_exclude_credentials():
    from REPAIR.app.schemas import SwitchConfigResponse, EquipmentResponse
    from LOCATION.app.schemas import NetworkSwitchResponse
    sensitive = {"password", "username", "snmp_community", "api_key", "extra_params"}
    assert not sensitive.intersection(SwitchConfigResponse.model_fields)
    assert not sensitive.intersection(NetworkSwitchResponse.model_fields)
    assert "SwitchConfigResponse" in str(EquipmentResponse.model_fields["switch_config"].annotation)


def test_tls_and_ssh_verification(monkeypatch):
    import ssl
    import paramiko
    from SHARED.transport_security import tls_context, ssh_client
    assert tls_context().verify_mode == ssl.CERT_REQUIRED
    assert tls_context().check_hostname
    fake = Mock()
    monkeypatch.setattr(paramiko, "SSHClient", lambda: fake)
    ssh_client()
    fake.load_system_host_keys.assert_called_once()
    assert isinstance(fake.set_missing_host_key_policy.call_args.args[0], paramiko.RejectPolicy)


def test_demo_disabled(client):
    from SHARED.ldap_service import LDAPService
    from SHARED.database import SessionLocal
    from SHARED.models import Asset
    from LOCATION.app.services.switch_integration_service import SwitchIntegrationService
    with SessionLocal() as db:
        assert LDAPService._seed_mock_computers(db, None)["status"] == "error"
        assert db.query(Asset).count() == 0
        with pytest.raises(ValueError, match="disabled"):
            SwitchIntegrationService.simulate_roaming_event(db, 1, 1, "00:11:22:33:44:55")


def test_cors(client):
    headers = {"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"}
    assert client.options("/api/auth/login", headers=headers).status_code == 400
    headers["Origin"] = "https://allowed.example"
    assert client.options("/api/auth/login", headers=headers).headers["access-control-allow-origin"] == headers["Origin"]


def test_deployment_no_internal_ports_or_tracked_keys():
    import yaml
    for path in (ROOT / "docker-compose.yml", ROOT / "CARTRIDGE/docker-compose.yml"):
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        for name, service in config["services"].items():
            if name != "nginx-proxy":
                assert not service.get("ports"), name
    assert not (ROOT / "nginx/ssl/key.pem").exists()


@pytest.mark.parametrize("path", ["/api/cartridges", "/api/branches", "/cartridges/api/settings", "/print/act/1", "/repair/print/repair-act/1"])
def test_business_data_requires_auth(client, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_redis_failure_is_closed(monkeypatch):
    from SHARED import login_security as limiter
    from fastapi import HTTPException
    monkeypatch.setattr(limiter, "REDIS_URL", "redis://localhost")
    fake = Mock()
    fake.eval.side_effect = ConnectionError("unavailable")
    monkeypatch.setattr(limiter, "_redis", fake)
    with pytest.raises(HTTPException) as exc:
        limiter.check_login(SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")), "test")
    assert exc.value.status_code == 503


def test_rate_limit_is_atomic_under_concurrency(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from fastapi import HTTPException
    from SHARED import login_security as limiter
    limiter._attempts.clear()
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    def attempt(n):
        try:
            limiter.check_login(request, "same-account")
            return True
        except HTTPException as exc:
            assert exc.status_code == 429
            return False
    with ThreadPoolExecutor(max_workers=12) as pool:
        assert sum(pool.map(attempt, range(30))) == 10


def test_ldap_requires_verified_tls(monkeypatch):
    import ssl
    import ldap3
    from SHARED.transport_security import ldap_connection
    factory = Mock()
    monkeypatch.setattr(ldap3, "Connection", factory)
    for secure in (False, True):
        ldap_connection("dc.example", 636 if secure else 389, secure, "test", secrets.token_urlsafe(24))
        server = factory.call_args.args[0]
        assert server.tls.validate == ssl.CERT_REQUIRED
        assert factory.call_args.kwargs["auto_bind"] == (ldap3.AUTO_BIND_NO_TLS if secure else ldap3.AUTO_BIND_TLS_BEFORE_BIND)


def test_logs_redact_secrets(caplog):
    import logging
    from SHARED.logging_security import install, register_secret
    install()
    value = secrets.token_urlsafe(24)
    register_secret(value)
    with caplog.at_level(logging.WARNING):
        logging.warning("password=%s", value)
        try:
            raise ValueError(value)
        except ValueError:
            logging.exception("Integration failed")
    assert value not in caplog.text
    assert "REDACTED" in caplog.text


def test_password_hash_compatibility():
    import hashlib
    from SHARED.passwords import hash_password, verify_password
    value = secrets.token_urlsafe(24)
    salt = secrets.token_hex(16)
    old = salt + "$" + hashlib.pbkdf2_hmac("sha256", value.encode(), salt.encode(), 100000).hex()
    assert verify_password(value, old)
    assert verify_password(value, hash_password(value))
    assert not verify_password("wrong", old)


def test_network_allowlist(monkeypatch):
    from SHARED import network_policy
    monkeypatch.setattr(network_policy, "PRODUCTION", True)
    monkeypatch.setenv("NETWORK_ALLOWED_CIDRS", "10.20.30.0/24")
    network_policy.validate_device_address("10.20.30.7")
    for address in ("127.0.0.1", "169.254.169.254", "10.20.31.1", "attacker.example"):
        with pytest.raises(ValueError):
            network_policy.validate_device_address(address)


def test_actual_network_api_does_not_serialize_credentials(client, account):
    from SHARED.database import SessionLocal
    from SHARED.models import Asset, AssetType, NetworkSwitch, Floor, Branch
    secret = secrets.token_urlsafe(24)
    with SessionLocal() as db:
        branch = db.query(Branch).first()
        floor = Floor(branch_id=branch.id, name="Test", floor_number=1)
        db.add(floor)
        db.flush()
        asset = Asset(inventory_number="SEC-1", name="Switch", asset_type=AssetType.SWITCH, branch_id=branch.id, floor_id=floor.id)
        db.add(asset)
        db.flush()
        db.add(NetworkSwitch(asset_id=asset.id, ip_address="10.20.30.7", username=secret, password=secret,
                             snmp_community=secret, total_ports=24, extra_params={"api_key": secret},
                             last_poll_status="error", last_poll_message=secret))
        db.commit()
        floor_id, asset_id = floor.id, asset.id
    token = client.post("/api/auth/login", json=account).json()["access_token"]
    for path in (f"/api/v1/location/floors/{floor_id}/switches", f"/api/v1/repair/equipment/{asset_id}", "/api/v1/repair/equipment"):
        response = client.get(path, headers={"Authorization": "Bearer " + token})
        assert response.status_code == 200, response.text
        assert secret not in response.text


@pytest.mark.parametrize("override", [{"DEMO_ENABLED": "true"}, {"DEBUG": "true"}, {"CORS_ORIGINS": "*"}, {"ACCESS_TOKEN_EXPIRE_MINUTES": "1440"}, {"WHATSAPP_ENABLED": "true", "EVOLUTION_API_KEY": ""}, {"LDAP_ENABLED": "true", "LDAP_BIND_PASSWORD": ""}])
def test_production_configuration_rejects_unsafe_values(override):
    env = dict(os.environ)
    value = secrets.token_urlsafe(24)
    env.update(APP_ENV="production", DATABASE_URL=f"postgresql://service:{value}@database/app",
               REDIS_URL=f"redis://:{value}@redis/0")
    env.update(override)
    result = subprocess.run([sys.executable, "-c", "import SHARED.security_config"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert value not in result.stderr


@pytest.mark.parametrize("mutation", ["expired", "issuer", "audience", "missing-exp", "wrong-key", "wrong-algorithm"])
def test_jwt_policy(mutation):
    import jwt
    import time
    from SHARED.tokens import create_access_token, decode_access_token
    from SHARED.security_config import SECRET_KEY
    claims = decode_access_token(create_access_token({"sub": "test"}))
    key, algorithm = SECRET_KEY, "HS256"
    if mutation == "expired": claims["exp"] = int(time.time()) - 1
    if mutation == "issuer": claims["iss"] = "another-app"
    if mutation == "audience": claims["aud"] = "another-client"
    if mutation == "missing-exp": del claims["exp"]
    if mutation == "wrong-key": key = secrets.token_urlsafe(48)
    if mutation == "wrong-algorithm": algorithm = "HS384"
    assert decode_access_token(jwt.encode(claims, key, algorithm=algorithm)) is None


def test_ad_cannot_take_over_local_identity(client, account, monkeypatch):
    from app.services.ldap_service import LDAPService
    monkeypatch.setattr(LDAPService, "authenticate_ad_user", lambda **kw: (True, account["username"], {}))
    for path in ("/api/auth/login", "/api/v1/auth/login"):
        response = client.post(path, json={**account, "auth_type": "ad"})
        assert response.status_code == 401


def test_unknown_ssh_host_is_rejected():
    import paramiko
    from SHARED.transport_security import ssh_client
    client = ssh_client()
    client._transport = Mock()
    with pytest.raises(paramiko.SSHException):
        client._policy.missing_host_key(client, "unknown.example", paramiko.RSAKey.generate(2048))


def test_network_exception_does_not_leak_credentials(monkeypatch):
    from LOCATION.app.services.switch_integration_service import SwitchIntegrationService
    import LOCATION.app.services.switch_integration_service as module
    secret = secrets.token_urlsafe(24)
    fake_socket = Mock()
    fake_socket.connect.side_effect = ConnectionError(secret)
    monkeypatch.setattr(module.socket, "socket", lambda *a, **k: fake_socket)
    result = SwitchIntegrationService.test_connection("10.20.30.1", "ssh_cli", username="user", password=secret)
    assert not result["success"]
    assert secret not in str(result)


def test_standalone_cartridge_entrypoint():
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    result = subprocess.run([sys.executable, "-c", "import app.main; print(app.main.app.title)"],
                            cwd=ROOT / "CARTRIDGE", env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "Cartridge Tracker" in result.stdout


def test_network_credentials_are_encrypted_at_rest(client):
    from SHARED.database import SessionLocal
    from SHARED.models import Asset, NetworkSwitch, Branch
    secret = secrets.token_urlsafe(24)
    with SessionLocal() as db:
        branch = db.query(Branch).first()
        asset = Asset(inventory_number="ENC-SW", name="Encrypted switch", branch_id=branch.id)
        db.add(asset); db.flush()
        switch = NetworkSwitch(asset_id=asset.id, ip_address="10.20.30.8", password=secret, snmp_community=secret)
        db.add(switch); db.commit()
        switch_id = switch.id
    from sqlalchemy import text
    from SHARED.database import engine
    with engine.connect() as connection:
        row = connection.execute(text("SELECT password, snmp_community FROM network_switches WHERE id=:id"), {"id": switch_id}).one()
        assert secret not in row.password
        assert secret not in row.snmp_community
        assert row.password.startswith("enc:v1:")
        assert row.snmp_community.startswith("enc:v1:")
    with SessionLocal() as db:
        switch = db.get(NetworkSwitch, switch_id)
        assert switch.password == secret
        assert switch.snmp_community == secret
