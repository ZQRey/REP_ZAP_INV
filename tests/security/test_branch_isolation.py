"""Authorization regressions against real HTTP routes and the canonical session."""
import pytest
from SHARED import models as m
from SHARED.database import SessionLocal
from SHARED.tokens import create_access_token


@pytest.fixture
def branches(client):
    with SessionLocal() as db:
        for bid in (1, 2):
            db.merge(m.Branch(id=bid, name=f"Branch {bid}", network_subnets=[f"10.{bid}.0.0/16"]))
        db.flush()
        for bid in (1, 2):
            db.add(m.ADUser(samaccountname=f"user{bid}", display_name="Same display name"))
            for role in ("admin", "technician", "operator", "viewer", "user"):
                db.add(m.AppUser(username=f"{role}{bid}", full_name="Same display name", role=role, branch_id=bid, is_active=True))
            db.add(m.Floor(id=bid, branch_id=bid, floor_number=bid, name=f"Floor {bid}"))
        db.add(m.AppUser(username="root", full_name="Root", role="superadmin", is_active=True))
        db.add(m.AppUser(username="orphan", full_name="Orphan", role="admin", is_active=True))
        db.flush()
        for bid in (1, 2):
            db.add(m.Asset(id=bid, inventory_number=f"INV{bid}", name=f"Asset {bid}", branch_id=bid, floor_id=bid, current_user_id=f"user{bid}"))
            db.add(m.Cartridge(id=bid, marker_label=f"C{bid}", model="HP", cabinet="1", branch_id=bid, current_user_id=f"user{bid}"))
            db.add(m.RepairBatch(id=bid, act_number=f"R{bid}", vendor_name="SC", branch_id=bid))
            db.add(m.Batch(id=bid, act_number=f"B{bid}", vendor_name="SC", branch_id=bid))
        db.flush()
        for bid in (1, 2):
            db.add(m.RepairBatchItem(batch_id=bid, asset_id=bid))
            db.add(m.BatchItem(batch_id=bid, cartridge_id=bid))
            db.add(m.Zone(id=bid, floor_id=bid, name=f"Zone {bid}"))
            db.add(m.NetworkSwitch(id=bid, asset_id=bid, ip_address=f"10.{bid}.0.1"))
        db.flush()
        for bid in (1, 2):
            db.add(m.SwitchPort(id=bid, switch_id=bid, port_number=1, zone_id=bid, connected_asset_id=bid))
        db.commit()
        if db.bind.dialect.name == "postgresql":
            from sqlalchemy import text
            for table in m.Base.metadata.sorted_tables:
                if "id" in table.c:
                    db.execute(text("SELECT setval(pg_get_serial_sequence(:table, 'id'), COALESCE((SELECT MAX(id) FROM " + table.name + "), 0) + 1, false)"), {"table": table.name})
            db.commit()
    return client


