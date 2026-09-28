"""Explicit additive reconciliation of documented historical startup DDL drift."""
from alembic import op, context
import sqlalchemy as sa
from SHARED.migration_support import baseline_schema, baseline_differences, require_adoptable, validate_foreign_keys

revision = "0002_legacy_alignment"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade():
    if context.is_offline_mode():
        raise RuntimeError("Legacy alignment needs online read-only preflight; review on a restored copy")
    bind = op.get_bind()
    metadata = baseline_schema()
    differences = baseline_differences(bind)
    require_adoptable(differences, allow_legacy=True)
    validate_foreign_keys(bind, metadata)
    # Only known missing nullable fields, missing canonical FK/indexes, safe widening,
    # and obsolete server defaults were accepted above. Never remove rows/columns.
    for table in metadata.sorted_tables:
        inspector = sa.inspect(bind)
        columns = {c["name"]: c for c in inspector.get_columns(table.name)}
        for column in table.c:
            if column.name not in columns:
                op.add_column(table.name, sa.Column(column.name, column.type, nullable=True))
        changes = [d for d in differences if d["location"].startswith(table.name + ".")]
        missing_fks = []
        actual_fks = inspector.get_foreign_keys(table.name)
        for fk in table.foreign_key_constraints:
            names = [c.name for c in fk.columns]
            if not any(f["constrained_columns"] == names for f in actual_fks):
                remote = list(fk.elements)[0].column
                missing_fks.append((f"fk_{table.name}_{names[0]}_{remote.table.name}", names, remote, fk.ondelete))
        if changes or missing_fks:
            with op.batch_alter_table(table.name) as batch:
                for d in changes:
                    column_name = d["location"].split(".")[1]
                    if d["kind"] == "modify_type":
                        batch.alter_column(column_name, existing_type=sa.String(100), type_=sa.String(255), existing_nullable=True)
                    elif d["kind"] == "modify_default":
                        batch.alter_column(column_name, existing_type=table.c[column_name].type, server_default=None)
                for name, names, remote, ondelete in missing_fks:
                    batch.create_foreign_key(name, remote.table.name, names, [remote.name], ondelete=ondelete)
        actual_indexes = {i["name"] for i in sa.inspect(bind).get_indexes(table.name)}
        for index in sorted(table.indexes, key=lambda i: i.name):
            if index.name not in actual_indexes:
                op.create_index(index.name, table.name, [c.name for c in index.columns], unique=index.unique)
    require_adoptable(baseline_differences(bind))


def downgrade():
    # Both revisions describe the same canonical baseline. Historical missing FKs,
    # missing columns, insecure defaults and shorter strings are NOT reinstated.
    # This is intentionally a schema no-op; no data is removed or narrowed.
    pass
