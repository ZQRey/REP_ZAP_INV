from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Body, status
from sqlalchemy.orm import Session, joinedload

from SHARED.database import get_db
from SHARED.models import (
    NetworkSwitch,
    SwitchPort,
    Asset,
    AssetType,
    AssetStatus,
    AssetCondition,
    AppUser,
    Floor,
    Zone,
    EquipmentHistoryLog
)
from SHARED.auth_service import get_current_user, require_role
from LOCATION.app.schemas import (
    NetworkSwitchResponse,
    NetworkSwitchCreate,
    NetworkSwitchUpdate,
    SwitchPortResponse,
    SwitchPortUpdate,
    SwitchSimulateRequest,
    SwitchConnectionTestRequest,
    SwitchConnectionTestResponse
)
from LOCATION.app.services.switch_integration_service import SwitchIntegrationService, normalize_mac

router = APIRouter(prefix="/api/v1/location", tags=["Location Switches"])


def _format_switch_response(sw: NetworkSwitch) -> NetworkSwitchResponse:
    """Вспомогательный форматер ответа коммутатора."""
    ports_out = []
    for p in sorted(sw.ports, key=lambda x: x.port_number):
        ports_out.append(SwitchPortResponse(
            id=p.id,
            switch_id=p.switch_id,
            port_number=p.port_number,
            port_speed=p.port_speed,
            vlan_id=p.vlan_id,
            status=p.status,
            cabinet=p.cabinet,
            socket_label=p.socket_label,
            zone_id=p.zone_id,
            last_mac=p.last_mac,
            last_ip=p.last_ip,
            last_seen_at=p.last_seen_at,
            connected_asset_id=p.connected_asset_id,
            connected_asset_name=p.connected_asset.name if p.connected_asset else None,
            connected_asset_inv=p.connected_asset.inventory_number if p.connected_asset else None
        ))

    return NetworkSwitchResponse(
        id=sw.id,
        asset_id=sw.asset_id,
        ip_address=sw.ip_address,
        management_type=sw.management_type or "snmp",
        mgmt_port=sw.mgmt_port or 161,
        username=sw.username,
        snmp_community=sw.snmp_community,
        model=sw.model,
        total_ports=sw.total_ports,
        name=sw.asset.name if sw.asset else "Коммутатор",
        cabinet=sw.asset.cabinet if sw.asset else None,
        last_poll_status=sw.last_poll_status or "never",
        last_poll_message=sw.last_poll_message,
        last_polled_at=sw.last_polled_at,
        floor_id=sw.asset.floor_id if sw.asset else None,
        coords_x=sw.asset.coords_x if sw.asset else None,
        coords_y=sw.asset.coords_y if sw.asset else None,
        extra_params=sw.extra_params,
        ports=ports_out
    )


@router.get("/floors/{floor_id}/switches", response_model=List[NetworkSwitchResponse])
def get_floor_switches(
    floor_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user)
):
    """Список коммутаторов на этаже с подробной раскладкой портов и привязкой к кабинетам."""
    switches = db.query(NetworkSwitch).join(Asset).options(
        joinedload(NetworkSwitch.asset),
        joinedload(NetworkSwitch.ports).joinedload(SwitchPort.connected_asset),
        joinedload(NetworkSwitch.ports).joinedload(SwitchPort.zone)
    ).filter(Asset.floor_id == floor_id).all()

    return [_format_switch_response(sw) for sw in switches]