def headers(username="admin1"):
    # Malicious elevated token claims must not supersede the current database account.
    return {"Authorization": "Bearer " + create_access_token({"sub": username, "role": "superadmin", "branch_id": 2})}


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/api/v1/repair/equipment/2", None),
    ("PUT", "/api/v1/repair/equipment/2", {"name": "stolen"}),
    ("DELETE", "/api/v1/repair/equipment/2", None),
    ("POST", "/api/v1/repair/equipment", {"inventory_number": "X", "name": "X", "branch_id": 2}),
    ("GET", "/api/v1/repair/batches/2", None),
    ("POST", "/api/v1/repair/batches", {"asset_ids": [1, 2], "vendor_name": "SC"}),
    ("GET", "/api/v1/location/branches/2/floors", None),
    ("PUT", "/api/v1/location/floors/2", {"name": "stolen"}),
    ("DELETE", "/api/v1/location/floors/2", None),
    ("POST", "/api/v1/location/floors", {"branch_id": 2, "name": "X", "floor_number": 5}),
    ("GET", "/api/cartridges/2", None),
    ("GET", "/api/batches/2", None),
    ("POST", "/api/v1/repair/equipment/return-sc", {"item_ids": [1, 2]}),
    ("POST", "/api/cartridges/bulk-issue", {"cartridge_ids": [1, 2]}),
    ("POST", "/api/notifications/whatsapp/ready", {"cartridge_ids": [1, 2]}),
    ("PUT", "/api/v1/location/switches/1/ports/1", {"connected_asset_id": 2}),
    ("POST", "/api/v1/location/assets/1/position", {"floor_id": 2, "coords_x": 0.5, "coords_y": 0.5}),
    ("DELETE", "/api/v1/location/zones/2", None),
    ("POST", "/api/v1/location/switches/2/poll", None),
    ("POST", "/api/v1/location/switches/test-connection", {"ip_address": "10.2.0.1"}),
])
def test_foreign_object_ids_rejected(branches, method, path, body):
    response = branches.request(method, path, json=body, headers=headers())
    assert response.status_code in (403, 404), response.text
    with SessionLocal() as db:
        assert db.get(m.Asset, 2).name == "Asset 2"
        assert db.get(m.Floor, 2).name == "Floor 2"


@pytest.mark.parametrize("username,expected", [("admin1", 404), ("user1", 403), ("orphan", 403), ("root", 200)])
def test_explicit_cross_branch_policy(branches, username, expected):
    response = branches.get("/api/v1/repair/equipment/2", headers=headers(username))
    assert response.status_code == expected, response.text


def test_own_branch_read_and_aggregates(branches):
    from sqlalchemy import func
    from sqlalchemy.orm import aliased, joinedload
    from SHARED.policies.core import Principal
    from SHARED.policies.session import bind_scope
    assert branches.get("/api/v1/repair/equipment/1", headers=headers()).status_code == 200
    with SessionLocal() as db:
        actor = Principal.from_user(db.query(m.AppUser).filter_by(username="admin1").one())
        bind_scope(db, actor, {"action": "read"}, 1)
        assert db.query(func.count(m.Asset.id)).scalar() == 1
        alias = aliased(m.Asset)
        assert [a.id for a in db.query(alias).all()] == [1]
        batch = db.query(m.RepairBatch).options(joinedload(m.RepairBatch.items)).one()
        assert batch.id == 1 and [i.asset.id for i in batch.items] == [1]


def test_ordinary_user_ownership_is_login_not_display_name(branches):
    assert branches.get("/api/v1/repair/equipment/1", headers=headers("user1")).status_code == 403
    with SessionLocal() as db:
        db.add(m.Asset(id=3, inventory_number="INV3", name="Unassigned", branch_id=1))
        db.commit()
    assert branches.get("/api/v1/repair/equipment/3", headers=headers("user1")).status_code == 403


def routes(application, prefix=""):
    from fastapi.routing import APIRoute
    from starlette.routing import Mount
    for route in application.routes:
        if isinstance(route, APIRoute):
            for method in route.methods:
                yield prefix + route.path, method, route
        elif hasattr(route, "effective_route_contexts"):
            for effective in route.effective_route_contexts():
                if isinstance(effective.original_route, APIRoute):
                    for method in effective.methods:
                        yield prefix + effective.path, method, effective
        elif isinstance(route, Mount) and hasattr(route.app, "routes"):
            yield from routes(route.app, prefix + route.path)


def test_every_mounted_endpoint_has_policy_and_rejects_anonymous(client):
    import re
    from main_server import app
    from SHARED.policies.http import POLICIES, endpoint_key, authorize_request
    found = set()
    for path, method, route in routes(app):
        key = endpoint_key(route.endpoint, method)
        assert key in POLICIES, (method, path, key)
        assert any(d.call is authorize_request for d in route.dependant.dependencies), path
        found.add(key)
        if POLICIES[key]["public"]:
            continue
        url = re.sub(r"\{[^}]+\}", "2", path)
        response = client.request(method, url, json={} if method != "GET" else None)
        assert response.status_code == 401, (method, path, response.status_code, response.text)
    assert found == set(POLICIES), "Unregistered or stale endpoint policies"


