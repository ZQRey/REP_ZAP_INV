from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTENDS = [
    ROOT / "PORTAL/static/portal.js",
    ROOT / "CARTRIDGE/app/static/js/app.js",
    ROOT / "REPAIR/app/static/js/repair_app.js",
    ROOT / "LOCATION/app/static/js/location_canvas.js",
]
HTML = [
    ROOT / "PORTAL/static/portal.html",
    ROOT / "CARTRIDGE/app/static/index.html",
    ROOT / "REPAIR/app/static/index.html",
    ROOT / "LOCATION/app/static/index.html",
]


def test_all_frontends_load_shared_api_client():
    for path in HTML:
        assert '/static/api-client.js' in path.read_text(encoding='utf-8'), path


def test_frontend_does_not_persist_auth_token_in_local_storage():
    for path in FRONTENDS:
        source = path.read_text(encoding='utf-8')
        assert "localStorage.setItem('token'" not in source
        assert 'localStorage.setItem("token"' not in source


def test_frontend_does_not_put_bearer_token_in_urls():
    for path in FRONTENDS:
        source = path.read_text(encoding='utf-8')
        assert '?token=' not in source
        assert '&token=' not in source


def test_api_client_uses_session_storage_and_handles_core_statuses():
    source = (ROOT / "PORTAL/static/api-client.js").read_text(encoding='utf-8')
    assert "sessionStorage.getItem('token')" in source
    assert "sessionStorage.removeItem('token')" in source
    for status in (401, 403, 404, 409, 422, 429, 500):
        assert f"{status}:" in source or f"status === {status}" in source
