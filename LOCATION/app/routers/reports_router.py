"""Branch-scoped inventory and switch forwarding-table reports."""
import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from SHARED.database import get_db
from SHARED.models import Asset, SwitchPort
from LOCATION.app.services.switch_integration_service import normalize_mac

router = APIRouter(prefix="/api/v1/location/reports", tags=["Location Reports"])
FIELDS = {
    "branch": "Филиал", "floor": "Этаж", "room": "Кабинет",
    "inventory_number": "Инвентарный номер", "name": "Техника", "mac": "MAC",
    "ip": "IP техники", "switch": "Коммутатор", "switch_ip": "IP коммутатора",
    "port": "Порт", "socket": "Розетка", "vlan": "VLAN", "connection": "Подключение",
    "downstream_name": "Свич в кабинете", "downstream_port_count": "Портов на свиче", "downstream_port": "Порт свича (вручную)",
    "status": "Состояние порта", "last_seen": "Последнее обнаружение",
}


def build_report(db: Session):
    assets = db.query(Asset).all()  # The shared ORM policy applies the authenticated branch scope.
    by_mac = {}
    for asset in assets:
        mac = normalize_mac(asset.mac_address)
        if mac:
            by_mac.setdefault(mac, []).append(asset)
    rows, observed = [], set()

    def row(asset=None, port=None, mac=None):
        switch = port.switch if port else None
        zone = port.zone if port and port.zone else (asset.zone if asset else None)
        floor = zone.floor if zone else (asset.floor if asset else (switch.asset.floor if switch else None))
        branch = asset.branch if asset else (switch.asset.branch if switch else None)
        topology = ((switch.extra_params or {}).get("port_topology", {}).get(str(port.port_number), {}) if port else {})
        mode = topology.get("mode", "auto")
        connection = {"auto": "Авто", "direct": "Напрямую", "unmanaged": "Через неуправляемый свич", "uplink": "Межкоммутаторный канал"}.get(mode, mode)
        if topology.get("name"):
            connection += ": " + topology["name"]
        return {
            "branch": branch.name if branch else "Не назначен", "floor": floor.name if floor else "Не размещена",
            "room": (zone.room_number or zone.name) if zone else (asset.cabinet if asset else (port.cabinet if port else "")),
            "inventory_number": asset.inventory_number if asset else "", "name": asset.name if asset else "Неизвестное устройство",
            "mac": mac or (asset.mac_address if asset else ""), "ip": asset.ip_address if asset else "",
            "switch": switch.asset.name if switch else "", "switch_ip": switch.ip_address if switch else "",
            "port": port.port_number if port else "", "socket": port.socket_label if port else "",
            "vlan": port.vlan_id if port else "", "connection": connection if port else "Не обнаружено",
            "downstream_name": topology.get("name", ""), "downstream_port_count": topology.get("port_count", ""),
            "downstream_port": topology.get("ports", {}).get(normalize_mac(mac or (asset.mac_address if asset else None)), ""),
            "status": port.status if port else "", "last_seen": port.last_seen_at.isoformat(timespec="seconds") if port and port.last_seen_at else "",
        }

    for port in db.query(SwitchPort).all():
        macs = sorted({normalize_mac(m) for m in (port.learned_macs or [])} - {None})
        for mac in macs:
            matches = by_mac.get(mac, [])
            # Duplicate MACs remain ambiguous; the report never invents an asset identity.
            asset = matches[0] if len(matches) == 1 else None
            rows.append(row(asset, port, mac))
            if asset:
                observed.add(asset.id)
        if port.connected_asset and port.connected_asset.id not in observed:
            rows.append(row(port.connected_asset, port))
            observed.add(port.connected_asset.id)
        topology = (port.switch.extra_params or {}).get("port_topology", {}).get(str(port.port_number), {})
        if not macs and not port.connected_asset and (topology or port.zone_id or port.socket_label or port.cabinet):
            rows.append(row(None, port))
    rows.extend(row(a) for a in assets if a.id not in observed)
    return rows


@router.get("")
def get_network_report(branch_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    rows = build_report(db)
    return {"columns": FIELDS, "items": rows, "total": len(rows)}


@router.get("/csv")
def export_network_report(branch_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(FIELDS.values())
    for row in build_report(db):
        # Spreadsheet exports must not execute formulas from user-supplied names.
        writer.writerow(("'" + str(row[k])) if str(row[k] or "").startswith(("=", "+", "-", "@")) else row[k] for k in FIELDS)
    return Response(output.getvalue().encode("utf-8-sig"), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="network-report.csv"'})
