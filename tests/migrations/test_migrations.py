"""Run against isolated SQLite locally and disposable PostgreSQL 15 in CI."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import ast
import json
from pathlib import Path
import pytest
import sqlalchemy as sa
from alembic import command
from alembic.migration import MigrationContext
from SHARED.database import Base, engine, init_db, SessionLocal
from SHARED.schema_management import alembic_config
from SHARED.migration_support import baseline_schema, baseline_differences

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def empty_database():
    Base.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.execute(sa.text("DROP TABLE IF EXISTS alembic_version"))
    return engine


def config(**flags):
    cfg = alembic_config()
    cfg.cmd_opts = SimpleNamespace(x=[f"{k}={str(v).lower()}" for k, v in flags.items()])
    return cfg


def current():
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def test_empty_startup_is_read_only_and_requires_migration(empty_database):
    statements = []
    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip().split()[0].upper())
    sa.event.listen(engine, "before_cursor_execute", record)
    try:
        with pytest.raises(RuntimeError, match="Alembic head"):
            init_db()
    finally:
        sa.event.remove(engine, "before_cursor_execute", record)
    assert not {"ALTER", "CREATE", "DROP", "INSERT", "UPDATE", "DELETE"}.intersection(statements)
    assert sa.inspect(engine).get_table_names() == []


def test_fresh_upgrade_model_parity_and_startup(empty_database):
    command.upgrade(config(), "head")
    assert current() == "0007_port_learned_macs"
    command.check(config())  # zero missing columns/FKs/indexes/types/defaults at head
    inspector = sa.inspect(engine)
    spec = json.loads((ROOT / "alembic/integrity_spec.json").read_text(encoding="utf-8"))
    for name, rules in spec.items():
        checks = {c["name"] for c in inspector.get_check_constraints(name)}
        uniques = {c["name"]: c["column_names"] for c in inspector.get_unique_constraints(name)}
        columns = {c["name"]: c for c in inspector.get_columns(name)}
        assert all(constraint in checks for constraint, _ in rules.get("checks", []))
        assert all(uniques[constraint] == cols for constraint, cols in rules.get("unique", []))
        assert all(not columns[col]["nullable"] for col in rules.get("not_null", []))
    init_db()
    command.upgrade(config(), "head")  # idempotent versioned execution
    with SessionLocal() as db:
        from SHARED.models import Branch, DocumentCounter
        assert db.query(Branch).count() == 1
        assert db.query(DocumentCounter).count() == 2


def test_existing_exact_schema_requires_explicit_adoption_and_preserves_rows(empty_database):
    baseline = baseline_schema()
    baseline.create_all(engine)  # emulate restored pre-Alembic database, only in tests
    with engine.begin() as connection:
        connection.execute(baseline.tables["branches"].insert().values(id=42, name="Existing branch", notes="preserve"))
        connection.execute(baseline.tables["batches"].insert().values(id=9, act_number="OLD-2025-0099", vendor_name="Vendor", status="open"))
        assert baseline_differences(connection) == []
    with pytest.raises(RuntimeError, match="Existing schema"):
        command.upgrade(config(), "head")
    command.upgrade(config(adopt_existing=True), "head")
    with SessionLocal() as db:
        from SHARED.models import Branch, DocumentCounter
        assert db.get(Branch, 42).notes == "preserve"
        assert db.get(DocumentCounter, "cartridge").last_value == 99
    init_db()


def test_known_legacy_drift_is_explicit_and_additive(empty_database):
    baseline = baseline_schema()
    baseline.tables["branches"].c.it_office.type = sa.String(100)
    baseline.tables["branches"]._columns.remove(baseline.tables["branches"].c.network_subnets)
    table = baseline.tables["batches"]
    for fk in list(table.foreign_key_constraints):
        table.constraints.remove(fk)
        for element in fk.elements:
            element.parent.foreign_keys.remove(element)
    baseline.create_all(engine)
    with engine.begin() as connection:
        connection.execute(baseline.tables["branches"].insert().values(id=42, name="Legacy", it_office="Room"))
    with pytest.raises(RuntimeError, match="Baseline schema mismatch"):
        command.upgrade(config(adopt_existing=True), "head")
    command.upgrade(config(adopt_existing=True, accept_legacy_drift=True), "head")
    with engine.connect() as connection:
        assert tuple(connection.execute(sa.text("SELECT name, it_office, network_subnets FROM branches WHERE id=42")).one()) == ("Legacy", "Room", None)
    assert sa.inspect(engine).get_foreign_keys("batches")
    command.check(config())


def test_unknown_drift_is_rejected_without_dropping_data(empty_database):
    baseline = baseline_schema()
    baseline.tables["branches"].c.name.type = sa.String(17)
    baseline.create_all(engine)
    with pytest.raises(RuntimeError, match="Baseline schema mismatch"):
        command.upgrade(config(adopt_existing=True, accept_legacy_drift=True), "head")
    assert sa.inspect(engine).get_columns("branches")[1]["type"].length == 17
    assert current() is None


def test_orphans_block_foreign_key_repair_without_deleting_rows(empty_database):
    baseline = baseline_schema()
    table = baseline.tables["batches"]
    for fk in list(table.foreign_key_constraints):
        table.constraints.remove(fk)
        for element in fk.elements:
            element.parent.foreign_keys.remove(element)
    baseline.create_all(engine)
    with engine.begin() as connection:
        connection.execute(table.insert().values(id=1, act_number="OLD-1", vendor_name="V", branch_id=99999, status="open"))
    with pytest.raises(RuntimeError, match="Orphan rows"):
        command.upgrade(config(adopt_existing=True, accept_legacy_drift=True), "head")
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT branch_id FROM batches WHERE id=1")).scalar_one() == 99999


@pytest.mark.parametrize("bad", ["duplicate", "negative", "null"])
def test_invalid_existing_data_blocks_integrity_without_cleanup(empty_database, bad):
    command.upgrade(config(), "0002_legacy_alignment")
    baseline = baseline_schema()
    with engine.begin() as connection:
        if bad == "duplicate":
            connection.execute(baseline.tables["batches"].insert().values(id=1, act_number="EXISTING-1", vendor_name="V", status="open"))
            connection.execute(baseline.tables["cartridges"].insert().values(id=1, marker_label="C1", model="M", cabinet="R", status="IN_USE"))
            connection.execute(baseline.tables["batch_items"].insert(), [{"id":1,"batch_id":1,"cartridge_id":1},{"id":2,"batch_id":1,"cartridge_id":1}])
        else:
            connection.execute(baseline.tables["branches"].insert().values(id=1, name="B"))
            connection.execute(baseline.tables["floors"].insert().values(id=1, branch_id=1, name="F", scale_pixels_per_meter=None if bad == "null" else -1))
    with pytest.raises(RuntimeError, match="Duplicate|Invalid|NULL"):
        command.upgrade(config(), "head")
    assert current() == "0002_legacy_alignment"
    assert "document_counters" not in sa.inspect(engine).get_table_names()
    if bad == "duplicate":
        with engine.connect() as connection:
            assert connection.execute(sa.text("SELECT count(*) FROM batch_items")).scalar_one() == 2


def test_constraints_are_enforced(client):
    from SHARED.models import Batch, Cartridge, BatchItem, Branch, Floor
    with SessionLocal() as db:
        batch = Batch(act_number="A-1", vendor_name="V")
        cartridge = Cartridge(marker_label="C-1", model="M", cabinet="R")
        db.add_all([batch, cartridge]); db.flush()
        ids = batch.id, cartridge.id
        db.add(BatchItem(batch_id=ids[0], cartridge_id=ids[1])); db.commit()
    with SessionLocal() as db:
        db.add(BatchItem(batch_id=ids[0], cartridge_id=ids[1]))
        with pytest.raises(sa.exc.IntegrityError): db.commit()
    with SessionLocal() as db:
        db.add(BatchItem(batch_id=999999, cartridge_id=ids[1]))
        with pytest.raises(sa.exc.IntegrityError): db.commit()
    with SessionLocal() as db:
        branch = db.query(Branch).first()
        db.add(Floor(branch_id=branch.id, name="Invalid", scale_pixels_per_meter=0))
        with pytest.raises(sa.exc.IntegrityError): db.commit()


def test_parallel_numbering_and_deleted_documents_do_not_reuse_numbers(client):
    from SHARED.document_numbers import next_document_number
    from SHARED.models import Batch
    def create(index):
        with SessionLocal() as db:
            number = next_document_number(db, "cartridge", "ACT-", "20260928", 3)
            db.add(Batch(act_number=number, vendor_name="Concurrent"))
            db.commit()
            return number
    with ThreadPoolExecutor(max_workers=6) as executor:
        numbers = list(executor.map(create, range(24)))
    assert len(set(numbers)) == 24
    with SessionLocal() as db:
        db.query(Batch).delete(); db.commit()
    assert create(25).endswith("-025")


def test_counter_rollback_is_transactional(client):
    from SHARED.document_numbers import next_document_number
    with SessionLocal() as db:
        first = next_document_number(db, "repair", "REPAIR-", "2026", 4)
        db.rollback()
    with SessionLocal() as db:
        assert next_document_number(db, "repair", "REPAIR-", "2026", 4) == first
        db.commit()


def test_both_document_apis_use_persisted_atomic_counters(client, account):
    from SHARED.models import Cartridge, CartridgeStatus, Asset, AssetStatus, Branch, DocumentCounter
    with SessionLocal() as db:
        branch = db.query(Branch).first()
        cartridge = Cartridge(marker_label="API-CART", model="M", cabinet="R", branch_id=branch.id, status=CartridgeStatus.PENDING_VENDOR)
        asset = Asset(inventory_number="API-ASSET", name="A", branch_id=branch.id, status=AssetStatus.PENDING_SC)
        db.add_all([cartridge, asset]); db.commit()
        cartridge_id, asset_id = cartridge.id, asset.id
    token = client.post("/api/auth/login", json=account).json()["access_token"]
    headers = {"Authorization": "Bearer " + token}
    for path, body, scope in [
        ("/api/batches", {"cartridge_ids": [cartridge_id], "vendor_name": "Vendor"}, "cartridge"),
        ("/api/v1/repair/batches", {"asset_ids": [asset_id], "vendor_name": "Vendor"}, "repair"),
    ]:
        result = client.post(path, json=body, headers=headers)
        assert result.status_code in {200, 201}, result.text
        assert int(result.json()["act_number"].rsplit("-", 1)[-1]) == 1
        with SessionLocal() as db:
            assert db.get(DocumentCounter, scope).last_value == 1


def test_downgrade_requires_explicit_destructive_flag_and_reupgrade_preserves_rows(client):
    from SHARED.models import Branch
    with SessionLocal() as db:
        branch_id = db.query(Branch).first().id
    with pytest.raises(RuntimeError, match="cannot be safely narrowed|allow_destructive"):
        command.downgrade(config(), "0002_legacy_alignment")
    command.downgrade(config(allow_destructive=True), "0001_baseline")
    command.upgrade(config(), "head")
    with SessionLocal() as db:
        assert db.get(Branch, branch_id) is not None
    with pytest.raises(RuntimeError, match="DROPS ALL APPLICATION DATA"):
        # only exercise the protected baseline revision after nonbaseline downgrade
        command.downgrade(config(allow_destructive=True), "0001_baseline")
        command.downgrade(config(), "base")


def test_no_schema_mutation_outside_migrations_or_test_fixtures():
    for directory in ("SHARED", "CARTRIDGE/app", "REPAIR/app", "LOCATION/app"):
        for path in (ROOT / directory).rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "ALTER TABLE" not in source, path
            assert "CREATE TABLE" not in source, path
            tree = ast.parse(source)
            assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in {"create_all", "drop_all", "add_column"} for n in ast.walk(tree)), path
    for path in (ROOT / "Dockerfile", ROOT / "CARTRIDGE/Dockerfile"):
        assert "alembic upgrade" not in path.read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert 'command: ["alembic", "upgrade", "head"]' in compose
    assert "service_completed_successfully" in compose
