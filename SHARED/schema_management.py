"""Read-only startup gate and explicit Alembic configuration helpers."""
from pathlib import Path
from contextlib import asynccontextmanager
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[1]


def alembic_config():
    return Config(str(ROOT / "alembic.ini"))


def require_schema_head(engine):
    expected = set(ScriptDirectory.from_config(alembic_config()).get_heads())
    with engine.connect() as connection:
        actual = set(MigrationContext.configure(connection).get_current_heads())
    if actual != expected:
        raise RuntimeError("Database schema is not at Alembic head. Follow DATABASE_MIGRATIONS.md; "
                           "run an explicit reviewed alembic upgrade head before starting the application.")


@asynccontextmanager
async def schema_lifespan(app):
    from SHARED.database import engine
    require_schema_head(engine)
    yield
