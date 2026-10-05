from SHARED.policies.static import LocationStaticFiles
from SHARED.auth_service import require_business_auth
from SHARED.schema_management import schema_lifespan
from SHARED.security_config import CORS_ORIGINS
from pathlib import Path
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from LOCATION.app.routers import (
    floors_router,
    zones_router,
    assets_placement_router,
    switches_router,
    pathfinding_router,
    reports_router
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    lifespan=schema_lifespan,
    dependencies=[Depends(require_business_auth)],
    title="NetMap & ITAM API",
    description="Интерактивная 2D-карта сети, трассировка кабелей и IT-активы",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(floors_router.router)
app.include_router(zones_router.router)
app.include_router(assets_placement_router.router)
app.include_router(switches_router.router)
app.include_router(pathfinding_router.router)
app.include_router(reports_router.router)

app.mount("/static", LocationStaticFiles(directory=str(STATIC_DIR)), name="location-static")


@app.get("/health")
def health():
    return {"status": "ok", "service": "location-netmap"}


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


from SHARED.http_security import install as install_http_security
install_http_security(app)
