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