def test_viewer_cannot_mutate_any_endpoint(branches):
    import re
    from main_server import app
    from SHARED.policies.http import POLICIES, endpoint_key
    for path, method, route in routes(app):
        policy = POLICIES[endpoint_key(route.endpoint, method)]
        if policy["public"] or policy["action"] in {"read", "password_self"}:
            continue
        response = branches.request(method, re.sub(r"\{[^}]+\}", "1", path), json={}, headers=headers("viewer1"))
        assert response.status_code == 403, (method, path, response.text)


def test_operator_only_reports_and_no_side_effects(branches):
    import re
    from main_server import app
    from SHARED.policies.http import POLICIES, endpoint_key
    for path, method, route in routes(app):
        policy = POLICIES[endpoint_key(route.endpoint, method)]
        if policy["public"] or "operator" in policy["roles"]:
            continue
        response = branches.request(method, re.sub(r"\{[^}]+\}", "1", path), json={}, headers=headers("operator1"))
        assert response.status_code == 403, (method, path, response.text)
    for path in ("/api/reports/data", "/api/v1/repair/reports/data", "/api/v1/location/reports", "/api/v1/location/reports/csv"):
        assert branches.get(path, headers=headers("operator1")).status_code == 200


def test_network_report_scope_and_shared_port(branches):
    with SessionLocal() as db:
        db.get(m.Asset, 1).mac_address = "AA:BB:CC:DD:EE:01"
        db.get(m.Asset, 2).mac_address = "AA:BB:CC:DD:EE:02"
        db.get(m.SwitchPort, 1).learned_macs = ["AA:BB:CC:DD:EE:01", "11:22:33:44:55:66"]
        db.commit()
    response = branches.get("/api/v1/location/reports", headers=headers("operator1"))
    assert response.status_code == 200, response.text
    data = response.json()
    assert "INV1" in str(data)
    assert "INV2" not in str(data)
    assert "Branch 2" not in str(data)
    assert len([r for r in data["items"] if r["port"] == 1]) == 2
    assert branches.get("/api/v1/location/reports?branch_id=2", headers=headers("operator1")).status_code == 403
    assert branches.get("/api/cartridges/1", headers=headers("user1")).status_code == 403


def test_manual_registration_accepts_no_employee(branches):
    response = branches.post("/api/v1/repair/equipment", headers=headers("admin1"), json={
        "inventory_number": "EMPTY-OWNER", "name": "Monitor", "asset_type": "monitor", "current_user_id": ""})
    assert response.status_code == 200, response.text
    assert response.json()["current_user_id"] is None


def test_unmanaged_switch_supports_28_ports_and_manual_mapping(branches):
    response = branches.put("/api/v1/location/switches/1/ports/1", headers=headers("admin1"), json={
        "connection_mode": "unmanaged", "downstream_name": "Office 28", "downstream_port_count": 28,
        "downstream_ports": {"AA:BB:CC:DD:EE:01": 28}})
    assert response.status_code == 200, response.text
    assert response.json()["downstream_port_count"] == 28
    assert response.json()["downstream_ports"]["AA:BB:CC:DD:EE:01"] == 28
    with SessionLocal() as db:
        db.get(m.SwitchPort, 1).connected_asset_id = None
        db.commit()
    report = branches.get("/api/v1/location/reports", headers=headers("operator1")).json()
    assert any(row["downstream_name"] == "Office 28" and row["downstream_port_count"] == 28 for row in report["items"])
    response = branches.put("/api/v1/location/switches/1/ports/1", headers=headers("admin1"), json={
        "downstream_ports": {"AA:BB:CC:DD:EE:01": 29}})
    assert response.status_code == 422


