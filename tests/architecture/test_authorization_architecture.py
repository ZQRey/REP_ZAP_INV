import ast
from pathlib import Path
from SHARED.database import Base
from SHARED.policies.core import SCOPED, GLOBAL
from scripts.audit_authorization import check

ROOT = Path(__file__).resolve().parents[2]


def test_every_entity_has_exactly_one_scope():
    assert not SCOPED & GLOBAL
    assert {mapper.class_ for mapper in Base.registry.mappers} == SCOPED | GLOBAL


def test_every_source_route_has_reviewed_policy():
    check()


def test_single_bearer_implementation_and_no_request_session_bypass():
    bearers = []
    for module in ("SHARED", "CARTRIDGE", "REPAIR", "LOCATION"):
        for path in (ROOT / module).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "HTTPBearer":
                    bearers.append(path.relative_to(ROOT).as_posix())
                if module != "SHARED" and "app" in path.parts and isinstance(node, ast.ImportFrom):
                    assert not any(a.name in {"SessionLocal", "session_scope", "engine"} for a in node.names) or path.name == "database.py", path
    assert bearers == ["SHARED/authentication.py"]
