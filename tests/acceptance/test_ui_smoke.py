"""Release acceptance checks for browser-visible navigation and static assets."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]

PAGES = {
    "/": ROOT / "PORTAL/static/portal.html",
    "/cartridges/": ROOT / "CARTRIDGE/app/static/index.html",
    "/repair/": ROOT / "REPAIR/app/static/index.html",
    "/location/": ROOT / "LOCATION/app/static/index.html",
}


def test_primary_pages_and_local_assets_exist(client):
    for url, path in PAGES.items():
        assert path.exists(), path
        response = client.get(url)
        assert response.status_code == 200, (url, response.status_code)

    for html_path in PAGES.values():
        html = html_path.read_text(encoding="utf-8")
        for src in re.findall(r'(?:src|href)="(/[^"#?]+)', html):
            if src.startswith("/static/"):
                local = ROOT / "PORTAL" / src.removeprefix("/static/")
                assert local.exists(), f"{html_path}: missing {src}"
            elif src.startswith("/cartridges/static/"):
                local = ROOT / "CARTRIDGE/app/static" / src.removeprefix("/cartridges/static/")
                assert local.exists(), f"{html_path}: missing {src}"
            elif src.startswith("/repair/static/"):
                local = ROOT / "REPAIR/app/static" / src.removeprefix("/repair/static/")
                assert local.exists(), f"{html_path}: missing {src}"
            elif src.startswith("/location/static/"):
                local = ROOT / "LOCATION/app/static" / src.removeprefix("/location/static/")
                assert local.exists(), f"{html_path}: missing {src}"


def test_alpine_click_handlers_have_javascript_methods():
    pairs = [
        (ROOT / "PORTAL/static/portal.html", ROOT / "PORTAL/static/portal.js"),
        (ROOT / "CARTRIDGE/app/static/index.html", ROOT / "CARTRIDGE/app/static/js/app.js"),
        (ROOT / "REPAIR/app/static/index.html", ROOT / "REPAIR/app/static/js/repair_app.js"),
        (ROOT / "LOCATION/app/static/index.html", ROOT / "LOCATION/app/static/js/location_canvas.js"),
    ]
    builtins = {"preventDefault", "stopPropagation", "map", "filter", "find", "forEach", "includes", "some", "every"}
    for html_path, js_path in pairs:
        html = html_path.read_text(encoding="utf-8")
        js = js_path.read_text(encoding="utf-8")
        handlers = re.findall(r'@(?:click|submit(?:\.prevent)?|change)="([^"]+)"', html)
        names = set()
        for handler in handlers:
            names.update(re.findall(r'\b([A-Za-z_$][\w$]*)\s*\(', handler))
        missing = sorted(name for name in names if name not in builtins and not re.search(rf'\b{re.escape(name)}\s*\(', js))
        assert not missing, f"{html_path}: handlers without JS methods: {missing}"


def test_health_checks_database(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"