def test_room_number_and_room_name_are_not_false_roaming(branches):
    with SessionLocal() as db:
        asset = db.get(m.Asset, 1)
        asset.mac_address, asset.zone_id, asset.cabinet = "AA:BB:CC:DD:EE:01", 1, "120"
        asset.coords_x = asset.coords_y = .5
        port = db.get(m.SwitchPort, 1)
        port.status, port.cabinet, port.learned_macs = "up", "Zone 1", ["AA:BB:CC:DD:EE:01"]
        db.commit()
    response = branches.get("/api/v1/location/floors/1/assets", headers=headers("admin1"))
    assert response.status_code == 200, response.text
    assert response.json()[0]["network_location_status"] == "online"


def test_acceptance_is_not_a_second_repair(branches):
    with SessionLocal() as db:
        db.add_all([m.EquipmentHistoryLog(asset_id=1, action="Приемка в IT-отдел"),
                    m.EquipmentHistoryLog(asset_id=1, action="Передача в сервисный центр")])
        db.commit()
    response = branches.get("/api/v1/repair/reports/data", headers=headers("admin1"))
    assert response.status_code == 200, response.text
    row = next(r for r in response.json()["report"]["items"] if r["inventory_number"] == "INV1")
    assert row["repairs_count_all"] == 1


def test_branch_selection_rejected_on_every_scoped_endpoint(branches):
    import re
    from main_server import app
    from SHARED.policies.http import POLICIES, endpoint_key
    for path, method, route in routes(app):
        policy = POLICIES[endpoint_key(route.endpoint, method)]
        if policy["public"] or not policy["branch_scope"]:
            continue
        response = branches.request(method, re.sub(r"\{[^}]+\}", "2", path), params={"branch_id": 2}, json={}, headers=headers())
        assert response.status_code == 403, (method, path, response.text)


def test_creates_use_server_branch_and_explicit_superadmin_scope(branches):
    for username, branch, status in [("admin1", None, 200), ("root", 2, 200)]:
        payload = {"inventory_number": username, "name": "Created"}
        if branch is not None:
            payload["branch_id"] = branch
        response = branches.post("/api/v1/repair/equipment", json=payload, headers=headers(username))
        assert response.status_code in (200, 201), response.text
        assert response.json()["branch_id"] == (branch or 1)


def test_batch_creation_retains_valid_branch_workflow(branches):
    with SessionLocal() as db:
        db.get(m.Asset, 1).status = m.AssetStatus.PENDING_SC
        db.get(m.Cartridge, 1).status = m.CartridgeStatus.PENDING_VENDOR
        db.commit()
    for url, body in [("/api/v1/repair/batches", {"asset_ids": [1], "vendor_name": "SC"}),
                      ("/api/batches", {"cartridge_ids": [1], "vendor_name": "SC"})]:
        response = branches.post(url, json=body, headers=headers("admin1"))
        assert response.status_code in (200, 201), response.text
    with SessionLocal() as db:
        assert db.query(m.RepairBatch).order_by(m.RepairBatch.id.desc()).first().branch_id == 1
        assert db.query(m.Batch).order_by(m.Batch.id.desc()).first().branch_id == 1


def test_branch_admin_user_permissions(branches):
    with SessionLocal() as db:
        ids = {u.username: u.id for u in db.query(m.AppUser).all()}
    for username, body in [("admin1", {"role": "superadmin"}), ("operator1", {"role": "admin"}),
                           ("operator1", {"branch_id": 2}), ("operator2", {"full_name": "Changed"})]:
        response = branches.put(f"/api/app-users/{ids[username]}", json=body, headers=headers())
        assert response.status_code in (403, 404), response.text
    response = branches.post("/api/app-users", json={"username": "escalation", "full_name": "X", "auth_type": "ad", "role": "superadmin"}, headers=headers())
    assert response.status_code == 403
    response = branches.post("/api/app-users", json={"username": "newstaff", "full_name": "X", "auth_type": "ad", "role": "operator"}, headers=headers())
    assert response.status_code == 201, response.text
    assert response.json()["branch_id"] == 1


