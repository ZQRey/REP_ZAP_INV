"""Regression tests for migration/runtime configuration isolation."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def test_model_metadata_import_requires_only_database_url():
    env = os.environ.copy()
    for name in (
        "SECRET_KEY",
        "SECRET_KEY_FILE",
        "REDIS_URL",
        "REDIS_URL_FILE",
        "NETWORK_CREDENTIAL_KEY",
        "NETWORK_CREDENTIAL_KEY_FILE",
        "EVOLUTION_API_KEY",
        "EVOLUTION_API_KEY_FILE",
        "LDAP_BIND_PASSWORD",
        "LDAP_BIND_PASSWORD_FILE",
    ):
        env.pop(name, None)

    env["APP_ENV"] = "production"
    env["DATABASE_URL"] = "sqlite:///:memory:"

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from SHARED.database import Base; "
                "from SHARED import models; "
                "assert Base.metadata.tables; "
                "print('migration metadata import ok')"
            ),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "migration metadata import ok" in result.stdout
