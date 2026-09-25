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
    def sync_models_from_ad_computers(cls, db: Session) -> Dict[str, Any]:
        """
        Формирует и пополняет справочник моделей на основе полученных данных с компьютеров AD.
        Извлекает уникальные названия моделей, вычисляет средние характеристики и сохраняет.
        """
        ad_assets = db.query(Asset).filter(Asset.ad_guid != None).all()
        if not ad_assets:
            # Если нет прямого ad_guid, возьмем все компьютеры в реестре
            ad_assets = db.query(Asset).filter(
                Asset.asset_type.in_([AssetType.WORKSTATION, AssetType.LAPTOP, AssetType.SERVER])
            ).all()

        created_count = 0
        updated_count = 0

        # Извлекаем модели из названий и заметок
        model_candidates: Dict[str, List[Asset]] = {}

        for a in ad_assets:
            # Проверяем заметки (часто там описание "HP ProDesk 400 G6")
            cand_name = None
            if a.notes and "AD Description:" in a.notes:
                desc = a.notes.replace("AD Description:", "").replace("AD:", "").strip()
                if desc and len(desc) > 3 and not desc.startswith("ИНВ"):
                    cand_name = desc

            if not cand_name:
                # Очищаем имя актива от префиксов "Компьютер "
                name_clean = re.sub(r'^(?:Компьютер|Ноутбук|ПК|Сервер)\s+', '', a.name, flags=re.I).strip()
                # Если имя состоит из шаблона вендор+модель
                if cls.parse_vendor(name_clean):
                    cand_name = name_clean

            if not cand_name and a.hostname:
                # Попробуем разобрать префиксы хоста (напр. HP400-01 -> HP ProDesk 400)
                h = a.hostname.upper()
                if "HP" in h:
                    cand_name = "HP ProDesk Workstation"
                elif "DELL" in h:
                    cand_name = "Dell OptiPlex Workstation"
                elif "LENOVO" in h or "TP" in h:
                    cand_name = "Lenovo ThinkPad Workstation"
                else:
                    cand_name = f"Офисный ПК ({a.os_name or 'Windows'})"

            if cand_name:
                cand_name = cand_name.strip()
                if cand_name not in model_candidates:
                    model_candidates[cand_name] = []
                model_candidates[cand_name].append(a)

        # Для каждого кандидата создаем или обновляем запись в EquipmentModel
        for m_name, asset_group in model_candidates.items():
            parsed = cls.parse_model_details(m_name)
            vendor = parsed["vendor"]
            cat = parsed["category"]

            # Вычисляем типовые характеристики на основе группы компьютеров
            stats = cls.calculate_average_specs(
                db=db,
                category=cat,
                vendor=vendor,
                model_name=m_name
            )

            specs_str = stats.get("specs_template")

            existing = db.query(EquipmentModel).filter(EquipmentModel.name.ilike(m_name)).first()
            if existing:
                if not existing.specs_template or "Windows" not in existing.specs_template:
                    existing.specs_template = specs_str
                    updated_count += 1
            else:
                new_m = EquipmentModel(
                    name=m_name,
                    category=cat,
                    vendor=vendor,
                    specs_template=specs_str,
                    notes=f"Автоматически сформировано из Active Directory (охватывает {len(asset_group)} устройств)"
                )
                db.add(new_m)
                created_count += 1

        db.commit()
        total_models = db.query(EquipmentModel).count()

        return {
            "status": "success",
            "message": f"Сформировано {created_count} новых моделей, обновлено {updated_count}. Всего в справочнике: {total_models} моделей.",
            "created": created_count,
            "updated": updated_count,
            "total_models": total_models
        }
