"""Identity, schema and lifecycle contracts for the canonical SQLAlchemy layer."""
import ast
import enum
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest
from sqlalchemy import event, inspect, text
from sqlalchemy.orm import configure_mappers

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = json.loads((Path(__file__).with_name("schema_before.json")).read_text(encoding="utf-8"))
FACTORIES = {"declarative_base", "registry", "automap_base", "generate_base", "create_engine",
             "create_async_engine", "sessionmaker", "async_sessionmaker", "scoped_session"}


def forbidden_initializers(source, path):
    tree = ast.parse(source)
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                aliases[alias.asname or alias.name] = (node.module or "") + "." + alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".")[0]] = alias.name if alias.asname else alias.name.split(".")[0]
    def resolve(node):
        if isinstance(node, ast.Name): return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute): return resolve(node.value) + "." + node.attr
        return ""
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and resolve(node.func).split(".")[-1] in FACTORIES:
            if path != "SHARED/database.py": findings.append((node.lineno, resolve(node.func)))
        if isinstance(node, ast.ClassDef):
            if any(resolve(base).split(".")[-1] in {"DeclarativeBase", "DeclarativeBaseNoMeta"} for base in node.bases):
                findings.append((node.lineno, "second declarative base"))
            if path != "SHARED/models.py" and any(isinstance(s, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__tablename__" for t in s.targets) for s in node.body):
                findings.append((node.lineno, "mapped class outside canonical module"))
    return findings


@pytest.mark.parametrize("source", [
    "from sqlalchemy.orm import declarative_base as make\nOther = make()",
    "import sqlalchemy.orm as orm\nclass Other(orm.DeclarativeBase): pass",
    "from sqlalchemy.orm import registry as Registry\nr = Registry()\nOther = r.generate_base()",
    "import sqlalchemy as sa\nengine = sa.create_engine('sqlite://')",
    "from sqlalchemy.orm import sessionmaker as Factory\nf = Factory()",
    "class Rogue(Base):\n    __tablename__ = 'rogue'",
])
def test_guard_detects_second_architecture(source):
    assert forbidden_initializers(source, "NEW_MODULE/database.py")


def test_only_canonical_initialization_and_model_definitions():
    findings = []
    for path in ROOT.rglob("*.py"):
        if any(p in path.parts for p in (".git", "__pycache__")): continue
        relative = path.relative_to(ROOT).as_posix()
        findings.extend((relative, *f) for f in forbidden_initializers(path.read_text(encoding="utf-8"), relative))
    assert findings == []
    tree = ast.parse((ROOT / "SHARED/database.py").read_text(encoding="utf-8"))
    calls = [n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    for factory in ("declarative_base", "create_engine", "sessionmaker"):
        assert calls.count(factory) == 1


def test_consumers_import_canonical_models_and_dependency():
    for directory in ("SHARED", "CARTRIDGE", "REPAIR", "LOCATION", "BD"):
        for path in (ROOT / directory).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    assert node.module not in {"app.database", "app.models", "CARTRIDGE.app.database", "CARTRIDGE.app.models"}, path


def test_compatibility_paths_export_identical_objects():
    import SHARED
    from SHARED import database, models
    configure_mappers()
    for name in ("CARTRIDGE.app.database",):
        module = importlib.import_module(name)
        for symbol in ("Base", "engine", "SessionLocal", "get_db", "init_db", "session_scope"):
            assert getattr(module, symbol) is getattr(database, symbol)
    for name in ("CARTRIDGE.app.models",):
        module = importlib.import_module(name)
        for symbol in [*CONTRACT["legacy"], "CartridgeStatus"]:
            assert getattr(module, symbol) is getattr(models, symbol)
    assert SHARED.Base is database.Base
    assert len(database.Base.registry.mappers) == len(CONTRACT["shared"]) + 2  # Notification + DocumentCounter
    assert set(database.Base.metadata.tables) == {m["table"] for m in CONTRACT["shared"].values()} | {"document_counters", "notifications"}
    for mapper in database.Base.registry.mappers:
        assert mapper.class_.__module__ == "SHARED.models"
        for relation in mapper.relationships:
            assert relation.mapper.registry is database.Base.registry


def default_value(value):
    if value is None: return None
    if hasattr(value, "arg"): value = value.arg
    if isinstance(value, enum.Enum): return value.__class__.__name__ + "." + value.name
    if callable(value): return getattr(value, "__qualname__", str(value))
    return str(value)


def describe(cls):
    table = cls.__table__
    columns = {}
    for c in table.columns:
        columns[c.name] = {
            "type": str(c.type), "nullable": c.nullable, "primary_key": c.primary_key,
            "autoincrement": c.autoincrement, "default": default_value(c.default), "onupdate": default_value(c.onupdate),
            "server_default": default_value(c.server_default), "unique": c.unique, "index": c.index,
            "foreign_keys": sorted([{"target": f.target_fullname, "ondelete": f.ondelete, "onupdate": f.onupdate} for f in c.foreign_keys], key=lambda x: x["target"]),
            "enum": {"name": c.type.name, "labels": c.type.enums, "native_enum": c.type.native_enum, "create_constraint": c.type.create_constraint, "validate_strings": c.type.validate_strings} if hasattr(c.type, "enums") else None,
        }
    relationships = {r.key: {"target": r.mapper.class_.__name__, "back_populates": r.back_populates, "uselist": r.uselist,
        "cascade": sorted(r.cascade), "lazy": r.lazy, "passive_deletes": r.passive_deletes, "viewonly": r.viewonly,
        "join": str(r.primaryjoin), "order_by": [str(o) for o in r.order_by] if r.order_by else [],
        "foreign_keys": sorted(str(c) for c in r._user_defined_foreign_keys)} for r in inspect(cls).relationships}
    return {"table": table.name, "columns": columns, "relationships": relationships,
        "indexes": sorted([{"name": i.name, "columns": [c.name for c in i.columns], "unique": i.unique} for i in table.indexes], key=lambda x: x["name"] or ""),
        "constraints": sorted([{"type": type(c).__name__, "name": c.name, "columns": [v.name for v in c.columns]} for c in table.constraints], key=lambda x: (x["type"], str(x["columns"]))) }


def test_original_fields_and_relationships_preserved_by_integrity_migration():
    from SHARED import models
    spec = json.loads((ROOT / "alembic/integrity_spec.json").read_text(encoding="utf-8"))
    for name, before in CONTRACT["shared"].items():
        expected = json.loads(json.dumps(before))
        if name == "AppUser":
            expected["columns"]["role"]["default"] = "user"
        if name == "NetworkSwitch":
            # 0005 widens persisted encrypted credential fields; the frozen
            # pre-migration snapshot intentionally remains unchanged.
            expected["columns"]["password"]["type"] = "VARCHAR(1000)"
            expected["columns"]["snmp_community"]["type"] = "VARCHAR(1000)"
        for col in spec.get(before["table"], {}).get("not_null", []):
            expected["columns"][col]["nullable"] = False
        actual = describe(getattr(models, name))
        assert actual["columns"] == expected["columns"], name
        assert actual["relationships"] == expected["relationships"], name
        assert all(c in actual["constraints"] for c in expected["constraints"]), name
        assert all(i in actual["indexes"] for i in expected["indexes"]), name


@pytest.mark.parametrize("dialect_name", ["sqlite", "postgresql"])
def test_frozen_baseline_ddl_matches_pre_migration_schema(dialect_name):
    from sqlalchemy.dialects import sqlite, postgresql
    from sqlalchemy.schema import CreateTable, CreateIndex
    from SHARED.migration_support import baseline_schema
    metadata = baseline_schema()
    dialect = {"sqlite": sqlite, "postgresql": postgresql}[dialect_name].dialect()
    before = json.loads(Path(__file__).with_name("ddl_before.json").read_text(encoding="utf-8"))[dialect_name]
    actual = {t.name: {"table": str(CreateTable(t).compile(dialect=dialect)), "indexes": sorted(str(CreateIndex(i).compile(dialect=dialect)) for i in t.indexes)} for t in metadata.sorted_tables}
    # Autogenerate may order equivalent FK clauses differently.
    for name in actual:
        for value in (actual[name], before[name]):
            value["table"] = sorted(line.strip().rstrip(",") for line in value["table"].splitlines() if line.strip())
    assert actual == before


@pytest.mark.parametrize("modules", [
    ["SHARED.models", "SHARED.database", "app.models", "app.database", "main_server"],
    ["app.database", "CARTRIDGE.app.models", "SHARED.auth_service", "main_server"],
    ["SHARED", "SHARED.config", "LOCATION.app.main", "REPAIR.app.main", "CARTRIDGE.app.main"],
])
def test_fresh_import_orders_have_no_cycles(modules):
    code = "import importlib; " + "; ".join(f"importlib.import_module({name!r})" for name in modules)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT), str(ROOT / "CARTRIDGE")])
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("path", ["/api/settings", "/cartridges/api/settings", "/api/v1/auth/me"])
def test_auth_guard_and_endpoint_share_one_session(client, account, monkeypatch, path):
    from SHARED import database
    token = client.post("/api/auth/login", json=account).json()["access_token"]
    factory = Mock(wraps=database.SessionLocal)
    monkeypatch.setattr(database, "SessionLocal", factory)
    result = client.get(path, headers={"Authorization": "Bearer " + token})
    assert result.status_code == 200, result.text
    assert factory.call_count == 1


