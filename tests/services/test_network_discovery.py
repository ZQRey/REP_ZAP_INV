import pytest
from SHARED.database import SessionLocal
from SHARED import models as m
from LOCATION.app.services.switch_integration_service import SwitchIntegrationService


def setup_network(db):
    b1=m.Branch(name="Origin"); b2=m.Branch(name="Destination")
    db.add_all([b1,b2]); db.flush()
    floor=m.Floor(branch_id=b2.id,name="Floor",floor_number=1)
    db.add(floor); db.flush()
    zone=m.Zone(floor_id=floor.id,name="Office",room_number="202",polygon_coords=[{"x":.1,"y":.1},{"x":.3,"y":.1},{"x":.3,"y":.3}])
    pc=m.Asset(branch_id=b1.id,inventory_number="PC",name="PC",mac_address="aabb.ccdd.eeff")
    sw_asset=m.Asset(branch_id=b2.id,inventory_number="SW",name="SW",floor_id=floor.id)
    db.add_all([zone,pc,sw_asset]);db.flush()
    sw=m.NetworkSwitch(asset_id=sw_asset.id,ip_address="10.0.0.2")
    db.add(sw);db.flush()
    db.add(m.SwitchPort(switch_id=sw.id,port_number=1,zone_id=zone.id))
    db.commit()
    return pc,sw,zone,b2


def test_unique_mac_transfers_between_branches(client):
    with SessionLocal() as db:
        pc,sw,zone,b2=setup_network(db)
        result=SwitchIntegrationService.process_mac_table(db,sw,[{"port":1,"mac":"AA:BB:CC:DD:EE:FF"}])
        assert result["matched_count"] == 1
        assert (pc.branch_id,pc.floor_id,pc.zone_id,pc.cabinet) == (b2.id,zone.floor_id,zone.id,"202")
        assert pc.coords_x == pytest.approx(.23333333)
        assert db.query(m.EquipmentHistoryLog).filter_by(asset_id=pc.id).count() == 1


def test_uplink_does_not_move_asset(client):
    with SessionLocal() as db:
        pc,sw,zone,b2=setup_network(db)
        old_branch=pc.branch_id
        result=SwitchIntegrationService.process_mac_table(db,sw,[{"port":1,"mac":"aabbccddeeff"},{"port":1,"mac":"112233445566"}])
        assert result["relocated_assets"] == []
        assert pc.branch_id == old_branch


@pytest.mark.parametrize("setting,expected", [("true",True),("false",False)])
def test_ad_sync_uses_login_transport_settings(client, monkeypatch, setting, expected):
    from SHARED.ldap_service import LDAPService
    from types import SimpleNamespace
    calls=[]
    monkeypatch.setattr(LDAPService,"get_ldap_settings",lambda db: {
        "ad_host":"ldap://dc.example:389","ad_base_dn":"DC=example", "ad_bind_user":"svc",
        "ad_bind_password":"password", "ad_allow_plaintext":setting})
    monkeypatch.setattr("SHARED.ldap_service.ldap_connection", lambda *a,**kw:
        (calls.append(kw) or SimpleNamespace(entries=[],search=lambda **kw: True,unbind=lambda:None)))
    with SessionLocal() as db:
        assert LDAPService.sync_ad_computers(db)["status"] == "success"
    assert calls[0]["allow_plaintext"] is expected


def test_room_description_round_trip_and_user_denial(client, account):
    from SHARED.tokens import create_access_token
    headers={"Authorization":"Bearer "+create_access_token({"sub":account["username"]})}
    with SessionLocal() as db:
        branch=m.Branch(name="Rooms");db.add(branch);db.flush()
        floor=m.Floor(branch_id=branch.id,name="Plan",floor_number=1);db.add(floor);db.flush()
        fid=floor.id; bid=branch.id
        db.add(m.AppUser(username="ordinary",full_name="Ordinary",role="user",branch_id=branch.id,is_active=True))
        db.commit()
    payload={"name":"Office","room_number":"101","description":"Accounting", "polygon_coords":[{"x":.1,"y":.1},{"x":.4,"y":.1},{"x":.4,"y":.4}]}
    response=client.post(f"/api/v1/location/floors/{fid}/zones",json=payload,headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["description"] == "Accounting"
    payload["description"]="IT office"
    response=client.put(f"/api/v1/location/zones/{response.json()['id']}",json=payload,headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["description"] == "IT office"
    ordinary={"Authorization":"Bearer "+create_access_token({"sub":"ordinary"})}
    for route in (f"/api/v1/location/branches/{bid}/floors", "/api/v1/repair/equipment"):
        assert client.get(route,headers=ordinary).status_code == 403


def test_superadmin_http_poll_transfers_atomically(client, account, monkeypatch):
    from SHARED.tokens import create_access_token
    with SessionLocal() as db:
        pc,sw,zone,b2=setup_network(db)
        pid,sid,zid,bid=pc.id,sw.id,zone.id,b2.id
    monkeypatch.setattr("LOCATION.app.services.switch_integration_service.validate_device_address",lambda address:None)
    monkeypatch.setattr(SwitchIntegrationService,"_poll_snmp_bridge",lambda sw:[{"port":1,"mac":"aabbccddeeff"}])
    response=client.post(f"/api/v1/location/switches/{sid}/poll",headers={"Authorization":"Bearer "+create_access_token({"sub":account["username"]})})
    assert response.status_code == 200, response.text
    assert response.json()["relocated_assets"][0]["asset_id"] == pid
    with SessionLocal() as db:
        pc=db.get(m.Asset,pid)
        assert (pc.branch_id,pc.zone_id) == (bid,zid)


def test_owner_branch_comes_from_cartridge_and_admin_is_unchanged(client):
    from SHARED.user_branch import sync_cartridge_owner_branch
    with SessionLocal() as db:
        branch=m.Branch(name="Ownership");db.add(branch);db.flush()
        ordinary=m.AppUser(username="owner",full_name="Owner",role="user",is_active=True)
        admin=m.AppUser(username="administrator",full_name="Admin",role="admin",is_active=True)
        db.add_all([ordinary,admin,m.ADUser(samaccountname="OWNER",display_name="Owner")]);db.flush();db.add(m.Cartridge(marker_label="OWN",model="HP",cabinet="1",branch_id=branch.id,current_user_id="OWNER"));db.flush()
        assert sync_cartridge_owner_branch(db,ordinary)
        assert ordinary.branch_id == branch.id
        assert not sync_cartridge_owner_branch(db,admin)
        assert admin.branch_id is None


def test_new_user_without_cartridges_gets_empty_list(client):
    from SHARED.tokens import create_access_token
    with SessionLocal() as db:
        db.add(m.AppUser(username="new-owner",full_name="New",role="user",is_active=True));db.commit()
    headers={"Authorization":"Bearer "+create_access_token({"sub":"new-owner"})}
    response=client.get('/api/cartridges',headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == []
