"""Reject invalid legacy rows, add integrity constraints and atomic document counters."""
import json
from pathlib import Path
from alembic import op, context
import sqlalchemy as sa
from SHARED.migration_support import baseline_schema, validate_foreign_keys

revision = "0003_integrity_numbering"
down_revision = "0002_legacy_alignment"
branch_labels = None
depends_on = None
SPEC = json.loads((Path(__file__).resolve().parents[1] / "integrity_spec.json").read_text(encoding="utf-8"))


def preflight(bind):
    metadata = baseline_schema()
    validate_foreign_keys(bind, metadata)
    for name, rules in SPEC.items():
        table = metadata.tables[name]
        for column in rules.get("not_null", []):
            if bind.execute(sa.select(sa.literal(1)).select_from(table).where(table.c[column].is_(None)).limit(1)).first():
                raise RuntimeError(f"NULL values: {name}.{column}; explicit data correction required")
        for constraint, columns in rules.get("unique", []):
            query = sa.select(sa.literal(1)).select_from(table).group_by(*(table.c[c] for c in columns)).having(sa.func.count() > 1).limit(1)
            if bind.execute(query).first():
                raise RuntimeError(f"Duplicate relationship: {constraint}; no automatic deletion")
        for constraint, expression in rules.get("checks", []):
            if bind.execute(sa.select(sa.literal(1)).select_from(table).where(sa.text(f"NOT ({expression})")).limit(1)).first():
                raise RuntimeError(f"Invalid values: {constraint}; explicit data correction required")
    counters = {}
    for scope, table_name in (("cartridge", "batches"), ("repair", "repair_batches")):
        maximum = 0
        # One-time offline deployment initialization, never a runtime numbering algorithm.
        for (number,) in bind.execute(sa.select(metadata.tables[table_name].c.act_number)):
            suffix = number.rsplit("-", 1)[-1]
            if suffix.isascii() and suffix.isdigit():
                maximum = max(maximum, int(suffix))
        if maximum >= 9223372036854775806:
            raise RuntimeError("Document suffix exceeds counter capacity; review legacy numbers")
        counters[scope] = maximum
    return metadata, counters


def upgrade():
    if context.is_offline_mode():
        raise RuntimeError("Integrity migration requires online data preflight; review on a restored copy")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Writers must be stopped for deployment. Lock also closes the preflight/DDL race.
        names = ", ".join(sorted(baseline_schema().tables))
        bind.execute(sa.text(f"LOCK TABLE {names} IN SHARE ROW EXCLUSIVE MODE"))
    metadata, counters = preflight(bind)
    for name, rules in SPEC.items():
        with op.batch_alter_table(name) as batch:
            for column in rules.get("not_null", []):
                batch.alter_column(column, existing_type=metadata.tables[name].c[column].type, nullable=False)
            for constraint, columns in rules.get("unique", []):
                batch.create_unique_constraint(constraint, columns)
            for constraint, expression in rules.get("checks", []):
                batch.create_check_constraint(constraint, expression)
            for index, columns in rules.get("indexes", []):
                batch.create_index(index, columns, unique=False)
    table = op.create_table("document_counters",
                           sa.Column("scope", sa.String(32), primary_key=True),
                           sa.Column("last_value", sa.BigInteger(), nullable=False),
                           sa.CheckConstraint("last_value >= 0", name="ck_document_counters_value"))
    op.bulk_insert(table, [{"scope": scope, "last_value": value} for scope, value in counters.items()])


def downgrade():
    if context.get_x_argument(as_dictionary=True).get("allow_destructive") != "true":
        raise RuntimeError("Downgrade removes integrity guarantees and numbering history; requires -x allow_destructive=true")
    metadata = baseline_schema()
    op.drop_table("document_counters")
    for name, rules in reversed(list(SPEC.items())):
        with op.batch_alter_table(name) as batch:
            for index, _ in reversed(rules.get("indexes", [])):
                batch.drop_index(index)
            for constraint, _ in reversed(rules.get("checks", [])):
                batch.drop_constraint(constraint, type_="check")
            for constraint, _ in reversed(rules.get("unique", [])):
                batch.drop_constraint(constraint, type_="unique")
            for column in reversed(rules.get("not_null", [])):
                batch.alter_column(column, existing_type=metadata.tables[name].c[column].type, nullable=True)
