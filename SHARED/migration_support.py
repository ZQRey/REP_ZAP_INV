"""Auditing for the frozen baseline. No automatic schema changes."""
import importlib.util
from pathlib import Path
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
import sqlalchemy as sa

LEGACY_COLUMNS = {
    "network_switches": {"management_type", "mgmt_port", "username", "password", "snmp_community", "model", "total_ports", "extra_params", "last_poll_status", "last_poll_message", "last_polled_at"},
    "switch_ports": {"cabinet", "socket_label", "zone_id", "last_mac", "last_ip", "last_seen_at", "connected_asset_id"},
    "cartridges": {"branch_id", "condition"}, "batches": {"branch_id"},
    "app_users": {"wa_instance_name"}, "branches": {"it_office", "wa_message_template", "network_subnets"},
}
LEGACY_DEFAULTS = {
    ("network_switches", "management_type"): "snmp",
    ("network_switches", "mgmt_port"): "161",
    ("network_switches", "snmp_community"): "",  # obsolete default is recognized separately, never restored
    ("network_switches", "total_ports"): "24",
    ("network_switches", "last_poll_status"): "never",
    ("cartridges", "condition"): "working",
}
REMOVED_SNMP_DEFAULT = "public"  # audit comparison only; never assigned to a device or column


def baseline_schema():
    path = Path(__file__).resolve().parents[1] / "alembic/frozen_baseline.py"
    spec = importlib.util.spec_from_file_location("_frozen_database_baseline", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.schema()


def _known(diff):
    kind = diff[0]
    if kind == "add_column":
        return diff[3].name in LEGACY_COLUMNS.get(diff[2], set())
    if kind in {"add_fk", "add_index"}:
        return True  # only canonical objects are compared; all are validated before adding
    if kind == "modify_type":
        return diff[2:4] == ("branches", "it_office") and getattr(diff[5], "length", None) == 100 and getattr(diff[6], "length", None) == 255
    if kind == "modify_default" and diff[6] is None:
        key = (diff[2], diff[3])
        if key not in LEGACY_DEFAULTS: return False
        raw = str(getattr(diff[5], "arg", diff[5])).split("::")[0].strip("()'")
        return raw == LEGACY_DEFAULTS[key] or (key == ("network_switches", "snmp_community") and raw == REMOVED_SNMP_DEFAULT)
    return False


def baseline_differences(connection):
    metadata = baseline_schema()
    inspector = sa.inspect(connection)
    def include(obj, name, type_, reflected, compare_to):
        return type_ != "table" or name in metadata.tables
    context = MigrationContext.configure(connection, opts={"compare_type": True, "compare_server_default": True, "include_object": include})
    raw = compare_metadata(context, metadata)
    flattened = [item for d in raw for item in (d if isinstance(d, list) else [d])]
    differences = []
    for d in flattened:
        if d[0] in {"add_column", "remove_column", "modify_type", "modify_nullable", "modify_default"}:
            location = d[2] + "." + (d[3].name if hasattr(d[3], "name") else str(d[3]))
        else:
            obj = d[-1]
            location = str(getattr(getattr(obj, "table", None), "name", getattr(obj, "name", "schema")))
        differences.append({"kind": d[0], "location": location, "known_legacy": _known(d)})
    # Autogenerate does not reliably detect primary-key and PostgreSQL enum changes.
    existing = set(inspector.get_table_names())
    for table in metadata.sorted_tables:
        if table.name not in existing: continue
        if inspector.get_pk_constraint(table.name)["constrained_columns"] != [c.name for c in table.primary_key]:
            differences.append({"kind": "primary_key", "location": table.name, "known_legacy": False})
        for check in inspector.get_check_constraints(table.name):
            differences.append({"kind": "unexpected_check", "location": table.name + "." + str(check["name"]), "known_legacy": False})
    if connection.dialect.name == "postgresql":
        enums = {e["name"]: e["labels"] for e in inspector.get_enums()}
        for table in metadata.sorted_tables:
            if table.name not in existing: continue
            for col in table.c:
                if isinstance(col.type, sa.Enum) and enums.get(col.type.name) != col.type.enums:
                    differences.append({"kind": "enum_labels", "location": col.type.name, "known_legacy": False})
    return differences


def require_adoptable(differences, allow_legacy=False):
    forbidden = [d for d in differences if not (allow_legacy and d["known_legacy"])]
    if forbidden:
        description = "; ".join(d["kind"] + ":" + d["location"] for d in forbidden)
        raise RuntimeError("Baseline schema mismatch; no automatic repair: " + description)


def validate_foreign_keys(connection, metadata):
    """Fail before DDL on orphans; never print row data or delete invalid records."""
    existing = sa.inspect(connection)
    for table in metadata.sorted_tables:
        columns = {c["name"] for c in existing.get_columns(table.name)}
        for fk in table.foreign_key_constraints:
            local, remote = list(fk.columns)[0], list(fk.elements)[0].column
            if local.name not in columns: continue  # new nullable column has no rows yet
            q = (sa.select(sa.literal(1)).select_from(table.outerjoin(remote.table, local == remote))
                 .where(local.is_not(None), remote.is_(None)).limit(1))
            if connection.execute(q).first():
                raise RuntimeError(f"Orphan rows: {table.name}.{local.name}; resolve explicitly before migration")


def main():
    import json
    from SHARED.database import engine
    with engine.connect() as connection:
        result = baseline_differences(connection)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result else 0


if __name__ == "__main__":
    raise SystemExit(main())