def test_superadmin_cannot_create_cross_branch_relationships(branches):
    response = branches.post("/api/v1/repair/batches", json={"asset_ids": [1, 2], "vendor_name": "SC"}, headers=headers("root"))
    assert response.status_code == 403


def test_unknown_endpoint_fails_closed(client):
    from fastapi import FastAPI, Depends
    from fastapi.testclient import TestClient
    from SHARED.policies.http import authorize_request
    app = FastAPI(dependencies=[Depends(authorize_request)])
    @app.get("/unreviewed")
    def unreviewed():
        return {"leak": True}
    with TestClient(app) as test:
        assert test.get("/unreviewed").status_code == 403


def test_floor_maps_require_object_scope_and_are_not_public(branches):
    response = branches.post("/api/v1/location/floors/2/upload-map", files={"file": ("map.png", b"test map", "image/png")}, headers=headers("root"))
    assert response.status_code == 200, response.text
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "LOCATION/app/static/maps" / response.json()["map_image_url"].rsplit("/", 1)[1]
    try:
        assert branches.get(response.json()["map_image_url"]).status_code == 404
        assert branches.get("/api/v1/location/floors/2/map").status_code == 401
        assert branches.get("/api/v1/location/floors/2/map", headers=headers()).status_code == 404
        own = branches.get("/api/v1/location/floors/2/map", headers=headers("admin2"))
        assert own.content == b"test map" and "no-store" in own.headers["cache-control"]
        with SessionLocal() as db:
            db.get(m.Floor, 1).map_image_url = response.json()["map_image_url"]
            db.commit()
        assert branches.get("/api/v1/location/floors/1/map", headers=headers()).status_code == 404
    finally:
        path.unlink(missing_ok=True)


@pytest.mark.parametrize("path", ["/api/reports/data", "/api/v1/repair/reports/data", "/api/v1/location/stats",
                                  "/api/v1/location/placed-assets", "/api/v1/repair/ad/stats", "/api/v1/location/floors/1/switches"])
def test_reports_statistics_and_network_do_not_leak_foreign_objects(branches, path):
    response = branches.get(path, headers=headers("viewer1"))
    assert response.status_code == 200, response.text
    assert "Asset 2" not in response.text and "INV2" not in response.text and "Branch 2" not in response.text
    assert "10.2.0.1" not in response.text


def test_legacy_cross_branch_links_block_cascading_deletion(branches):
    with SessionLocal() as db:
        db.add(m.RepairBatchItem(batch_id=2, asset_id=1))
        db.commit()
    response = branches.delete("/api/v1/repair/equipment/1", headers=headers())
    assert response.status_code == 409, response.text
    with SessionLocal() as db:
        assert db.get(m.Asset, 1) is not None
        assert db.query(m.RepairBatchItem).filter_by(batch_id=2, asset_id=1).count() == 1


def test_admin_cannot_expand_network_allowlist(branches):
    response = branches.put("/api/branches/1", json={"network_subnets": ["0.0.0.0/0"]}, headers=headers())
    assert response.status_code == 403


def test_superadmin_can_explicitly_reassign_user_branch(branches):
    with SessionLocal() as db:
        uid = db.query(m.AppUser).filter_by(username="operator1").one().id
    response = branches.put(f"/api/app-users/{uid}", json={"branch_id": 2}, headers=headers("root"))
    assert response.status_code == 200, response.text
    assert response.json()["branch_id"] == 2


def test_inactive_and_unknown_roles_rejected(branches):
    with SessionLocal() as db:
        db.query(m.AppUser).filter_by(username="operator1").one().is_active = False
        db.query(m.AppUser).filter_by(username="viewer1").one().role = "invented"
        db.commit()
    assert branches.get("/api/v1/repair/equipment", headers=headers("operator1")).status_code == 401
    assert branches.get("/api/v1/repair/equipment", headers=headers("viewer1")).status_code == 403


