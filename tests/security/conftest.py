import os
import secrets
import sys
import tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "CARTRIDGE"))
_temp = tempfile.TemporaryDirectory()
os.environ.update(APP_ENV="test", SECRET_KEY=secrets.token_urlsafe(48),
                  DATABASE_URL="sqlite:///" + (Path(_temp.name) / "test.db").as_posix(),
                  REDIS_URL="", DEMO_ENABLED="false", CORS_ORIGINS="https://allowed.example")
for key in ("SECRET_KEY_FILE", "DATABASE_URL_FILE", "REDIS_URL_FILE", "EVOLUTION_API_KEY_FILE", "LDAP_BIND_PASSWORD_FILE"):
    os.environ.pop(key, None)


def pytest_sessionfinish(session, exitstatus):
    for module in ("SHARED.database", "app.database", "CARTRIDGE.app.database"):
        if module in sys.modules:
            sys.modules[module].engine.dispose()
    _temp.cleanup()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from main_server import app
    from SHARED.database import Base, engine, init_db
    from SHARED.login_security import _attempts
    Base.metadata.drop_all(engine)
    init_db()
    _attempts.clear()
    with TestClient(app) as result:
        yield result


@pytest.fixture
def account(client):
    from SHARED.database import SessionLocal
    from SHARED.models import AppUser
    from SHARED.auth_service import AuthService
    password = secrets.token_urlsafe(24)
    with SessionLocal() as db:
        db.add(AppUser(username="security-test", full_name="Test", role="superadmin", auth_type="local",
                       is_active=True, password_hash=AuthService.hash_password(password)))
        db.commit()
    return {"username": "security-test", "password": password, "auth_type": "local"}