def test_shared_identity_map_and_relationship_alias(client):
    from SHARED.database import SessionLocal
    from SHARED.models import Branch, Batch
    old = importlib.import_module("CARTRIDGE.app.models")
    with SessionLocal() as db:
        branch = db.query(Branch).first()
        assert db.get(old.Branch, branch.id) is branch
        batch = old.Batch(act_number="ARCH-1", vendor_name="Test", branch=branch)
        db.add(batch)
        db.flush()
        assert branch.batches is branch.cartridge_batches
        assert batch in branch.cartridge_batches
        assert inspect(Batch).relationships.branch.back_populates == "cartridge_batches"


def test_session_lifecycle_rolls_back_and_closes(monkeypatch):
    from SHARED import database
    session = Mock()
    monkeypatch.setattr(database, "SessionLocal", lambda: session)
    with pytest.raises(ValueError):
        with database.session_scope() as db:
            assert db is session
            raise ValueError("operation failed")
    session.rollback.assert_called_once()
    session.close.assert_called_once()
    session.commit.assert_not_called()


def test_no_implicit_commit_and_no_data_loss(client):
    from SHARED.database import session_scope
    from SHARED.models import Branch
    with session_scope() as db:
        db.add(Branch(name="uncommitted-branch"))
        db.flush()
    with session_scope() as db:
        assert db.query(Branch).filter_by(name="uncommitted-branch").count() == 0
        assert db.query(Branch).count() == 1