def test_scope_layer_rejects_unscoped_sql_and_read_side_effects(branches):
    from fastapi import HTTPException
    from sqlalchemy import text
    from SHARED.policies.core import Principal, require_object_access
    from SHARED.policies.session import bind_scope
    with SessionLocal() as db:
        actor = Principal.from_user(db.query(m.AppUser).filter_by(username="admin1").one())
        # Even a direct helper call without a bound request cannot use a guessed ID.
        with pytest.raises(HTTPException):
            require_object_access(db, actor, m.Asset, 2)
        bind_scope(db, actor, {"action": "read"}, 1)
        with pytest.raises(HTTPException):
            db.execute(text("SELECT * FROM assets"))
        db.query(m.Asset).filter_by(id=1).one().name = "GET mutation"
        with pytest.raises(HTTPException):
            db.commit()


def test_notifications_preflight_all_ids_before_any_adapter_call(branches, monkeypatch):
    from CARTRIDGE.app.services.whatsapp_service import WhatsAppService
    def forbidden(*args, **kwargs):
        pytest.fail("External adapter called before authorization completed")
    monkeypatch.setattr(WhatsAppService, "get_instance_for_user", forbidden)
    response = branches.post("/api/notifications/whatsapp/ready", json={"cartridge_ids": [1, 2]}, headers=headers())
    assert response.status_code == 404


def test_authorized_cleanup_preserves_other_branch(branches):
    response = branches.delete("/api/v1/location/floors/1", headers=headers())
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        assert db.get(m.Floor, 1) is None
        assert db.get(m.Asset, 1).floor_id is None
        assert db.get(m.Asset, 2).floor_id == 2
    response = branches.delete("/api/v1/repair/equipment/1", headers=headers())
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        assert db.get(m.Asset, 1) is None and db.get(m.Asset, 2) is not None


def test_network_registration_cannot_create_allowlist_bypass(branches):
    response = branches.post("/api/v1/repair/equipment", json={
        "inventory_number": "bad-network", "name": "Switch", "asset_type": "switch",
        "switch_config": {"ip_address": "10.2.0.100"},
    }, headers=headers())
    assert response.status_code == 403, response.text

    response = branches.put("/api/v1/repair/equipment/1", json={
        "switch_config": {"ip_address": "10.1.0.1", "password": "write-only-test-value"},
    }, headers=headers("operator1"))
    assert response.status_code == 403, response.text


@pytest.mark.parametrize("content_type", ["application/json", "application/problem+json", None])
def test_bulk_preflight_matches_fastapi_json_content_types(branches, monkeypatch, content_type):
    from CARTRIDGE.app.services.whatsapp_service import WhatsAppService
    def forbidden(*args, **kwargs):
        pytest.fail("Adapter called for an unauthorized bulk request")
    monkeypatch.setattr(WhatsAppService, "get_instance_for_user", forbidden)
    request_headers = headers()
    if content_type:
        request_headers["Content-Type"] = content_type
    response = branches.post("/api/notifications/whatsapp/ready", content='{"cartridge_ids": [1, 2]}', headers=request_headers)
    assert response.status_code in (403, 404), response.text


def test_omada_controller_must_be_in_admin_branch_network(branches, monkeypatch):
    from LOCATION.app.services.switch_integration_service import SwitchIntegrationService
    def forbidden(**kwargs):
        raise AssertionError("Unauthorized controller must not be contacted")
    monkeypatch.setattr(SwitchIntegrationService,"test_connection",forbidden)
    response=branches.post('/api/v1/location/switches/test-connection',headers=headers('admin1'),json={
        'ip_address':'10.1.0.1','management_type':'omada','mgmt_port':8043,
        'extra_params':{'omada_auth_mode':'openapi','controller_host':'10.2.0.100'}})
    assert response.status_code == 403, response.text
