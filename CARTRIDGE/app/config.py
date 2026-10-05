import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Compatibility constant; database URL and path are owned by SHARED.
from SHARED.config import DEFAULT_SQLITE_PATH

from SHARED.security_config import DATABASE_URL, SECRET_KEY, DEBUG, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

from SHARED.config import DEFAULT_SETTINGS as SHARED_DEFAULT_SETTINGS, SETTING_DESCRIPTIONS as SHARED_SETTING_DESCRIPTIONS

DEFAULT_SETTINGS = dict(SHARED_DEFAULT_SETTINGS)
DEFAULT_SETTINGS.update({
    # Backward-compatible cartridge aliases still used by legacy report/batch code.
    "default_vendor": SHARED_DEFAULT_SETTINGS["default_cartridge_vendor"],
    "act_prefix": SHARED_DEFAULT_SETTINGS["cartridge_act_prefix"],

    # WhatsApp (Evolution API)
    "wa_mode": "shared",  # "shared" | "individual"
    "wa_api_url": "http://whatsapp-gateway:8080",
    "wa_api_key": "",
    "wa_instance_name": "cartridge_bot",
    "wa_message_template": "Здравствуйте, {name}! Ваш картридж {marker} ({model}) для кабинета {cabinet} успешно заправлен и ожидает выдачи в {it_office}.",
    
    # General / Org details
    "org_name": "ООО «ТехноПром»",
    "it_office": "Кабинет IT № 108",
    "default_vendor": "ООО «СервисПринт»",
    "act_prefix": SHARED_DEFAULT_SETTINGS["cartridge_act_prefix"],
})

SETTING_DESCRIPTIONS = dict(SHARED_SETTING_DESCRIPTIONS)
SETTING_DESCRIPTIONS.update({
    "wa_api_url": "URL сервиса Evolution API (локальный шлюз)",
    "wa_api_key": "Глобальный API Key шлюза Evolution API",
    "wa_instance_name": "Имя инстанса WhatsApp в Evolution API",
    "wa_message_template": "Шаблон WhatsApp-сообщения при готовности к выдаче",
    
    "org_name": "Наименование организации (для шапки акта передачи)",
    "it_office": "Кабинет / Местоположение IT-отдела для получения картриджей",
    "default_vendor": "Поставщик услуг заправки по умолчанию (сервисный центр)",
    "act_prefix": "Префикс номеров актов передачи",
})

