import os
from pathlib import Path

# Корень проекта (Cartridge_Refilling)
BASE_DIR = Path(__file__).resolve().parent.parent

# Папка базы данных BD/
BD_DIR = BASE_DIR / "BD"
BD_DIR.mkdir(parents=True, exist_ok=True)

# Путь к файлу единой базы данных SQLite по умолчанию
DEFAULT_SQLITE_PATH = BD_DIR / "app_unified.db"

# URL подключения к БД (SQLite локально или PostgreSQL из переменной окружения)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}")

# Секретный ключ JWT и настройки безопасности
SECRET_KEY = os.getenv("SECRET_KEY", "unified-it-enterprise-secret-key-2026")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "24"))
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

# Глобальные дефолтные системные настройки
DEFAULT_SETTINGS = {
    # Active Directory / LDAP
    "ad_host": "ldap://192.168.1.10:389",
    "ad_base_dn": "DC=company,DC=local",
    "ad_bind_user": "CN=svc_ldap,OU=Service,DC=company,DC=local",
    "ad_bind_password": "",
    "ad_attr_name": "displayName",
    "ad_attr_cabinet": "physicalDeliveryOfficeName",
    "ad_attr_department": "department",
    "ad_attr_phone": "mobile,telephoneNumber",
    "ad_filter_users": "(&(objectCategory=person)(objectClass=user)(!(userAccountControl:1.2.840.113556.1.4.803:=2)))",
    "ad_filter_computers": "(&(objectCategory=computer)(!(userAccountControl:1.2.840.113556.1.4.803:=2)))",
    
    # WhatsApp (Evolution API) — ИСКЛЮЧИТЕЛЬНО для модуля картриджей
    "wa_mode": "shared",
    "wa_api_url": "http://whatsapp-gateway:8080",
    "wa_api_key": "cartridge_secret_key_2026",
    "wa_instance_name": "cartridge_bot",
    "wa_message_template": "Здравствуйте, {name}! Ваш картридж {marker} ({model}) для кабинета {cabinet} успешно заправлен и ожидает выдачи в {it_office}.",
    
    # Организация и реквизиты
    "org_name": "ООО «ТехноПром»",
    "it_office": "Кабинет IT № 108",
    "default_cartridge_vendor": "ООО «СервисПринт»",
    "default_repair_vendor": "ООО «ТехноРемСервис»",
    "cartridge_act_prefix": "АКТ-ЗПР-",
    "repair_act_prefix": "АКТ-РЕМ-",
}

SETTING_DESCRIPTIONS = {
    "ad_host": "LDAP Сервер (IP или доменное имя с протоколом ldap:// или ldaps://)",
    "ad_base_dn": "Базовый DN каталога Active Directory (Base DN)",
    "ad_bind_user": "Учетная запись для подключения к AD (Bind DN или user@domain)",
    "ad_bind_password": "Пароль учетной записи для подключения к LDAP",
    "ad_attr_name": "Атрибут ФИО / имени пользователя в AD",
    "ad_attr_cabinet": "Атрибут номера кабинета в AD",
    "ad_attr_department": "Атрибут подразделения/отдела в AD",
    "ad_attr_phone": "Атрибуты телефона (через запятую)",
    "ad_filter_users": "LDAP-фильтр выборки пользователей",
    "ad_filter_computers": "LDAP-фильтр выборки компьютеров",
    
    "wa_api_url": "URL сервиса Evolution API (шлюз WhatsApp)",
    "wa_api_key": "Глобальный API Key шлюза Evolution API",
    "wa_instance_name": "Имя инстанса WhatsApp в Evolution API",
    "wa_message_template": "Шаблон WhatsApp-сообщения при готовности картриджа к выдаче",
    
    "org_name": "Наименование организации (для актов передачи)",
    "it_office": "Кабинет / Местоположение IT-отдела по умолчанию",
    "default_cartridge_vendor": "Поставщик услуг заправки картриджей по умолчанию",
    "default_repair_vendor": "Сервисный центр по ремонту техники по умолчанию",
    "cartridge_act_prefix": "Префикс номеров актов передачи картриджей",
    "repair_act_prefix": "Префикс номеров актов передачи техники в ремонт",
}
