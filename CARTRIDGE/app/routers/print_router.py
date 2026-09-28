from SHARED.authentication import require_authenticated_user
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from SHARED.database import get_db
from SHARED.models import Batch, BatchItem, Cartridge
from CARTRIDGE.app.services.settings_service import SettingsService

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(prefix="/print", tags=["Print"])


MONTH_NAMES_RU = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря"
]


def format_russian_date(dt) -> str:
    """Форматирует дату в формате '23 сентября 2026 г.'."""
    if not dt:
        return ""
    month = MONTH_NAMES_RU[dt.month - 1]
    return f"«{dt.day:02d}» {month} {dt.year} г."


@router.get("/act/{batch_id}", response_class=HTMLResponse)
def print_act(request: Request, batch_id: int, db: Session = Depends(get_db), current_user=Depends(require_authenticated_user)):
    """Печатная страница А4 для акта передачи картриджей поставщику."""
    batch = db.query(Batch).options(
        joinedload(Batch.items).joinedload(BatchItem.cartridge),
        joinedload(Batch.branch)
    ).filter(Batch.id == batch_id).first()

    if not batch:
        raise HTTPException(status_code=404, detail="Акт не найден.")

    if current_user.role != "superadmin" and (current_user.branch_id is None or batch.branch_id != current_user.branch_id):
        raise HTTPException(status_code=404, detail="Document not found")

    settings = SettingsService.get_all(db)
    org_name = settings.get("org_name", "ООО «ТехноПром»")
    it_office = settings.get("it_office", "Кабинет IT")
    if batch.branch and batch.branch.it_office and batch.branch.it_office.strip():
        it_office = batch.branch.it_office.strip()

    return templates.TemplateResponse(
        request=request,
        name="act_print.html",
        context={
            "batch": batch,
            "org_name": org_name,
            "it_office": it_office,
            "created_date_ru": format_russian_date(batch.created_at)
        }
    )

