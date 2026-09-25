from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from SHARED.database import get_db
from SHARED.models import NetworkSwitch, SwitchPort, Asset, AssetType, AssetStatus, AssetCondition, AppUser, Floor
from SHARED.auth_service import get_current_user, require_role
from LOCATION.app.schemas import NetworkSwitchResponse, SwitchPortResponse

router = APIRouter(prefix="/api/v1/location", tags=["Location Switches"])


@router.get("/floors/{floor_id}/switches", response_model=List[NetworkSwitchResponse])
def get_floor_switches(
    floor_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user)
):
    """Список коммутаторов на этаже с подробной раскладкой портов."""
    switches = db.query(NetworkSwitch).join(Asset).options(
        joinedload(NetworkSwitch.asset),
        joinedload(NetworkSwitch.ports).joinedload(SwitchPort.connected_asset)
    ).filter(Asset.floor_id == floor_id).all()

    # Если коммутаторов на этаже нет, создадим демонстрационный управляемый свитч SW-CORE01 в серверной
    if not switches:
        floor = db.query(Floor).filter(Floor.id == floor_id).first()
        if floor:
            sw_asset = Asset(
                inventory_number="SW-CORE-01",
                name="Cisco Catalyst 2960X-24TS",
                asset_type=AssetType.SWITCH,
                status=AssetStatus.AT_WORKPLACE,
                condition=AssetCondition.WORKING,
                branch_id=floor.branch_id,
                floor_id=floor_id,
                cabinet="Серверная 108",
                coords_x=0.20,
                coords_y=0.22,
                ip_address="192.168.1.254"
            )
            db.add(sw_asset)
            db.flush()

            sw = NetworkSwitch(
                asset_id=sw_asset.id,
                ip_address="192.168.1.254",
                snmp_community="public",
                model="Cisco Catalyst 2960X",
                total_ports=24
            )
            db.add(sw)
            db.flush()

            # Создаем 24 порта
            for p in range(1, 25):
                sport = SwitchPort(
                    switch_id=sw.id,
                    port_number=p,
                    port_speed="1Gbps",
                    vlan_id=10,
                    status="up" if p in (1, 2, 5, 12, 24) else "down"
                )
                db.add(sport)

            db.commit()
            switches = [sw]

    result = []
    for sw in switches:
        ports_out = []
        for p in sorted(sw.ports, key=lambda x: x.port_number):
            ports_out.append(SwitchPortResponse(
                id=p.id,
                switch_id=p.switch_id,
                port_number=p.port_number,
                port_speed=p.port_speed,
                vlan_id=p.vlan_id,
                status=p.status,
                connected_asset_id=p.connected_asset_id,
                connected_asset_name=p.connected_asset.name if p.connected_asset else None,
                connected_asset_inv=p.connected_asset.inventory_number if p.connected_asset else None
            ))

        result.append(NetworkSwitchResponse(
            id=sw.id,
            asset_id=sw.asset_id,
            ip_address=sw.ip_address,
            snmp_community=sw.snmp_community,
            model=sw.model,
            total_ports=sw.total_ports,
            name=sw.asset.name if sw.asset else "Коммутатор",
            floor_id=sw.asset.floor_id if sw.asset else None,
            coords_x=sw.asset.coords_x if sw.asset else None,
            coords_y=sw.asset.coords_y if sw.asset else None,
            ports=ports_out
        ))
    return result


@router.post("/switches/{switch_id}/ports/{port_number}/connect")
def connect_switch_port(
    switch_id: int,
    port_number: int,
    asset_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician"]))
):
    """Коммутация порта с оконечным устройством."""
    sport = db.query(SwitchPort).filter(
        SwitchPort.switch_id == switch_id,
        SwitchPort.port_number == port_number
    ).first()
    if not sport:
        raise HTTPException(status_code=404, detail="Порт не найден")

    sport.connected_asset_id = asset_id
    sport.status = "up" if asset_id else "down"
    db.commit()

    return {"success": True, "message": f"Порт {port_number} {'подключен к активу' if asset_id else 'отключен'}"}
