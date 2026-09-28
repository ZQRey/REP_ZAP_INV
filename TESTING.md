# Testing

The repository uses four CI gates:

1. **Static/security** — project security scanners, authorization audit, Ruff fatal-error checks, Bandit, dependency audit and JavaScript syntax.
2. **Unit/API/security** — the normal pytest suite using an isolated temporary database and mocked external integrations.
3. **PostgreSQL integration** — Alembic upgrade/downgrade, schema constraints, concurrent document numbering and branch-isolation tests against disposable PostgreSQL.
4. **Docker build** — verifies that the production image remains buildable.

## Local commands

    python -m pip install -r requirements-dev.txt
    python -m pytest
    python scripts/check_security.py
    python scripts/audit_authorization.py
    ruff check SHARED CARTRIDGE REPAIR LOCATION PORTAL main_server.py
    bandit -c pyproject.toml -r SHARED CARTRIDGE REPAIR LOCATION main_server.py
    pip-audit -r requirements.txt

The PostgreSQL migration suite intentionally refuses to run against a non-loopback or incorrectly named database. Use scripts/start_test_postgres.py in CI/dev environments rather than pointing it at production.

External AD, Evolution API, switches and SNMP/SSH devices must be mocked in automated tests. Real-device validation is a separate manual acceptance activity.
