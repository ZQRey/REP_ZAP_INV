from SHARED.settings_security import effective_settings, SECRET_SETTINGS
from SHARED.security_config import PRODUCTION
from fastapi import HTTPException
from typing import Dict, Optional
from sqlalchemy.orm import Session
from SHARED.models import SystemSetting
from CARTRIDGE.app.config import DEFAULT_SETTINGS


class SettingsService:
    @staticmethod
    def get_all(db: Session) -> Dict[str, str]:
        """Возвращает все настройки из БД в виде словаря key -> value с учетом дефолтов."""
        records = db.query(SystemSetting).all()
        settings = dict(DEFAULT_SETTINGS)
        for r in records:
            if r.value is not None:
                settings[r.key] = r.value
        return effective_settings(settings)

    @staticmethod
    def get(db: Session, key: str, default: Optional[str] = None) -> Optional[str]:
        """Получить значение одной настройки по ключу."""
        return SettingsService.get_all(db).get(key, default)

    @staticmethod
    def update_bulk(db: Session, updates: Dict[str, Optional[str]]) -> Dict[str, str]:
        """Обновляет набор настроек атомарно и совместимо со старыми LDAP-ключами."""
        updates = dict(updates)
        legacy_filter = updates.pop("ad_filter", None)
        if legacy_filter is not None and "ad_filter_users" not in updates:
            updates["ad_filter_users"] = legacy_filter

        if PRODUCTION and any(k in SECRET_SETTINGS for k in updates):
            raise HTTPException(400, "Integration secrets are managed by environment or secret files")

        dialect = db.get_bind().dialect.name
        for key, val in updates.items():
            values = {"key": key, "value": val}
            if dialect == "postgresql":
                from sqlalchemy.dialects.postgresql import insert
                stmt = insert(SystemSetting).values(**values).on_conflict_do_update(
                    index_elements=[SystemSetting.key],
                    set_={"value": val},
                )
                db.execute(stmt)
            elif dialect == "sqlite":
                from sqlalchemy.dialects.sqlite import insert
                stmt = insert(SystemSetting).values(**values).on_conflict_do_update(
                    index_elements=[SystemSetting.key],
                    set_={"value": val},
                )
                db.execute(stmt)
            else:
                record = db.get(SystemSetting, key)
                if record:
                    record.value = val
                else:
                    db.add(SystemSetting(**values))
        db.commit()
        return SettingsService.get_all(db)

