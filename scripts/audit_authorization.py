"""Check the explicit policy registry against every source route, including aliases."""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def declarations():
    files = [ROOT / "main_server.py"]
    for module in ("CARTRIDGE", "REPAIR", "LOCATION"):
        files.extend((ROOT / module / "app").rglob("*.py"))
    rows = []
    for path in sorted(files):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        prefixes = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and getattr(node.value.func, "id", None) == "APIRouter":
                prefixes[node.targets[0].id] = next((ast.literal_eval(k.value) for k in node.value.keywords if k.arg == "prefix"), "")
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                    continue
                method = decorator.func.attr.upper()
                if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
                    continue
                url = prefixes.get(getattr(decorator.func.value, "id", ""), "") + ast.literal_eval(decorator.args[0])
                file = path.relative_to(ROOT).as_posix()
                rows.append({"key": f"{file}:{node.name}:{method}", "path": url, "method": method, "file": file, "line": node.lineno})
    return rows


def check():
    policies = json.loads((ROOT / "SHARED/policies/endpoints.json").read_text(encoding="utf-8"))
    rows = declarations()
    assert {r["key"] for r in rows} == set(policies), "Endpoint added/removed without explicit policy review"
    for key, policy in policies.items():
        assert sorted(policy["paths"]) == sorted(r["path"] for r in rows if r["key"] == key), key
    return rows, policies


if __name__ == "__main__":
    rows, policies = check()
    print(f"Reviewed registry: {len(rows)} declarations, {len(policies)} handler/method policies")
