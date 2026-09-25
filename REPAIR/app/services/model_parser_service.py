import re
import statistics
from typing import Dict, Any, Optional, List, Tuple
from collections import Counter
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from SHARED.models import Asset, AssetType, EquipmentModel

# Справочник известных вендоров
KNOWN_VENDORS = [
    ("HEWLETT-PACKARD", "HP"),
    ("HEWLETT PACKARD", "HP"),
    ("HP", "HP"),
    ("DELL", "Dell"),
    ("LENOVO", "Lenovo"),
    ("IBM", "IBM"),
    ("ACER", "Acer"),
    ("ASUS", "ASUS"),
    ("APPLE", "Apple"),
    ("MICROSOFT", "Microsoft"),
    ("SAMSUNG", "Samsung"),
    ("LG", "LG"),
    ("PHILIPS", "Philips"),
    ("AOC", "AOC"),
    ("BENQ", "BenQ"),
    ("VIEWSONIC", "ViewSonic"),
    ("CISCO", "Cisco"),
    ("MIKROTIK", "MikroTik"),
    ("TP-LINK", "TP-Link"),
    ("TPLINK", "TP-Link"),
    ("D-LINK", "D-Link"),
    ("DLINK", "D-Link"),
    ("ELTEX", "Eltex"),
    ("HUAWEI", "Huawei"),
    ("ZYXEL", "Zyxel"),
    ("UBIQUITI", "Ubiquiti"),
    ("UNIFI", "Ubiquiti"),
    ("NETGEAR", "Netgear"),
    ("CANON", "Canon"),
    ("EPSON", "Epson"),
    ("XEROX", "Xerox"),
    ("PANTUM", "Pantum"),
    ("KYOCERA", "Kyocera"),
    ("BROTHER", "Brother"),
    ("RICOH", "Ricoh"),
    ("KONICA MINOLTA", "Konica Minolta"),
    ("APC", "APC"),
    ("CYBERPOWER", "CyberPower"),
    ("IPPON", "Ippon"),
    ("POWERCOM", "Powercom"),
    ("EATON", "Eaton"),
    ("SUPERMICRO", "Supermicro"),
    ("INTEL", "Intel"),
    ("AMD", "AMD"),
    ("AQUARIUS", "Aquarius"),
    ("DEPO", "Depo"),
    ("KRAFTWAY", "Kraftway"),
    ("ICL", "ICL"),
]

# Шаблоны категорий
CATEGORY_PATTERNS = [
    # Коммутаторы / Свитчи
    ("switch", [
        r"\bswitch\b", r"коммутатор", r"свитч", r"catalyst", r"edgeswitch", r"jetstream",
        r"procurve", r"aruba", r"\bcrs\d+", r"tl-sg", r"\bsg\d+", r"\bdgs-\d+", r"\bdes-\d+",
        r"\bmes\d+", r"cloud router switch"
    ]),
    # ИБП (UPS)
    ("ups", [
        r"\bups\b", r"ибп", r"smart-ups", r"back-ups", r"innova", r"smart winner",
        r"back power", r"bnt-", r"spt-"
    ]),
    # Принтеры / МФУ
    ("printer", [
        r"laserjet", r"ecotank", r"pagewide", r"i-sensys", r"phaser", r"workcentre",
        r"\bmfp\b", r"мфу", r"принтер", r"printer", r"ecosys", r"pixma", r"deskjet",
        r"stylus", r"sharp", r"dcp-", r"mfc-"
    ]),
    # Мониторы
    ("monitor", [
        r"монитор", r"monitor", r"ultrasharp", r"proart", r"syncmaster", r"flatron",
        r"\bips\b.*display", r"gaming monitor"
    ]),
    # Ноутбуки
    ("laptop", [
        r"ноутбук", r"laptop", r"notebook", r"thinkpad", r"latitude", r"inspiron",
        r"vostro", r"xps", r"probook", r"elitebook", r"macbook", r"ideapad",
        r"yoga", r"aspire", r"zenbook", r"expertbook", r"travelmate"
    ]),
    # Серверы
    ("server", [
        r"proliant", r"poweredge", r"primergy", r"\bserver\b", r"сервер", r"\bdc01\b", r"\bsrv\b"
    ]),
    # Рабочие станции / ПК
    ("workstation", [
        r"prodesk", r"elitedesk", r"optiplex", r"precision", r"thinkcentre",
        r"veriton", r"workstation", r"\bпк\b", r"компьютер", r"\btower\b",
        r"\bmicro\b", r"\bsff\b", r"desktop", r"system unit", r"системный блок"
    ])
]


