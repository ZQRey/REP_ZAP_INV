import os
import logging
from pathlib import Path

_config_logger = logging.getLogger("SHARED.config")

# Корень проекта (Cartridge_Refilling)
BASE_DIR = Path(__file__).resolve().parent.parent

# Папка базы данных BD/
BD_DIR = BASE_DIR / "BD"
BD_DIR.mkdir(parents=True, exist_ok=True)

# Путь к файлу единой базы данных SQLite по умолчанию
DEFAULT_SQLITE_PATH = BD_DIR / "app_unified.db"

# URL подключения к БД (SQLite локально или PostgreSQL из переменной окружения)
from SHARED.security_config import DATABASE_URL, SECRET_KEY, DEBUG, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

from SHARED.default_settings import DEFAULT_SETTINGS, SETTING_DESCRIPTIONS
