from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from SHARED.database import get_db
from SHARED.models import RepairBatch, RepairBatchItem, Asset, SystemSetting, Branch

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(prefix="/print", tags=["Repair Print"])

MONTH_NAMES_RU = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря"
]


def format_russian_date(dt) -> str:
    if not dt:
        return ""
    month = MONTH_NAMES_RU[dt.month - 1]
    return f"«{dt.day:02d}» {month} {dt.year} г."


@router.get("/repair-act/{batch_id}", response_class=HTMLResponse)
def print_repair_act(request: Request, batch_id: int, db: Session = Depends(get_db)):
    """Печатная страница А4 для акта передачи техники в сервисный центр."""
    batch = db.query(RepairBatch).options(
        joinedload(RepairBatch.items).joinedload(RepairBatchItem.asset),
        joinedload(RepairBatch.branch)
    ).filter(RepairBatch.id == batch_id).first()

    if not batch:
        raise HTTPException(status_code=404, detail="Акт передачи не найден")

    org_setting = db.query(SystemSetting).filter(SystemSetting.key == "org_name").first()
    org_name = org_setting.value if org_setting and org_setting.value else "ООО «ТехноПром»"

    branch_title = batch.branch.name if batch.branch else "Главный офис"
    it_office = batch.branch.it_office if batch.branch and batch.branch.it_office else "IT-отдел"

    return templates.TemplateResponse(
        request=request,
        name="repair_act_print.html",
        context={
            "batch": batch,
            "org_name": org_name,
            "branch_title": branch_title,
            "it_office": it_office,
            "created_date_ru": format_russian_date(batch.created_at)
        }
    )