@router.post("/switches", response_model=NetworkSwitchResponse, status_code=status.HTTP_201_CREATED)
def create_switch(
    payload: NetworkSwitchCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician"]))
):
    """Добавить новый управляемый коммутатор на этаж."""
    floor = db.query(Floor).filter(Floor.id == payload.floor_id).first()
    if not floor:
        raise HTTPException(status_code=404, detail="Этаж не найден")

    # Проверяем уникальность инвентарного номера
    req_inv = payload.inventory_number.strip() if payload.inventory_number and payload.inventory_number.strip() else None
    if req_inv:
        existing = db.query(Asset).filter(Asset.inventory_number == req_inv).first()
        inv_num = f"{req_inv}-{int(datetime.utcnow().timestamp()) % 10000}" if existing else req_inv
    else:
        clean_ip = payload.ip_address.strip().replace('.', '-').replace(':', '-')
        base_inv = f"SW-{clean_ip}"
        existing = db.query(Asset).filter(Asset.inventory_number == base_inv).first()
        inv_num = f"{base_inv}-{int(datetime.utcnow().timestamp()) % 10000}" if existing else base_inv

    asset = Asset(
        inventory_number=inv_num,
        name=payload.name.strip(),
        asset_type=AssetType.SWITCH,
        status=AssetStatus.AT_WORKPLACE,
        condition=AssetCondition.WORKING,
        branch_id=payload.branch_id or floor.branch_id,
        floor_id=payload.floor_id,
        cabinet=payload.cabinet,
        coords_x=max(0.0, min(1.0, payload.coords_x)),
        coords_y=max(0.0, min(1.0, payload.coords_y)),
        ip_address=payload.ip_address.strip()
    )
    db.add(asset)
    db.flush()

    total_ports = max(4, min(96, payload.total_ports))
    sw = NetworkSwitch(
        asset_id=asset.id,
        ip_address=payload.ip_address.strip(),
        management_type=payload.management_type,
        mgmt_port=payload.mgmt_port,
        username=payload.username.strip() if payload.username else None,
        password=payload.password.strip() if payload.password else None,
        snmp_community=payload.snmp_community.strip() if payload.snmp_community else "public",
        model=payload.model.strip() if payload.model else "L2 Managed Switch",
        total_ports=total_ports,
        extra_params=payload.extra_params or {"allow_demo_fallback": True}
    )
    db.add(sw)
    db.flush()

    # Генерируем порты
    for p in range(1, total_ports + 1):
        sport = SwitchPort(
            switch_id=sw.id,
            port_number=p,
            port_speed="1Gbps",
            vlan_id=1,
            status="down"
        )
        db.add(sport)

    db.commit()
    db.refresh(sw)
    return _format_switch_response(sw)


@router.put("/switches/{switch_id}", response_model=NetworkSwitchResponse)
def update_switch(
    switch_id: int,
    payload: NetworkSwitchUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician"]))
):
    """Обновить параметры подключения и интеграции коммутатора (Omada, MikroTik, HP, TP-Link, SNMP)."""
    sw = db.query(NetworkSwitch).options(
        joinedload(NetworkSwitch.asset),
        joinedload(NetworkSwitch.ports)
    ).filter(NetworkSwitch.id == switch_id).first()

    if not sw:
        raise HTTPException(status_code=404, detail="Коммутатор не найден")

    if payload.name and sw.asset:
        sw.asset.name = payload.name.strip()
    if payload.cabinet and sw.asset:
        sw.asset.cabinet = payload.cabinet.strip()
    if payload.ip_address:
        sw.ip_address = payload.ip_address.strip()
        if sw.asset:
            sw.asset.ip_address = sw.ip_address
    if payload.model is not None:
        sw.model = payload.model.strip() if payload.model else None
    if payload.management_type is not None:
        sw.management_type = payload.management_type
    if payload.mgmt_port is not None:
        sw.mgmt_port = payload.mgmt_port
    if payload.username is not None:
        sw.username = payload.username.strip() if payload.username else None
    if payload.password is not None and payload.password.strip():
        sw.password = payload.password.strip()
    if payload.snmp_community is not None:
        sw.snmp_community = payload.snmp_community.strip()
    if payload.extra_params is not None:
        sw.extra_params = payload.extra_params

    # Если изменилось число портов
    if payload.total_ports and payload.total_ports != sw.total_ports:
        new_total = max(4, min(96, payload.total_ports))
        current_max = max((p.port_number for p in sw.ports), default=0)
        if new_total > current_max:
            for p in range(current_max + 1, new_total + 1):
                db.add(SwitchPort(switch_id=sw.id, port_number=p, port_speed="1Gbps", status="down"))
        sw.total_ports = new_total

    db.commit()
    db.refresh(sw)
    return _format_switch_response(sw)


@router.post("/switches/test-connection", response_model=SwitchConnectionTestResponse)
def test_switch_connection(
    payload: SwitchConnectionTestRequest,
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician", "operator"]))
):
    """
    Проверка доступности коммутатора и корректности параметров авторизации (SSH / Omada / SNMP).
    """
    result = SwitchIntegrationService.test_connection(
        ip_address=payload.ip_address,
        management_type=payload.management_type,
        mgmt_port=payload.mgmt_port,
        username=payload.username,
        password=payload.password,
        snmp_community=payload.snmp_community,
        extra_params=payload.extra_params
    )
    return SwitchConnectionTestResponse(**result)


