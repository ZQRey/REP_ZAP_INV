"""Frozen canonical schema; existing database adoption requires explicit verification.

Production schema was not accessible. This baseline describes main c07e978,
not a claimed observation of a deployed database. See DATABASE_MIGRATIONS.md.
"""
from alembic import op, context
import sqlalchemy as sa
from SHARED.migration_support import baseline_schema, baseline_differences, require_adoptable

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    metadata = baseline_schema()
    if not context.is_offline_mode():
        existing = set(sa.inspect(op.get_bind()).get_table_names()) & set(metadata.tables)
        if existing:
            args = context.get_x_argument(as_dictionary=True)
            if args.get("adopt_existing") != "true":
                raise RuntimeError("Existing schema: run the read-only baseline audit, then explicitly use -x adopt_existing=true")
            differences = baseline_differences(op.get_bind())
            require_adoptable(differences, allow_legacy=args.get("accept_legacy_drift") == "true")
            return  # only the Alembic version is recorded; no application DDL/DML
    metadata.create_all(op.get_bind(), checkfirst=False)


def downgrade():
    if context.get_x_argument(as_dictionary=True).get("allow_destructive") != "true":
        raise RuntimeError("Baseline downgrade DROPS ALL APPLICATION DATA; requires -x allow_destructive=true")
    baseline_schema().drop_all(op.get_bind(), checkfirst=False)
