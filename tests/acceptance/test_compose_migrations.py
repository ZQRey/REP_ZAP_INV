"""Deployment orchestration regression checks."""
from pathlib import Path
import yaml


def test_compose_runs_schema_migration_before_app_services():
    compose = yaml.safe_load(Path("docker-compose.yml").read_text())
    services = compose["services"]
    migration = services["database-migrations"]
    assert migration["command"] == ["alembic", "upgrade", "head"]
    assert migration["depends_on"]["postgres-db"]["condition"] == "service_healthy"
    for service_name in ("unified-server", "notification-worker"):
        dependency = services[service_name]["depends_on"]["database-migrations"]
        assert dependency["condition"] == "service_completed_successfully"