@router.delete("/switches/{switch_id}")
def delete_switch(
    switch_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician"]))
):
    """Удалить коммутатор с карты с очисткой портов."""
    try:
        sw = db.query(NetworkSwitch).filter(NetworkSwitch.id == switch_id).first()
        if not sw:
            raise HTTPException(status_code=404, detail="Коммутатор не найден")

        asset = sw.asset
        # Удаляем все порты коммутатора
        db.query(SwitchPort).filter(SwitchPort.switch_id == sw.id).delete(synchronize_session=False)
        db.delete(sw)
        if asset:
            db.query(SwitchPort).filter(SwitchPort.connected_asset_id == asset.id).update(
                {"connected_asset_id": None}, synchronize_session=False
            )
            db.query(EquipmentHistoryLog).filter(EquipmentHistoryLog.asset_id == asset.id).delete(synchronize_session=False)
            db.delete(asset)
        db.commit()
        return {"success": True, "message": "Коммутатор успешно удален"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка удаления коммутатора: {str(e)}")


@router.put("/switches/{switch_id}/ports/{port_number}", response_model=SwitchPortResponse)
def update_switch_port(
    switch_id: int,
    port_number: int,
    payload: SwitchPortUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician", "operator"]))
):
    """
    Настройка порта коммутатора:
    - Привязка порта к кабинету (напр. 'Кабинет 302')
    - Маркировка розетки (напр. 'Розетка 302-1')
    - Привязка к зоне этажа
    - VLAN ID и статус
    """
    sport = db.query(SwitchPort).filter(
        SwitchPort.switch_id == switch_id,
        SwitchPort.port_number == port_number
    ).first()

    if not sport:
        sport = SwitchPort(switch_id=switch_id, port_number=port_number)
        db.add(sport)

    if payload.cabinet is not None:
        sport.cabinet = payload.cabinet.strip() if payload.cabinet else None
    if payload.socket_label is not None:
        sport.socket_label = payload.socket_label.strip() if payload.socket_label else None
    if payload.vlan_id is not None:
        sport.vlan_id = payload.vlan_id
    if payload.status is not None:
        sport.status = payload.status
    if payload.zone_id is not None:
        sport.zone_id = payload.zone_id if payload.zone_id > 0 else None
        # Если указана зона, можно автоматически проставить кабинет
        if sport.zone_id:
            zone = db.query(Zone).filter(Zone.id == sport.zone_id).first()
            if zone and zone.name:
                sport.cabinet = zone.name

    if payload.connected_asset_id is not None:
        sport.connected_asset_id = payload.connected_asset_id if payload.connected_asset_id > 0 else None
        if sport.connected_asset_id:
            sport.status = "up"

    db.commit()
    db.refresh(sport)

    return SwitchPortResponse(
        id=sport.id,
        switch_id=sport.switch_id,
        port_number=sport.port_number,
        port_speed=sport.port_speed,
        vlan_id=sport.vlan_id,
        status=sport.status,
        cabinet=sport.cabinet,
        socket_label=sport.socket_label,
        zone_id=sport.zone_id,
        last_mac=sport.last_mac,
        last_ip=sport.last_ip,
        last_seen_at=sport.last_seen_at,
        connected_asset_id=sport.connected_asset_id,
        connected_asset_name=sport.connected_asset.name if sport.connected_asset else None,
        connected_asset_inv=sport.connected_asset.inventory_number if sport.connected_asset else None
    )


@router.post("/switches/{switch_id}/ports/{port_number}/connect")
def connect_switch_port(
    switch_id: int,
    port_number: int,
    asset_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician"]))
):
    """Быстрая коммутация порта с оконечным устройством."""
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


@router.post("/switches/{switch_id}/poll")
def poll_switch_mac_table(
    switch_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician", "operator"]))
):
    """
    Опрос коммутатора (Omada, MikroTik, HP, TP-Link, SNMP) и синхронизация MAC-таблицы:
    - Обнаруживает устройства на портах.
    - Автоматически отслеживает роуминг (перемещение компьютеров между кабинетами).
    - Перемещает маркеры на интерактивной карте в нужный кабинет!
    """
    try:
        result = SwitchIntegrationService.poll_switch(db=db, switch_id=switch_id)
        return result
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@router.post("/switches/{switch_id}/simulate-event")
def simulate_switch_event(
    switch_id: int,
    payload: SwitchSimulateRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician"]))
):
    """
    Тестирование / демонстрация перемещения техники (L2 Roaming):
    Симулирует обнаружение MAC-адреса на выбранном порту и проверяет автоматический переезд устройства.
    """
    try:
        res = SwitchIntegrationService.simulate_roaming_event(
            db=db,
            switch_id=switch_id,
            port_number=payload.port_number,
            mac_address=payload.mac_address,
            target_cabinet=payload.target_cabinet
        )
        return res
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex))
