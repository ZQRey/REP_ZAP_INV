import inspect
import json
from pathlib import Path
from fastapi import Depends, HTTPException, Request
from SHARED.database import get_db
from SHARED.authentication import require_authenticated_user, security
from SHARED import models as m
from .core import require_branch_access, require_object_access, require_user_management, branch_of, require_consistent_references, require_network_target
from .session import bind_scope

ROOT = Path(__file__).resolve().parents[2]
POLICIES = json.loads(Path(__file__).with_name("endpoints.json").read_text(encoding="utf-8"))
REFERENCES = {"asset_id": m.Asset, "asset_ids": m.Asset, "to_asset": m.Asset,
              "connected_asset_id": m.Asset, "cartridge_id": m.Cartridge, "cartridge_ids": m.Cartridge,
              "floor_id": m.Floor, "zone_id": m.Zone, "switch_id": m.NetworkSwitch, "from_switch": m.NetworkSwitch,
              "user_id": m.AppUser, "repair_item_id": m.RepairBatchItem, "item_ids": m.RepairBatchItem}


def endpoint_key(endpoint, method):
    path = Path(inspect.getfile(endpoint)).resolve().relative_to(ROOT).as_posix()
    if path.startswith("app/"): path = "CARTRIDGE/" + path
    return f"{path}:{endpoint.__name__}:{method}"




async def authorize_request(request: Request, credentials=Depends(security), db=Depends(get_db)):
    endpoint = request.scope.get("endpoint")
    key = endpoint_key(endpoint, request.method)
    policy = POLICIES.get(key)
    if policy is None:
        raise HTTPException(403, "Endpoint has no authorization policy")
    if policy["public"]: return
    user = require_authenticated_user(request, credentials, db)
    principal = request.state.principal
    if principal.role not in policy["roles"]:
        raise HTTPException(403, "Endpoint permission denied")
    if policy["branch_scope"] and principal.role != "superadmin" and principal.branch_id is None:
        raise HTTPException(403, "Branch membership required")
    branch = None if principal.role == "superadmin" else principal.branch_id
    bind_scope(db, principal, policy, branch)
    body = {}
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    is_json = not content_type or content_type == "application/json" or (content_type.startswith("application/") and content_type.endswith("+json"))
    if is_json and await request.body():
        try: body = await request.json()
        except (ValueError, UnicodeDecodeError): raise HTTPException(422, "Invalid JSON body") from None
    containers = [dict(request.path_params), dict(request.query_params)]
    if isinstance(body, dict):
        containers.append(body)
        if isinstance(body.get("switch_config"), dict): containers.append(body["switch_config"])
        if body.get("switch_config") is not None and principal.role not in {"superadmin", "admin", "technician"}:
            raise HTTPException(403, "Network configuration permission required")
    # Branch selection is validated before resolving any referenced ID or calling an adapter.
    for values in containers:
        if "branch_id" in values and values["branch_id"] is not None:
            try: selected = int(values["branch_id"])
            except (ValueError, TypeError): raise HTTPException(422, "Invalid branch_id") from None
            if selected <= 0:
                if principal.role != "superadmin": raise HTTPException(403, "Global branch scope denied")
                continue
            require_branch_access(principal, selected)
            require_object_access(db, principal, m.Branch, selected)
            if policy["branch_scope"]:
                if not (policy["domain"] == "users" and policy["action"] == "write" and values is body):
                    db.info["scope_branch"] = selected
                db.info["create_branch"] = selected
    seen_branches = set()
    for values in containers:
        for field, value in values.items():
            model = REFERENCES.get(field)
            if field == "batch_id": model = m.Batch if policy["domain"] == "cartridges" else m.RepairBatch
            if model is None or value is None: continue
            ids = value if isinstance(value, list) else [value]
            if isinstance(value, list) and len({str(v) for v in ids}) != len(ids):
                raise HTTPException(422, "Duplicate IDs in bulk request")
            for object_id in ids:
                try: object_id = int(object_id)
                except (TypeError, ValueError): raise HTTPException(422, "Invalid object ID") from None
                if object_id <= 0 and field not in request.path_params:
                    continue  # clear optional relationship; before_flush still validates its owner
                obj = require_object_access(db, principal, model, object_id)
                if policy["action"] == "write":
                    require_consistent_references(db, obj)
                if policy["domain"] == "users" and policy["action"] == "write":
                    require_user_management(principal, obj)
                if policy["domain"] == "whatsapp" and principal.role != "superadmin" and obj.id != principal.id:
                    raise HTTPException(403, "WhatsApp account ownership required")
                branch_value = branch_of(db, obj)
                if branch_value is not None: seen_branches.add(branch_value)
                if policy["network"]:
                    sw = obj if model is m.NetworkSwitch else getattr(obj, "switch_device", None)
                    if sw is not None: require_network_target(db, principal, sw.ip_address)
        if (policy["network"] or isinstance(body, dict) and values is body.get("switch_config")) and values.get("ip_address"):
            require_network_target(db, principal, values["ip_address"])
    if policy["action"] == "write" and len(seen_branches) > 1:
        raise HTTPException(403, "An operation cannot link objects from different branches")
    if len(seen_branches) == 1 and "create_branch" not in db.info:
        db.info["create_branch"] = next(iter(seen_branches))
    if policy["domain"] == "users" and policy["action"] == "write" and isinstance(body, dict):
        require_user_management(principal, role=body.get("role"), branch_id=body.get("branch_id"))
    if policy["domain"] == "branches" and principal.role != "superadmin" and isinstance(body, dict) and "network_subnets" in body:
        own_branch = require_object_access(db, principal, m.Branch, principal.branch_id)
        if body["network_subnets"] != own_branch.network_subnets:
            raise HTTPException(403, "Only superadmin can change the branch network allowlist")
    if policy["domain"] == "whatsapp" and principal.role != "superadmin":
        instance = request.query_params.get("instance_name")
        own = user.wa_instance_name or f"operator_{user.id}"
        if instance and instance != own:
            raise HTTPException(403, "WhatsApp instance ownership required")
    return user
