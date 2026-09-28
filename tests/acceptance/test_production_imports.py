"""Import-level regression checks for modules required by production startup."""


def test_shared_models_import_cleanly():
    import SHARED.models as models
    assert models.Branch.__table__.name == "branches"
    assert hasattr(models.Branch, "batches")


def test_settings_service_imports_cleanly():
    from CARTRIDGE.app.services.settings_service import SettingsService
    assert callable(SettingsService.get_all)


def test_whatsapp_service_imports_cleanly():
    from CARTRIDGE.app.services.whatsapp_service import WhatsAppService
    assert callable(WhatsAppService.clean_phone)


def test_notification_worker_imports_cleanly():
    import SHARED.notification_worker as worker
    assert callable(worker.process_once)


def test_unified_server_imports_without_cartridge_path_shim():
    import sys
    from pathlib import Path
    cartridge_root = str(Path(__file__).resolve().parents[2] / "CARTRIDGE")
    assert cartridge_root not in sys.path
    import main_server
    assert main_server.app.title == "Unified IT Enterprise Platform"


def test_cartridge_auth_imports_by_real_package_name():
    from CARTRIDGE.app.routers.auth_router import login
    from CARTRIDGE.app.services.auth_service import AuthService
    assert callable(login)
    assert callable(AuthService.authenticate_user)
