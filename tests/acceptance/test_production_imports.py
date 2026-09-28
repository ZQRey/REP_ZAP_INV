"""Import-level regression checks for modules required by production startup."""


def test_shared_models_import_cleanly():
    import SHARED.models as models
    assert models.Branch.__table__.name == "branches"
    assert hasattr(models.Branch, "batches")


def test_notification_worker_imports_cleanly():
    import SHARED.notification_worker as worker
    assert callable(worker.process_once)
