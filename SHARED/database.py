from contextlib import contextmanager
import os
import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger("SHARED.database")

# Поддержка SQLite и PostgreSQL
connect_args = {}
effective_db_url = os.getenv("DATABASE_URL", "").strip()
if not effective_db_url:
    raise RuntimeError("Required configuration missing: DATABASE_URL")

if effective_db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
elif effective_db_url.startswith("postgres://"):
    effective_db_url = effective_db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif effective_db_url.startswith("postgresql://") and not effective_db_url.startswith("postgresql+"):
    # В SQLAlchemy 2.0 схема "postgresql://" по умолчанию ищет драйвер 'psycopg' (psycopg3).
    # Если установлен только psycopg2-binary, автоматически используем postgresql+psycopg2://.
    try:
        import psycopg
    except ImportError:
        effective_db_url = effective_db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = create_engine(effective_db_url, connect_args=connect_args, hide_parameters=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")


@contextmanager
def session_scope():
    """One lifecycle: explicit business commits, rollback on failure, always close."""
    db = SessionLocal()
    try:
        yield db
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def get_db():
    """The single FastAPI dependency; dependency caching shares it within a request."""
    with session_scope() as db:
        yield db


def init_db():
    """
    Проверка версии схемы и инициализация базовых записей (без DDL):
    - Дефолтные системные настройки
    - Главный филиал
    - No implicit administrator provisioning
    - Базовые модели картриджей и техники
    """
    from SHARED import models
    from SHARED.config import DEFAULT_SETTINGS, SETTING_DESCRIPTIONS
    from SHARED.schema_management import require_schema_head
    require_schema_head(engine)

    try:
        with session_scope() as db:
            # 1. Системные настройки
            existing_keys = {s.key for s in db.query(models.SystemSetting.key).all()}
            for key, val in DEFAULT_SETTINGS.items():
                if key not in existing_keys:
                    db.add(
                        models.SystemSetting(
                            key=key,
                            value=val,
                            description=SETTING_DESCRIPTIONS.get(key, "")
                        )
                    )

            # Encrypt LDAP credentials that may have been stored by older releases as plaintext.
            from SHARED.credential_crypto import PREFIX, encrypt_secret
            for secret_key in ("ad_bind_user", "ad_bind_password"):
                secret_setting = db.query(models.SystemSetting).filter(
                    models.SystemSetting.key == secret_key
                ).first()
                if (
                    secret_setting
                    and secret_setting.value
                    and not secret_setting.value.startswith(PREFIX)
                ):
                    secret_setting.value = encrypt_secret(secret_setting.value)

            # Автоматическое обновление устаревших шаблонных значений LDAP до короткого формата
            bind_user_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "ad_bind_user").first()
            if bind_user_setting and bind_user_setting.value == "CN=svc_ldap,OU=Service,DC=company,DC=local":
                bind_user_setting.value = "svc_ldap@gp1.loc"

            base_dn_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "ad_base_dn").first()
            if base_dn_setting and base_dn_setting.value == "DC=company,DC=local":
                base_dn_setting.value = "DC=gp1,DC=loc"

            # 2. Главный филиал по умолчанию
            main_branch = db.query(models.Branch).first()
            if not main_branch:
                main_branch = models.Branch(
                    name="Главный офис",
                    code="HQ",
                    address="Центральный офис",
                    it_office="Кабинет IT № 108",
                    notes="Основной филиал компании"
                )
                db.add(main_branch)
                db.flush()

            # Administrators are provisioned explicitly via SHARED.bootstrap_admin.

            # 4. Базовые популярные модели картриджей (если справочник пуст)
            demo_enabled = os.getenv("DEMO_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
            if demo_enabled and db.query(models.CartridgeModel).count() == 0:
                demo_models = [
                    models.CartridgeModel(name="HP 85A (CE285A)", vendor="HP", resource_pages=1600, compatible_printers="HP LaserJet P1102 / M1132 / M1212nf"),
                    models.CartridgeModel(name="HP 83A (CF283A)", vendor="HP", resource_pages=1500, compatible_printers="HP LaserJet Pro M125 / M127 / M201 / M225"),
                    models.CartridgeModel(name="Canon 725", vendor="Canon", resource_pages=1600, compatible_printers="Canon LBP6000 / MF3010"),
                    models.CartridgeModel(name="Kyocera TK-1170", vendor="Kyocera", resource_pages=7200, compatible_printers="Kyocera ECOSYS M2040dn / M2540dn / M2640idw"),
                    models.CartridgeModel(name="Samsung MLT-D101S", vendor="Samsung", resource_pages=1500, compatible_printers="Samsung ML-2160 / SCX-3400"),
                    models.CartridgeModel(name="Pantum PC-211EV", vendor="Pantum", resource_pages=1600, compatible_printers="Pantum P2207 / P2500 / M6500"),
                ]
                db.add_all(demo_models)

            # 5. Базовые категории моделей техники (если справочник пуст)
            if demo_enabled and db.query(models.EquipmentModel).count() == 0:
                demo_equip_models = [
                    models.EquipmentModel(name="HP ProDesk 400 G6", category="workstation", vendor="HP", specs_template="Core i5, 16GB RAM, 512GB SSD"),
                    models.EquipmentModel(name="Lenovo ThinkCentre M720q", category="workstation", vendor="Lenovo", specs_template="Core i3, 8GB RAM, 256GB SSD"),
                    models.EquipmentModel(name="Dell Latitude 5420", category="laptop", vendor="Dell", specs_template="Core i5-1135G7, 16GB RAM, 512GB SSD, 14\" FHD"),
                    models.EquipmentModel(name="HP LaserJet Pro M428fdn", category="printer", vendor="HP", specs_template="МФУ лазерное, A4, дуплекс, сеть"),
                    models.EquipmentModel(name="Dell P2419H", category="monitor", vendor="Dell", specs_template="23.8\" IPS, Full HD, HDMI/DP/VGA"),
                    models.EquipmentModel(name="APC Smart-UPS 1500VA", category="ups", vendor="APC", specs_template="1500VA / 1000W, LCD, 230V"),
                    models.EquipmentModel(name="Cisco Catalyst 2960X-48TS-L", category="switch", vendor="Cisco", specs_template="48x 1GbE, 4x 1G SFP, LAN Base"),
                ]
                db.add_all(demo_equip_models)

            db.commit()
            logger.info("[DB INIT] Configured database successfully initialized")
    except Exception as e:
        logger.error(f"[DB INIT ERROR] Failed to initialize database: {type(e).__name__}")
        raise

