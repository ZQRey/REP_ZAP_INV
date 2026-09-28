"""Use the canonical engine and metadata; never create a second pool/registry."""
from alembic import context
from sqlalchemy import text
from SHARED.database import Base, engine
from SHARED import models  # register canonical mapped classes

config = context.config
target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    # Evolution/PostGIS may share a server/schema: never propose dropping their tables.
    if type_ == "table":
        return name in target_metadata.tables
    return True


def run_transaction(connection):
    with connection.begin():
        if connection.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(734821906)"))
            connection.execute(text("SET LOCAL lock_timeout = '15s'"))
        context.configure(connection=connection, target_metadata=target_metadata,
                          compare_type=True, compare_server_default=True,
                          render_as_batch=connection.dialect.name == "sqlite",
                          include_object=include_object)
        with context.begin_transaction():
            context.run_migrations()
        if connection.dialect.name == "sqlite":
            if connection.exec_driver_sql("PRAGMA foreign_key_check").first():
                raise RuntimeError("SQLite foreign-key validation failed")


def run(connection):
    sqlite = connection.dialect.name == "sqlite"
    if sqlite:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
    try:
        run_transaction(connection)
    finally:
        if sqlite:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()


if context.is_offline_mode():
    context.configure(url=engine.url, target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get("connection") is not None:
    run(config.attributes["connection"])
else:
    with engine.connect() as connection:
        run(connection)
