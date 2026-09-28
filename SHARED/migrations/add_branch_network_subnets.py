"""Bridge a legacy-only Cartridge schema to the existing unified Branch model."""
import argparse
from sqlalchemy import inspect, text


def needs_migration(connection):
    inspector = inspect(connection)
    return inspector.has_table("branches") and "network_subnets" not in {
        column["name"] for column in inspector.get_columns("branches")
    }


def require_compatible_branches(engine):
    with engine.connect() as connection:
        if needs_migration(connection):
            raise RuntimeError(
                "Legacy branches schema lacks network_subnets. Back up the database, then run "
                "python -m SHARED.migrations.add_branch_network_subnets --check; "
                "use --apply explicitly to add the nullable JSON column. No startup writes performed."
            )


def apply_migration(engine):
    """Idempotent sequential execution; run once offline, never concurrently with startup."""
    if engine.dialect.name not in {"sqlite", "postgresql"}:
        raise RuntimeError("Only SQLite and PostgreSQL are supported")
    with engine.begin() as connection:
        if not needs_migration(connection):
            return False
        connection.execute(text("ALTER TABLE branches ADD COLUMN network_subnets JSON"))
        return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    from SHARED.database import engine
    try:
        if args.apply:
            print("Column added; existing rows preserved" if apply_migration(engine) else "No migration required")
            return 0
        with engine.connect() as connection:
            missing = needs_migration(connection)
        print("Migration required: branches.network_subnets" if missing else "No migration required")
        return 1 if missing else 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
