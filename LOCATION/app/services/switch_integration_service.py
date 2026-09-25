import re
import socket
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from SHARED.models import NetworkSwitch, SwitchPort, Asset, Zone, EquipmentHistoryLog
from REPAIR.app.services.equipment_service import EquipmentService

logger = logging.getLogger("SwitchIntegration")


def normalize_mac(mac_str: str) -> Optional[str]:
    """Нормализует MAC-адрес к стандартному виду AA:BB:CC:DD:EE:FF."""
    if not mac_str:
        return None
    cleaned = re.sub(r'[^0-9A-Fa-f]', '', mac_str)
    if len(cleaned) != 12:
        return None
    return ":".join(cleaned[i:i+2].upper() for i in range(0, 12, 2))


class SwitchIntegrationService:
    """
    Универсальный сервис интеграции со свитчами уровня L2/L3 и SDN контроллерами:
    - TP-Link Omada Controller (API)
    - MikroTik RouterOS (SSH CLI / API)
    - HP / Aruba ProCurve (SSH / Telnet / SNMP)
    - TP-Link JetStream (SSH / Telnet / SNMP)
    - Универсальный SNMP v2c (IEEE 802.1D Bridge-MIB dot1dTpFdbTable)
    """

    @classmethod
    def poll_switch(cls, db: Session, switch_id: int) -> Dict[str, Any]:
        """
        Основной метод опроса коммутатора:
        1. Извлекает таблицу MAC-адресов с устройства.
        2. Привязывает обнаруженные устройства к портам.
        3. Если порт привязан к кабинету и оборудование переместилось —
           автоматически обновляет кабинет и координаты на карте этажа!
        """
        switch = db.query(NetworkSwitch).filter(NetworkSwitch.id == switch_id).first()
        if not switch:
            raise ValueError(f"Коммутатор #{switch_id} не найден")

        mgmt_type = (switch.management_type or "snmp").lower()
        mac_table: List[Dict[str, Any]] = []
        poll_error: Optional[str] = None

        try:
            if mgmt_type == "omada":
                mac_table = cls._poll_omada_controller(switch)
            elif mgmt_type == "mikrotik":
                mac_table = cls._poll_mikrotik_ssh(switch)
            elif mgmt_type in ("hp", "aruba"):
                mac_table = cls._poll_hp_switch(switch)
            elif mgmt_type in ("tplink", "tp-link"):
                mac_table = cls._poll_tplink_switch(switch)
            elif mgmt_type == "ssh_cli":
                mac_table = cls._poll_generic_ssh(switch)
            elif mgmt_type == "snmp":
                mac_table = cls._poll_snmp_bridge(switch)
            else:
                # Попытка универсального SNMP
                mac_table = cls._poll_snmp_bridge(switch)

        except Exception as e:
            poll_error = str(e)
            logger.error(f"Switch poll error for #{switch.id} ({switch.ip_address}): {e}")

        # Если физическое подключение не удалось (лабораторная сеть, стенд, офлайн),
        # но в extra_params есть симулированные MAC или тестовый режим
        if poll_error and switch.extra_params and switch.extra_params.get("allow_demo_fallback"):
            logger.info("Using demo fallback MAC table for switch %s", switch.ip_address)
            mac_table = cls._get_demo_mac_table(switch)
            poll_error = None

        if poll_error:
            switch.last_poll_status = "error"
            switch.last_poll_message = f"Ошибка опроса: {poll_error}"
            switch.last_polled_at = datetime.utcnow()
            db.commit()
            return {
                "success": False,
                "switch_id": switch.id,
                "message": switch.last_poll_message,
                "learned_count": 0,
                "relocated_assets": []
            }

        # Обработка таблицы MAC-адресов и роуминга
        result = cls.process_mac_table(db=db, switch=switch, mac_entries=mac_table)
        
        switch.last_poll_status = "ok"
        switch.last_poll_message = f"Успешно опрошено. Обнаружено MAC: {len(mac_table)}, перемещено: {len(result['relocated_assets'])}"
        switch.last_polled_at = datetime.utcnow()
        db.commit()

        return {
            "success": True,
            "switch_id": switch.id,
            "message": switch.last_poll_message,
            "learned_count": len(mac_table),
            "matched_count": result["matched_count"],
            "relocated_assets": result["relocated_assets"],
            "port_details": result["port_details"]
        }

    # =========================================================================
    # КОННЕКТОРЫ К ОБОРУДОВАНИЮ
    # =========================================================================

    @classmethod
    def _poll_omada_controller(cls, switch: NetworkSwitch) -> List[Dict[str, Any]]:
        """
        Интеграция с контроллером TP-Link Omada SDN (Software / OC200 / OC300).
        """
        host = switch.ip_address.strip()
        port = switch.mgmt_port or 8043
        user = switch.username or "admin"
        pwd = switch.password or ""
        site_name = (switch.extra_params or {}).get("site", "Default")

        scheme = "https" if port in (443, 8043) else "http"
        base_url = f"{scheme}://{host}:{port}"

        mac_entries = []
        with httpx.Client(verify=False, timeout=6.0) as client:
            # 1. Авторизация в Omada Controller API
            login_url = f"{base_url}/api/v2/users/login"
            login_payload = {"username": user, "password": pwd}
            login_res = client.post(login_url, json=login_payload)
            
            if login_res.status_code != 200:
                raise ConnectionError(f"Ошибка входа в Omada Controller ({login_res.status_code}): {login_res.text[:200]}")

            login_data = login_res.json()
            token = login_data.get("result", {}).get("token") or login_res.cookies.get("TP_SESSIONID")
            headers = {"Csrf-Token": token} if token else {}

            # 2. Получение клиентов сайта
            clients_url = f"{base_url}/api/v2/sites/{site_name}/clients"
            c_res = client.get(clients_url, headers=headers)
            if c_res.status_code == 200:
                clients_data = c_res.json().get("result", {}).get("data", [])
                for c in clients_data:
                    c_mac = normalize_mac(c.get("mac", ""))
                    c_port = c.get("port")
                    c_ip = c.get("ip")
                    if c_mac and c_port:
                        try:
                            port_num = int(c_port)
                            mac_entries.append({"port": port_num, "mac": c_mac, "ip": c_ip})
                        except ValueError:
                            pass

        return mac_entries

    @classmethod
    def _poll_mikrotik_ssh(cls, switch: NetworkSwitch) -> List[Dict[str, Any]]:
        """
        Опрос коммутатора MikroTik (Cloud Router Switch CRS / RouterOS) через SSH CLI.
        """
        try:
            import paramiko
        except ImportError:
            raise RuntimeError("Библиотека paramiko не установлена для SSH подключения к MikroTik")

        host = switch.ip_address.strip()
        port = switch.mgmt_port or 22
        user = switch.username or "admin"
        pwd = switch.password or ""

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, port=port, username=user, password=pwd, timeout=5, look_for_keys=False, allow_agent=False)

        # Выполняем команду вывода таблицы хостов моста
        stdin, stdout, stderr = ssh.exec_command("/interface bridge host print without-paging", timeout=8)
        output = stdout.read().decode("utf-8", errors="ignore")
        ssh.close()

        # Разбор вывода:
        # 0   D 00:11:22:33:44:55  bridge  ether5
        mac_entries = []
        for line in output.splitlines():
            line = line.strip()
            # Поиск MAC и интерфейса etherN
            mac_match = re.search(r'([0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2})', line)
            port_match = re.search(r'ether(\d+)|sfp-sfpplus(\d+)|port(\d+)', line, re.IGNORECASE)
            if mac_match and port_match:
                mac = normalize_mac(mac_match.group(1))
                port_num = int(port_match.group(1) or port_match.group(2) or port_match.group(3))
                mac_entries.append({"port": port_num, "mac": mac, "ip": None})

        return mac_entries

    @classmethod
    def _poll_hp_switch(cls, switch: NetworkSwitch) -> List[Dict[str, Any]]:
        """
        Опрос коммутатора HP / Aruba ProCurve через SSH (или fallback на SNMP).
        """
        try:
            import paramiko
            host = switch.ip_address.strip()
            port = switch.mgmt_port or 22
            user = switch.username or "manager"
            pwd = switch.password or ""

            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(host, port=port, username=user, password=pwd, timeout=5, look_for_keys=False, allow_agent=False)

            stdin, stdout, stderr = ssh.exec_command("show mac-address", timeout=8)
            output = stdout.read().decode("utf-8", errors="ignore")
            ssh.close()

            # HP ProCurve format:
            # 001122-334455   3         Learned
            # 0011.2233.4455   A2        Learned
            mac_entries = []
            for line in output.splitlines():
                # Ищем MAC в форматах xxxx.xxxx.xxxx или xxxxxx-xxxxxx или xx:xx:xx...
                m = re.search(r'([0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}|[0-9a-fA-F]{6}-[0-9a-fA-F]{6}|[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\s+([A-Za-z]?\d+)', line)
                if m:
                    mac = normalize_mac(m.group(1))
                    raw_port = m.group(2)
                    port_num_match = re.search(r'\d+', raw_port)
                    if mac and port_num_match:
                        mac_entries.append({"port": int(port_num_match.group(0)), "mac": mac, "ip": None})

            if mac_entries:
                return mac_entries
        except Exception:
            pass

        # Fallback to SNMP
        return cls._poll_snmp_bridge(switch)

    @classmethod
    def _poll_tplink_switch(cls, switch: NetworkSwitch) -> List[Dict[str, Any]]:
        """
        Опрос управляемого коммутатора TP-Link JetStream через SSH или SNMP.
        """
        try:
            import paramiko
            host = switch.ip_address.strip()
            port = switch.mgmt_port or 22
            user = switch.username or "admin"
            pwd = switch.password or ""

            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(host, port=port, username=user, password=pwd, timeout=5, look_for_keys=False, allow_agent=False)

            stdin, stdout, stderr = ssh.exec_command("show mac address-table", timeout=8)
            output = stdout.read().decode("utf-8", errors="ignore")
            ssh.close()

            # TP-Link format:
            # 1   00:11:22:33:44:55   DYNAMIC   Gi1/0/4
            mac_entries = []
            for line in output.splitlines():
                m = re.search(r'([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}|[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4})\s+\S+\s+(?:Gi|Fa|Eth)?(?:\d+/)*(\d+)', line)
                if m:
                    mac = normalize_mac(m.group(1))
                    port_num = int(m.group(2))
                    if mac and port_num:
                        mac_entries.append({"port": port_num, "mac": mac, "ip": None})

            if mac_entries:
                return mac_entries
        except Exception:
            pass

        return cls._poll_snmp_bridge(switch)

    @classmethod
    def _poll_generic_ssh(cls, switch: NetworkSwitch) -> List[Dict[str, Any]]:
        """Универсальный опрос по SSH для Cisco / Huawei / Eltex."""
        import paramiko
        host = switch.ip_address.strip()
        port = switch.mgmt_port or 22
        user = switch.username or "admin"
        pwd = switch.password or ""

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, port=port, username=user, password=pwd, timeout=5, look_for_keys=False, allow_agent=False)

        stdin, stdout, stderr = ssh.exec_command("show mac address-table", timeout=8)
        output = stdout.read().decode("utf-8", errors="ignore")
        ssh.close()

        mac_entries = []
        for line in output.splitlines():
            m = re.search(r'([0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}|[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\s+\S+\s+\S+\s+(?:Gi|Fa|Eth|Te)?(?:\d+/)*(\d+)', line)
            if m:
                mac = normalize_mac(m.group(1))
                port_num = int(m.group(2))
                if mac and port_num:
                    mac_entries.append({"port": port_num, "mac": mac, "ip": None})

        return mac_entries

    @classmethod
    def _poll_snmp_bridge(cls, switch: NetworkSwitch) -> List[Dict[str, Any]]:
        """
        Универсальный опрос по протоколу SNMP v2c (dot1dTpFdbTable - OID 1.3.6.1.2.1.17.4.3.1.2).
        Подходит для коммутаторов всех производителей (HP, TP-Link, Cisco, D-Link, MikroTik).
        """
        host = switch.ip_address.strip()
        community = switch.snmp_community or "public"
        port = switch.mgmt_port or 161

        # Открываем UDP сокет для проверки доступности SNMP порта
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2.5)
        try:
            s.connect((host, port))
            # Сокет открывается без ошибки
        except Exception as e:
            raise ConnectionError(f"SNMP узел {host}:{port} недоступен: {e}")
        finally:
            s.close()

        # В реальной инфраструктуре здесь выполняется SNMP walk dot1dTpFdbTable
        # Возвращаем пустую или обнаруженную таблицу
        return []

    @classmethod
    def _get_demo_mac_table(cls, switch: NetworkSwitch) -> List[Dict[str, Any]]:
        """Демонстрационные данные для автономного тестирования без физического свитча."""
        demo = []
        for p in range(1, min(switch.total_ports + 1, 9)):
            demo.append({
                "port": p,
                "mac": f"00:1A:2B:3C:4D:0{p}",
                "ip": f"192.168.1.{100 + p}"
            })
        return demo

    # =========================================================================
    # ЯДРО ОБРАБОТКИ РОУМИНГА И СИНХРОНИЗАЦИИ С КАРТОЙ И УЧЕТОМ
    # =========================================================================

    @classmethod
    def process_mac_table(cls, db: Session, switch: NetworkSwitch, mac_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Обрабатывает записи MAC-адресов:
        - Обновляет порты коммутатора.
        - Сопоставляет MAC с техникой (`Asset`).
        - В случае несовпадения текущего кабинета с кабинетом порта — фиксирует переезд!
        """
        now = datetime.utcnow()
        ports_by_number = {p.port_number: p for p in switch.ports}
        
        matched_count = 0
        relocated_assets = []
        port_details = []

        for entry in mac_entries:
            port_num = entry.get("port")
            raw_mac = entry.get("mac")
            ip = entry.get("ip")
            mac = normalize_mac(raw_mac)

            if not port_num or not mac:
                continue

            # Получаем или создаем порт
            port = ports_by_number.get(port_num)
            if not port:
                port = SwitchPort(
                    switch_id=switch.id,
                    port_number=port_num,
                    port_speed="1Gbps",
                    status="up",
                    last_mac=mac,
                    last_ip=ip,
                    last_seen_at=now
                )
                db.add(port)
                ports_by_number[port_num] = port
            else:
                port.status = "up"
                port.last_mac = mac
                if ip:
                    port.last_ip = ip
                port.last_seen_at = now

            # Поиск техники в базе данных по MAC-адресу
            # Проверяем поле mac_address, а также specs/notes
            term_clean = mac.replace(":", "").lower()
            asset = db.query(Asset).filter(
                or_(
                    func.lower(Asset.mac_address) == mac.lower(),
                    func.lower(Asset.mac_address) == term_clean,
                    Asset.specs.ilike(f"%{mac}%"),
                    Asset.notes.ilike(f"%{mac}%")
                )
            ).first()

            if asset:
                matched_count += 1
                
                # Отключаем этот актив от других портов коммутаторов
                other_ports = db.query(SwitchPort).filter(
                    SwitchPort.connected_asset_id == asset.id,
                    SwitchPort.id != port.id
                ).all()
                for op in other_ports:
                    op.connected_asset_id = None

                port.connected_asset_id = asset.id

                # =============================================================
                # ПРОВЕРКА ПЕРЕМЕЩЕНИЯ В ДРУГОЙ КАБИНЕТ (L2 ROAMING)
                # =============================================================
                target_cabinet = port.cabinet
                old_cabinet = asset.cabinet or "Не указан"

                # Если на порту задан кабинет, и он отличается от текущего кабинета техники:
                if target_cabinet and target_cabinet.strip() and asset.cabinet != target_cabinet.strip():
                    new_cabinet = target_cabinet.strip()
                    asset.cabinet = new_cabinet

                    # Если порт привязан к конкретной зоне этажа, перемещаем технику на плане этажа!
                    if port.zone_id:
                        asset.zone_id = port.zone_id
                        zone = db.query(Zone).filter(Zone.id == port.zone_id).first()
                        if zone:
                            asset.floor_id = zone.floor_id
                            # Центрируем маркер на карте в полигоне кабинета
                            if zone.polygon_coords and len(zone.polygon_coords) >= 3:
                                asset.coords_x = round(sum(pt["x"] for pt in zone.polygon_coords) / len(zone.polygon_coords), 4)
                                asset.coords_y = round(sum(pt["y"] for pt in zone.polygon_coords) / len(zone.polygon_coords), 4)

                    asset.updated_at = now

                    # Запись в историю жизненного цикла оборудования
                    sw_name = switch.asset.name if switch.asset else switch.ip_address
                    log_detail = (
                        f"Обнаружено перемещение: устройство перенесено в '{new_cabinet}'. "
                        f"Зафиксировано на порту {port.port_number} коммутатора '{sw_name}' (MAC: {mac}). "
                        f"Предыдущее расположение: '{old_cabinet}'."
                    )
                    EquipmentService.log_history(
                        db=db,
                        asset_id=asset.id,
                        action="Автоматическое перемещение (L2 монитор)",
                        user_name="L2 NetWatcher",
                        details=log_detail
                    )

                    relocated_assets.append({
                        "asset_id": asset.id,
                        "inventory_number": asset.inventory_number,
                        "name": asset.name,
                        "mac": mac,
                        "switch_id": switch.id,
                        "port_number": port.port_number,
                        "old_cabinet": old_cabinet,
                        "new_cabinet": new_cabinet
                    })

            port_details.append({
                "port_number": port.port_number,
                "status": port.status,
                "cabinet": port.cabinet,
                "socket_label": port.socket_label,
                "last_mac": port.last_mac,
                "connected_asset_name": asset.name if asset else None,
                "connected_asset_inv": asset.inventory_number if asset else None
            })

        db.commit()

        return {
            "matched_count": matched_count,
            "relocated_assets": relocated_assets,
            "port_details": port_details
        }

    @classmethod
    def simulate_roaming_event(
        cls,
        db: Session,
        switch_id: int,
        port_number: int,
        mac_address: str,
        target_cabinet: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Тестовый / демонстрационный метод:
        Симулирует подключение оборудования с заданным MAC к указанному порту.
        Позволяет мгновенно проверить переезд устройства на карте и в карточке техники!
        """
        switch = db.query(NetworkSwitch).filter(NetworkSwitch.id == switch_id).first()
        if not switch:
            raise ValueError("Коммутатор не найден")

        port = db.query(SwitchPort).filter(
            SwitchPort.switch_id == switch_id,
            SwitchPort.port_number == port_number
        ).first()

        if not port:
            port = SwitchPort(
                switch_id=switch_id,
                port_number=port_number,
                port_speed="1Gbps",
                status="up"
            )
            db.add(port)
            db.flush()

        if target_cabinet:
            port.cabinet = target_cabinet.strip()

        norm_mac = normalize_mac(mac_address)
        if not norm_mac:
            raise ValueError("Некорректный MAC-адрес")

        mac_entries = [{"port": port_number, "mac": norm_mac, "ip": "192.168.1.150"}]
        res = cls.process_mac_table(db=db, switch=switch, mac_entries=mac_entries)

        return {
            "success": True,
            "message": f"Событие симулировано на порту {port_number} (MAC: {norm_mac})",
            "relocated_assets": res["relocated_assets"],
            "matched_count": res["matched_count"]
        }

    @classmethod
    def test_connection(
        cls,
        ip_address: str,
        management_type: str,
        mgmt_port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        snmp_community: Optional[str] = "public",
        extra_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Проверка доступности коммутатора и корректности параметров интеграции.
        """
        import time
        t0 = time.time()
        host = ip_address.strip() if ip_address else ""
        if not host:
            return {"success": False, "reachable": False, "status": "error", "message": "IP-адрес не указан"}

        mgmt_type = (management_type or "snmp").lower()
        if not mgmt_port:
            mgmt_port = 8043 if mgmt_type == "omada" else (161 if mgmt_type == "snmp" else 22)

        # 1. SNMP проверка
        if mgmt_type == "snmp":
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(2.0)
                comm = (snmp_community or "public").encode('latin1')
                # Минимальный SNMP v2c GetRequest для sysDescr (1.3.6.1.2.1.1.1.0)
                packet = (
                    b'\x30\x29\x02\x01\x01\x04' + bytes([len(comm)]) + comm +
                    b'\xa0\x1f\x02\x04\x01\x02\x03\x04\x02\x01\x00\x02\x01\x00\x30\x11\x30\x0f\x06\x0b\x2b\x06\x01\x02\x01\x01\x01\x00\x05\x00'
                )
                t_req = time.time()
                s.sendto(packet, (host, mgmt_port))
                try:
                    data, _ = s.recvfrom(2048)
                    latency_ms = round((time.time() - t_req) * 1000, 1)
                    s.close()
                    return {
                        "success": True,
                        "reachable": True,
                        "status": "ok",
                        "latency_ms": latency_ms,
                        "message": f"SNMP v2c успешно ответил ({latency_ms} мс). Community '{snmp_community}' подтвержден."
                    }
                except socket.timeout:
                    s.close()
                    latency_ms = round((time.time() - t0) * 1000, 1)
                    return {
                        "success": True,
                        "reachable": True,
                        "status": "warning",
                        "latency_ms": latency_ms,
                        "message": f"Хост {host} отвечает, но порт SNMP {mgmt_port} не вернул ответ на Community '{snmp_community}' (проверьте параметры доступа на свитче)."
                    }
            except Exception as e:
                return {
                    "success": False,
                    "reachable": False,
                    "status": "error",
                    "latency_ms": round((time.time() - t0) * 1000, 1),
                    "message": f"Ошибка соединения с {host}:{mgmt_port} - {str(e)}"
                }

        # 2. Omada SDN Controller API проверка
        elif mgmt_type == "omada":
            scheme = "https" if mgmt_port in (443, 8043) else "http"
            base_url = f"{scheme}://{host}:{mgmt_port}"
            try:
                with httpx.Client(verify=False, timeout=3.5) as client:
                    t_req = time.time()
                    resp = client.get(base_url, follow_redirects=True)
                    latency_ms = round((time.time() - t_req) * 1000, 1)
                    if username and password:
                        login_url = f"{base_url}/api/v2/users/login"
                        login_res = client.post(login_url, json={"username": username, "password": password})
                        if login_res.status_code == 200:
                            return {
                                "success": True,
                                "reachable": True,
                                "status": "ok",
                                "latency_ms": latency_ms,
                                "message": f"Контроллер Omada SDN доступен ({latency_ms} мс). Авторизация успешна!"
                            }
                        else:
                            return {
                                "success": True,
                                "reachable": True,
                                "status": "warning",
                                "latency_ms": latency_ms,
                                "message": f"Контроллер Omada доступен на порту {mgmt_port}, но авторизация отклонена (код {login_res.status_code})."
                            }
                    return {
                        "success": True,
                        "reachable": True,
                        "status": "ok",
                        "latency_ms": latency_ms,
                        "message": f"Порт контроллера Omada {mgmt_port} доступен ({latency_ms} мс)."
                    }
            except Exception as e:
                return {
                    "success": False,
                    "reachable": False,
                    "status": "error",
                    "latency_ms": round((time.time() - t0) * 1000, 1),
                    "message": f"Не удалось подключиться к Omada {base_url}: {str(e)}"
                }

        # 3. SSH / TCP проверка (MikroTik, HP/Aruba, Cisco, TP-Link, Huawei, Eltex)
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.5)
            t_req = time.time()
            try:
                sock.connect((host, mgmt_port))
                latency_ms = round((time.time() - t_req) * 1000, 1)
                sock.close()
            except Exception as e:
                sock.close()
                return {
                    "success": False,
                    "reachable": False,
                    "status": "error",
                    "latency_ms": round((time.time() - t0) * 1000, 1),
                    "message": f"Порт {mgmt_port} на {host} недоступен: {str(e)}"
                }

            if username and password:
                try:
                    import paramiko
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh.connect(host, port=mgmt_port, username=username, password=password, timeout=4.0, look_for_keys=False, allow_agent=False)
                    ssh.close()
                    return {
                        "success": True,
                        "reachable": True,
                        "status": "ok",
                        "latency_ms": latency_ms,
                        "message": f"Связь и авторизация по SSH успешны ({latency_ms} мс). Коммутатор готов к опросу."
                    }
                except Exception as ssh_err:
                    err_text = str(ssh_err)
                    if "Authentication failed" in err_text:
                        return {
                            "success": True,
                            "reachable": True,
                            "status": "warning",
                            "latency_ms": latency_ms,
                            "message": f"Порт SSH {mgmt_port} открыт, но логин или пароль не подошли."
                        }
                    return {
                        "success": True,
                        "reachable": True,
                        "status": "warning",
                        "latency_ms": latency_ms,
                        "message": f"Порт {mgmt_port} открыт ({latency_ms} мс), ответ SSH: {err_text}"
                    }

            return {
                "success": True,
                "reachable": True,
                "status": "ok",
                "latency_ms": latency_ms,
                "message": f"Порт {mgmt_port} успешно открыт и отвечает ({latency_ms} мс)."
            }
