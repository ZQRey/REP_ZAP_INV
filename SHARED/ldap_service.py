import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from SHARED.models import SystemSetting, ADUser, Asset, AssetType, AssetStatus, AssetCondition, Branch

logger = logging.getLogger("SHARED.ldap_service")


class LDAPService:
    @staticmethod
    def get_ldap_settings(db: Session) -> Dict[str, str]:
        """Получает текущие настройки подключения к Active Directory из базы данных."""
        settings = db.query(SystemSetting).all()
        return {s.key: (s.value or "") for s in settings}

    @staticmethod
    def sync_ad_users(db: Session) -> Dict[str, Any]:
        """
        Синхронизирует учетные записи сотрудников из Active Directory в таблицу ad_users.
        """
        settings = LDAPService.get_ldap_settings(db)
        host = settings.get("ad_host", "").strip()
        base_dn = settings.get("ad_base_dn", "").strip()
        bind_user = settings.get("ad_bind_user", "").strip()
        bind_pwd = settings.get("ad_bind_password", "").strip()
        filter_str = settings.get("ad_filter_users") or "(&(objectCategory=person)(objectClass=user)(!(userAccountControl:1.2.840.113556.1.4.803:=2)))"

        if not host or not base_dn:
            logger.warning("[AD SYNC] LDAP host or base_dn is empty. Sync aborted.")
            return {"status": "error", "message": "Настройки Active Directory не заполнены", "count": 0}

        try:
            from ldap3 import Server, Connection, ALL, SUBTREE
            server = Server(host, get_info=ALL, connect_timeout=5)
            conn = Connection(server, user=bind_user, password=bind_pwd, auto_bind=True)

            attrs = ["sAMAccountName", "displayName", "department", "physicalDeliveryOfficeName", "telephoneNumber", "mobile"]
            conn.search(
                search_base=base_dn,
                search_filter=filter_str,
                search_scope=SUBTREE,
                attributes=attrs
            )

            count_upserted = 0
            for entry in conn.entries:
                sam = str(entry.sAMAccountName.value).strip() if entry.sAMAccountName else None
                if not sam:
                    continue
                display_name = str(entry.displayName.value).strip() if entry.displayName else sam
                dept = str(entry.department.value).strip() if entry.department else None
                cab = str(entry.physicalDeliveryOfficeName.value).strip() if entry.physicalDeliveryOfficeName else None
                
                phone = None
                if hasattr(entry, 'mobile') and entry.mobile:
                    phone = str(entry.mobile.value).strip()
                elif hasattr(entry, 'telephoneNumber') and entry.telephoneNumber:
                    phone = str(entry.telephoneNumber.value).strip()

                user_obj = db.query(ADUser).filter(ADUser.samaccountname == sam).first()
                if user_obj:
                    user_obj.display_name = display_name
                    user_obj.department = dept
                    user_obj.cabinet = cab
                    user_obj.phone = phone
                    user_obj.updated_at = datetime.utcnow()
                else:
                    user_obj = ADUser(
                        samaccountname=sam,
                        display_name=display_name,
                        department=dept,
                        cabinet=cab,
                        phone=phone
                    )
                    db.add(user_obj)
                count_upserted += 1

            db.commit()
            conn.unbind()
            return {"status": "success", "message": f"Синхронизировано {count_upserted} сотрудников из AD", "count": count_upserted}

        except Exception as e:
            db.rollback()
            logger.error(f"[AD SYNC ERROR] Failed to sync users from AD: {e}")
            return {"status": "error", "message": f"Ошибка связи с Active Directory: {str(e)}", "count": 0}

    @staticmethod
    def sync_ad_computers(db: Session, default_branch_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Сбор информации о компьютерах из Active Directory.
        Запрашивает компьютеры (objectCategory=computer) и сохраняет их в реестр assets.
        Остальная техника (мониторы, принтеры, ИБП) вводится пользователями вручную.
        """
        settings = LDAPService.get_ldap_settings(db)
        host = settings.get("ad_host", "").strip()
        base_dn = settings.get("ad_base_dn", "").strip()
        bind_user = settings.get("ad_bind_user", "").strip()
        bind_pwd = settings.get("ad_bind_password", "").strip()
        filter_str = settings.get("ad_filter_computers") or "(&(objectCategory=computer)(!(userAccountControl:1.2.840.113556.1.4.803:=2)))"

        # Назначаем филиал по умолчанию (первый доступный), если не передан
        if not default_branch_id:
            main_branch = db.query(Branch).first()
            if main_branch:
                default_branch_id = main_branch.id

        added_count = 0
        updated_count = 0

        # Если настройки AD не заданы или подключение невозможно, проверим возможность тестового заполнения
        if not host or not base_dn or not bind_user:
            logger.info("[AD COMPUTERS] AD not configured, running demo/mock sync if database is empty")
            return LDAPService._seed_mock_computers(db, default_branch_id)

        try:
            from ldap3 import Server, Connection, ALL, SUBTREE
            server = Server(host, get_info=ALL, connect_timeout=5)
            conn = Connection(server, user=bind_user, password=bind_pwd, auto_bind=True)

            attrs = [
                "sAMAccountName",
                "dNSHostName",
                "operatingSystem",
                "operatingSystemVersion",
                "lastLogonTimestamp",
                "description",
                "objectGUID",
                "location"
            ]

            conn.search(
                search_base=base_dn,
                search_filter=filter_str,
                search_scope=SUBTREE,
                attributes=attrs
            )

            for entry in conn.entries:
                sam = str(entry.sAMAccountName.value).strip().rstrip("$") if entry.sAMAccountName else None
                dns_name = str(entry.dNSHostName.value).strip() if entry.dNSHostName else sam
                if not sam and not dns_name:
                    continue

                hostname = (dns_name or sam).lower()
                os_title = str(entry.operatingSystem.value).strip() if entry.operatingSystem else "Windows Workstation"
                os_ver = str(entry.operatingSystemVersion.value).strip() if entry.operatingSystemVersion else ""
                desc = str(entry.description.value).strip() if entry.description else ""
                guid = str(entry.objectGUID.value) if hasattr(entry, "objectGUID") and entry.objectGUID else None
                loc = str(entry.location.value).strip() if hasattr(entry, "location") and entry.location else None

                # Определяем тип: Сервер или Рабочая станция
                asset_type = AssetType.SERVER if "server" in os_title.lower() else AssetType.WORKSTATION

                # Инвентарный номер: ищем в описании (напр. "ИНВ-00123") или формируем по шаблону "AD-{hostname}"
                inv_number = None
                if desc and any(prefix in desc.upper() for prefix in ["ИНВ", "INV", "№", "N"]):
                    # Если в описании указан инвентарник
                    inv_number = desc.strip()
                else:
                    inv_number = f"AD-{sam.upper()}"

                # Ищем уже существующий компьютер по ad_guid, hostname или inv_number
                asset = None
                if guid:
                    asset = db.query(Asset).filter(Asset.ad_guid == guid).first()
                if not asset:
                    asset = db.query(Asset).filter(Asset.hostname == hostname).first()
                if not asset:
                    asset = db.query(Asset).filter(Asset.inventory_number == inv_number).first()

                full_os = f"{os_title} {os_ver}".strip()

                if asset:
                    asset.hostname = hostname
                    asset.os_name = full_os
                    asset.ad_guid = guid
                    if desc:
                        asset.notes = f"AD Description: {desc}"
                    if loc and not asset.cabinet:
                        asset.cabinet = loc
                    updated_count += 1
                else:
                    new_asset = Asset(
                        inventory_number=inv_number,
                        serial_number=None,
                        name=f"Компьютер {hostname.upper()}",
                        asset_type=asset_type,
                        status=AssetStatus.AT_WORKPLACE,
                        condition=AssetCondition.WORKING,
                        ad_guid=guid,
                        hostname=hostname,
                        os_name=full_os,
                        branch_id=default_branch_id,
                        cabinet=loc or "Кабинет 101",
                        specs={"OS": full_os, "Source": "Active Directory"},
                        notes=f"Собрано из AD: {desc}" if desc else "Собрано из Active Directory"
                    )
                    db.add(new_asset)
                    added_count += 1

            db.commit()
            conn.unbind()
            return {
                "status": "success",
                "message": f"Сбор из AD завершен: добавлено {added_count}, обновлено {updated_count} компьютеров",
                "added": added_count,
                "updated": updated_count
            }

        except Exception as e:
            db.rollback()
            logger.error(f"[AD COMPUTERS SYNC ERROR] Failed to sync computers from AD: {e}")
            existing_pc_count = db.query(Asset).count()
            if existing_pc_count == 0:
                mock_res = LDAPService._seed_mock_computers(db, default_branch_id)
                mock_res["message"] = f"Сервер AD недоступен ({str(e)}). Загружен стартовый демонстрационный пул компьютеров AD."
                return mock_res
            return {
                "status": "error",
                "message": f"Не удалось подключиться к серверу AD ({str(e)}). Проверьте настройки LDAP.",
                "added": 0,
                "updated": 0
            }

    @staticmethod
    def _seed_mock_computers(db: Session, branch_id: Optional[int]) -> Dict[str, Any]:
        """Создает тестовый набор компьютеров AD для автономной демонстрации, если в базе пусто."""
        existing_pc_count = db.query(Asset).filter(Asset.ad_guid != None).count()
        if existing_pc_count > 0:
            return {"status": "info", "message": f"В базе уже имеется {existing_pc_count} компьютеров из AD.", "added": 0, "updated": 0}

        demo_pcs = [
            ("AD-PC-BUH01", "buh-pc01", "Windows 11 Pro 23H2", "Бухгалтерия Главный бухгалтер", "Кабинет 201", "guid-buh-01"),
            ("AD-PC-BUH02", "buh-pc02", "Windows 10 Pro 22H2", "Бухгалтерия Расчетчик", "Кабинет 201", "guid-buh-02"),
            ("AD-PC-IT01", "it-admin", "Windows 11 Pro 23H2", "IT Отдел Рабочая станция", "Кабинет 108", "guid-it-01"),
            ("AD-PC-IT02", "it-support", "Windows 11 Pro 23H2", "IT Отдел Техник", "Кабинет 108", "guid-it-02"),
            ("AD-PC-DIR01", "dir-laptop", "Windows 11 Pro 23H2", "Дирекция Ноутбук", "Кабинет 301", "guid-dir-01"),
            ("AD-SRV-DC01", "srv-dc01", "Windows Server 2022", "Контроллер домена AD", "Серверная", "guid-srv-01"),
        ]

        added = 0
        for inv, host, os_name, desc, cab, guid in demo_pcs:
            asset = Asset(
                inventory_number=inv,
                name=f"Компьютер {host.upper()}",
                asset_type=AssetType.SERVER if "Server" in os_name else AssetType.WORKSTATION,
                status=AssetStatus.AT_WORKPLACE,
                condition=AssetCondition.WORKING,
                ad_guid=guid,
                hostname=host,
                os_name=os_name,
                branch_id=branch_id,
                cabinet=cab,
                specs={"OS": os_name, "Source": "Active Directory Demo"},
                notes=f"AD: {desc}"
            )
            db.add(asset)
            added += 1

        db.commit()
        return {
            "status": "success",
            "message": f"Демонстрационный сбор завершен: загружено {added} компьютеров с параметрами AD",
            "added": added,
            "updated": 0
        }