class ModelParserService:
    """Сервис умного распознавания моделей, вендоров, категорий и расчета средних характеристик."""

    @classmethod
    def parse_vendor(cls, text: str) -> Optional[str]:
        if not text:
            return None
        upper = text.upper()
        for pattern, canonical in KNOWN_VENDORS:
            # Ищем границу слова или вхождение
            if re.search(r'\b' + re.escape(pattern) + r'\b', upper):
                return canonical
        return None

    @classmethod
    def parse_category(cls, text: str) -> str:
        if not text:
            return "workstation"
        lower = text.lower()
        for cat, patterns in CATEGORY_PATTERNS:
            for pat in patterns:
                if re.search(pat, lower):
                    return cat
        return "workstation"

    @classmethod
    def parse_model_details(cls, raw_name: str) -> Dict[str, Any]:
        """
        Анализирует полное наименование модели и определяет:
        - Производителя (Vendor)
        - Категорию (Category)
        - Чистое название
        """
        raw_clean = (raw_name or "").strip()
        vendor = cls.parse_vendor(raw_clean)
        category = cls.parse_category(raw_clean)

        return {
            "name": raw_clean,
            "vendor": vendor,
            "category": category
        }

    @classmethod
    def calculate_average_specs(
        cls,
        db: Session,
        category: Optional[str] = None,
        vendor: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Подтягивает типовые характеристики с компьютеров/оборудования в среднем значении.
        Анализирует базу существующих активов (Asset.specs, Asset.os_name).
        """
        query = db.query(Asset)
        cat_clean = (category or "").lower()

        if cat_clean and cat_clean in [e.value for e in AssetType]:
            query = query.filter(Asset.asset_type == AssetType(cat_clean))
        elif cat_clean == "switch":
            query = query.filter(Asset.asset_type == AssetType.SWITCH)
        elif cat_clean in ("workstation", "laptop"):
            query = query.filter(Asset.asset_type.in_([AssetType.WORKSTATION, AssetType.LAPTOP]))

        if vendor:
            query = query.filter(Asset.name.ilike(f"%{vendor}%"))

        if model_name:
            # Отсекаем слишком специфичные слова
            words = [w for w in re.split(r'\s+', model_name) if len(w) >= 3 and w.lower() not in ("компьютер", "ноутбук", "модель", "новый")]
            if words:
                conditions = [Asset.name.ilike(f"%{w}%") for w in words[:2]]
                query = query.filter(or_(*conditions))

        assets = query.limit(100).all()

        # Если в базе нет таких активов, попробуем общую выборку по категории
        if not assets and cat_clean in ("workstation", "laptop", "server"):
            assets = db.query(Asset).filter(
                Asset.asset_type.in_([AssetType.WORKSTATION, AssetType.LAPTOP, AssetType.SERVER])
            ).limit(50).all()

        ram_values: List[int] = []
        cpu_list: List[str] = []
        storage_list: List[str] = []
        os_list: List[str] = []

        for a in assets:
            # Извлекаем ОС
            if a.os_name:
                os_clean = a.os_name.strip()
                if "Windows" in os_clean or "Linux" in os_clean:
                    os_list.append(os_clean)

            specs = a.specs if isinstance(a.specs, dict) else {}

            # Извлекаем RAM (ГБ)
            raw_ram = str(specs.get("RAM") or specs.get("ram") or specs.get("Память") or "")
            ram_match = re.search(r'(\d+)\s*(?:gb|гб|g|г)', raw_ram.lower())
            if ram_match:
                try:
                    ram_values.append(int(ram_match.group(1)))
                except ValueError:
                    pass

            # Извлекаем CPU
            raw_cpu = str(specs.get("CPU") or specs.get("cpu") or specs.get("Процессор") or "").strip()
            if raw_cpu:
                cpu_list.append(raw_cpu)

            # Извлекаем Накопитель
            raw_storage = str(specs.get("Storage") or specs.get("storage") or specs.get("SSD") or specs.get("Disk") or specs.get("Накопитель") or "").strip()
            if raw_storage:
                storage_list.append(raw_storage)

        # Вычисляем средние значения (или наиболее частотные)
        sample_size = len(assets)

        # RAM
        avg_ram = 16 # Базовое значение по умолчанию
        if ram_values:
            mean_ram = statistics.mean(ram_values)
            # Округляем к стандартным значениям RAM (4, 8, 16, 32, 64)
            standard_rams = [4, 8, 16, 32, 64]
            avg_ram = min(standard_rams, key=lambda x: abs(x - mean_ram))

        # CPU (наиболее часто встречающийся или типовой)
        common_cpu = Counter(cpu_list).most_common(1)[0][0] if cpu_list else (
            "Intel Core i5 (6 ядер, 2.9-4.3 GHz)" if cat_clean != "server" else "Intel Xeon Silver (8 ядер)"
        )

        # Storage
        common_storage = Counter(storage_list).most_common(1)[0][0] if storage_list else "512 GB NVMe SSD"

        # OS
        common_os = Counter(os_list).most_common(1)[0][0] if os_list else "Windows 11 Pro 64-bit"

        # Формируем типовые характеристики в зависимости от категории
        if cat_clean in ("workstation", "laptop"):
            template = f"{common_cpu} | {avg_ram} GB DDR4 RAM | {common_storage} | {common_os}"
        elif cat_clean == "switch":
            # Для коммутатора типовые характеристики
            ports = "24"
            if model_name:
                p_match = re.search(r'(\d+)(?:p|port|порт|ts|g|-)', model_name.lower())
                if p_match and int(p_match.group(1)) in (8, 16, 24, 48):
                    ports = p_match.group(1)
            template = f"{ports}x 10/100/1000 Mbps RJ45 | Managed L2 | 802.1Q VLAN | SNMP/SSH"
        elif cat_clean == "printer":
            template = "Лазерная печать A4 | Скорость до 38 стр/мин | Двусторонняя печать (Duplex) | Ethernet LAN"
        elif cat_clean == "ups":
            template = "Линейно-интерактивный ИБП 1500VA / 900W | Чистая синусоида | LCD дисплей | USB/SNMP"
        elif cat_clean == "monitor":
            template = "23.8\" IPS (1920x1080) | 75Hz | Яркость 250 кд/м² | HDMI, DisplayPort"
        else:
            template = f"{common_cpu} | {avg_ram} GB RAM | {common_storage}"

        return {
            "specs_template": template,
            "sample_size": sample_size,
            "average_ram_gb": avg_ram,
            "common_cpu": common_cpu,
            "common_storage": common_storage,
            "common_os": common_os
        }

    @classmethod
    def clean_os_title(cls, raw: Optional[str]) -> str:
        """Очищает строку ОС до понятного наименования редакции (напр. 'Windows 10 Pro')."""
        if not raw or "unknown" in str(raw).lower():
            return "Windows (редакция не указана)"
        s = str(raw).strip()
        s = re.sub(r'\s*\d+\.\d+(?:\.\d+)?(?:\s*\(\d+\))?', '', s)
        s = re.sub(r'\s*\(\d+\)', '', s)
        s = re.sub(r'\s*Build\s*\d+', '', s, flags=re.I)
        s = re.sub(r'\s+2[0-9]H[1-2]', '', s)
        s = re.sub(r'\s+', ' ', s).strip()
        return s or "Windows"

    @classmethod
    def determine_computer_model(
        cls,
        hostname: Optional[str],
        os_name: Optional[str],
        notes: Optional[str] = None,
        current_asset_type: Optional[AssetType] = None
    ) -> Dict[str, Any]:
        """
        Укрупненная группировка компьютеров организации в понятные пулы:
        - «Рабочая станция / ПК» (все клиентские офисные ПК и моноблоки)
        - «Серверное оборудование» (все контроллеры домена и сервисные серверы)
        - «Ноутбук / Мобильный ПК» (ноутбуки сотрудников)
        """
        raw_os = (os_name or "").strip()
        h = (hostname or "").upper()
        n = (notes or "").strip()

        is_server = (
            current_asset_type == AssetType.SERVER or
            "SERVER" in raw_os.upper() or
            any(srv_prefix in h for srv_prefix in ["SRV", "DC0", "DC-", "EXCH", "SQL", "PROXMOX", "ESXI"])
        )
        is_laptop = (
            current_asset_type == AssetType.LAPTOP or
            any(nb in h for nb in ["LAPTOP", "NB-", "NB_", "NOTE", "BOOK"]) or
            any(nb in n.lower() for nb in ["ноутбук", "laptop", "notebook"])
        )

        # Проверяем, есть ли явная аппаратная модель в описании (напр. "HP ProDesk 400 G6")
        specific_name = None
        specific_vendor = None
        if n:
            desc_clean = n.replace("AD Description:", "").replace("AD:", "").replace("Собрано из Active Directory:", "").strip()
            for pattern, canonical in KNOWN_VENDORS:
                if re.search(r'\b' + re.escape(pattern) + r'\b', desc_clean.upper()):
                    if len(desc_clean) > 3 and not desc_clean.upper().startswith("ИНВ"):
                        specific_name = desc_clean
                        specific_vendor = canonical
                        break

        if specific_name:
            cat = "server" if is_server else ("laptop" if is_laptop else "workstation")
            return {
                "name": specific_name,
                "vendor": specific_vendor,
                "category": cat
            }

        if is_server:
            return {
                "name": "Серверное оборудование",
                "vendor": "Microsoft / OEM Server",
                "category": "server"
            }
        elif is_laptop:
            return {
                "name": "Ноутбук / Мобильный ПК",
                "vendor": "OEM / Портативный ПК",
                "category": "laptop"
            }
        else:
            return {
                "name": "Рабочая станция / ПК",
                "vendor": "OEM / Корпоративная сборка",
                "category": "workstation"
            }

    @classmethod
    def build_group_ad_analytics(cls, asset_group: List[Asset], category: str) -> Tuple[str, str]:
        """
        Формирует максимально полную аналитическую сводку по пулу компьютеров из Active Directory:
        - Состав редакций ОС и распределение
        - Версии сборок (Builds)
        - Сетевая активность в домене (lastLogon)
        - Размещение по кабинетам и подразделениям
        - Количество закрепленных сотрудников
        """
        from datetime import datetime, timezone
        total = len(asset_group)

        # 1. Подсчет редакций ОС
        editions = Counter()
        for a in asset_group:
            clean_title = cls.clean_os_title(a.os_name)
            editions[clean_title] += 1
        ed_parts = [f"{k} ({v} шт.)" for k, v in editions.most_common(5)]
        ed_line = "💻 Редакции ОС: " + (", ".join(ed_parts) if ed_parts else "Windows")

        # 2. Подсчет номеров сборок
        builds = Counter()
        for a in asset_group:
            raw = a.os_name or ""
            m = re.search(r'\((\d{4,6})\)', raw) or re.search(r'10\.0\.(\d{4,6})', raw)
            if m:
                builds[m.group(1)] += 1
        b_parts = [f"Build {k} ({v} устр.)" for k, v in builds.most_common(4)]
        b_line = ("📦 Сборки: " + ", ".join(b_parts)) if b_parts else ""

        # 3. Активность в домене (lastLogon)
        now = datetime.now(timezone.utc)
        active_30d = 0
        with_logon = 0
        for a in asset_group:
            if a.last_logon:
                with_logon += 1
                try:
                    dt = a.last_logon
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if (now - dt).days <= 30:
                        active_30d += 1
                except Exception:
                    pass

        if with_logon > 0:
            pct = round((active_30d / total) * 100, 1)
            net_line = f"🌐 Сеть: {active_30d} из {total} входили в домен за 30 дн. ({pct}%)"
        else:
            net_line = "🌐 Сеть: Доменный пул Active Directory | Клиенты домена"

        # 4. Кабинеты и размещение
        cab_counts = Counter([a.cabinet for a in asset_group if a.cabinet and a.cabinet != 'Кабинет 101'])
        if not cab_counts:
            cab_counts = Counter([a.cabinet for a in asset_group if a.cabinet])
        top_cabs = [f"{k} ({v})" for k, v in cab_counts.most_common(4)]
        cab_line = ("📍 Размещение: " + ", ".join(top_cabs)) if top_cabs else f"📍 Размещение: {total} рабочих мест организации"

        # 5. Закрепление за пользователями
        users_count = sum(1 for a in asset_group if a.current_user_id or (a.notes and "AD" in a.notes))
        user_line = f"👤 Персонал: закреплено за {users_count} сотрудниками | В эксплуатации: 100%"

        lines = [ed_line]
        if b_line:
            lines.append(b_line)
        lines.append(net_line)
        lines.append(cab_line)
        if users_count > 0:
            lines.append(user_line)

        specs_template = "\n".join(lines)
        notes = (
            f"Автоматически объединено из Active Directory. Пул устройств: {total} шт. "
            f"Охватывает все подразделения и рабочие места."
        )

        return specs_template, notes

    @classmethod
    def sync_models_from_ad_computers(cls, db: Session) -> Dict[str, Any]:
        """
        Формирует укрупненный справочник моделей с максимальной информацией из Active Directory:
        - Удаляет фрагментированные карточки
        - Объединяет компьютеры в укрупненные пулы (Рабочая станция / ПК, Серверное оборудование)
        - Генерирует детальную сводку (редакции ОС, сборки, сетевая активность, кабинеты, пользователи)
        """
        # Удаляем старые фрагментированные карточки
        try:
            db.query(EquipmentModel).filter(
                or_(
                    EquipmentModel.name.ilike("Офисный ПК (%"),
                    EquipmentModel.name.ilike("ПК Рабочая станция (%"),
                    EquipmentModel.name.ilike("Сервер (%"),
                    EquipmentModel.name.ilike("Ноутбук (%")
                )
            ).delete(synchronize_session=False)
            db.commit()
        except Exception as del_err:
            db.rollback()
            logger.warning(f"Error purging old models: {del_err}")

        ad_assets = db.query(Asset).filter(
            or_(
                Asset.ad_guid != None,
                Asset.asset_type.in_([AssetType.WORKSTATION, AssetType.LAPTOP, AssetType.SERVER])
            )
        ).all()

        created_count = 0
        updated_count = 0
        model_candidates: Dict[str, List[Asset]] = {}
        model_meta: Dict[str, Dict[str, Any]] = {}

        for a in ad_assets:
            m_info = cls.determine_computer_model(
                hostname=a.hostname,
                os_name=a.os_name,
                notes=a.notes,
                current_asset_type=a.asset_type
            )
            model_name = m_info["name"]

            # Присваиваем укрупненное наименование в реестре техники
            if a.name != model_name:
                a.name = model_name

            # Актуализируем asset_type
            if m_info["category"] == "server" and a.asset_type != AssetType.SERVER:
                a.asset_type = AssetType.SERVER
            elif m_info["category"] == "laptop" and a.asset_type != AssetType.LAPTOP:
                a.asset_type = AssetType.LAPTOP
            elif m_info["category"] == "workstation" and a.asset_type != AssetType.WORKSTATION:
                a.asset_type = AssetType.WORKSTATION

            if model_name not in model_candidates:
                model_candidates[model_name] = []
                model_meta[model_name] = m_info
            model_candidates[model_name].append(a)

        # Сохраняем объединенные модели с полной аналитикой из AD
        for m_name, asset_group in model_candidates.items():
            meta = model_meta[m_name]
            vendor = meta["vendor"]
            cat = meta["category"]

            # Генерируем максимальную сводку по данным AD
            specs_str, notes_str = cls.build_group_ad_analytics(asset_group, cat)

            existing = db.query(EquipmentModel).filter(EquipmentModel.name.ilike(m_name)).first()
            if existing:
                existing.category = cat
                if vendor:
                    existing.vendor = vendor
                existing.specs_template = specs_str
                existing.notes = notes_str
                updated_count += 1
            else:
                new_m = EquipmentModel(
                    name=m_name,
                    category=cat,
                    vendor=vendor,
                    specs_template=specs_str,
                    notes=notes_str
                )
                db.add(new_m)
                created_count += 1

        db.commit()
        total_models = db.query(EquipmentModel).count()

        return {
            "status": "success",
            "message": f"Сформировано {created_count} укрупненных моделей, обновлено {updated_count}. Всего в справочнике: {total_models} моделей.",
            "created": created_count,
            "updated": updated_count,
            "total_models": total_models
        }