def test_branch_delete_does_not_cascade_into_other_modules(client, account):
    from SHARED.database import SessionLocal
    from SHARED.models import Branch, Floor, Zone, Asset
    with SessionLocal() as db:
        branch = db.query(Branch).first()
        floor = Floor(branch=branch, name="Preserved floor")
        zone = Zone(floor=floor, name="Preserved room")
        asset = Asset(branch=branch, floor=floor, zone=zone, name="Preserved asset", inventory_number="ARCH-ASSET")
        db.add_all([floor, zone, asset])
        db.commit()
        ids = branch.id, floor.id, zone.id, asset.id
    token = client.post("/api/auth/login", json=account).json()["access_token"]
    result = client.delete(f"/api/branches/{ids[0]}", headers={"Authorization": "Bearer " + token})
    assert result.status_code == 409
    with SessionLocal() as db:
        for cls, key in zip((Branch, Floor, Zone, Asset), ids):
            assert db.get(cls, key) is not None
        assert db.get(Asset, ids[3]).branch_id == ids[0]


def test_reset_uses_canonical_target_and_rejects_non_test_environment(monkeypatch):
    from CARTRIDGE import reset_data
    from SHARED.database import engine
    assert reset_data.require_test_database() == engine.url.database
    monkeypatch.setattr(reset_data, "ENVIRONMENT", "production")
    with pytest.raises(RuntimeError, match="APP_ENV=test"):
        reset_data.reset_full_database()
    with pytest.raises(RuntimeError, match="APP_ENV=test"):
        reset_data.reset_test_cartridges()


def test_unified_startup_does_not_issue_schema_changes(client):
    from SHARED.database import engine, init_db
    statements = []
    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip().split()[0].upper())
    event.listen(engine, "before_cursor_execute", record)
    try: init_db()
    finally: event.remove(engine, "before_cursor_execute", record)
    assert not {"CREATE", "ALTER", "DROP", "DELETE", "TRUNCATE"}.intersection(statements)


def test_retired_schema_mutator_cannot_change_database():
    from SHARED.migrations.add_branch_network_subnets import main
    with pytest.raises(SystemExit, match="Alembic"):
        main()
