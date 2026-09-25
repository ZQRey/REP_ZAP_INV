from typing import Optional
from urllib.parse import quote
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from SHARED.database import get_db
from SHARED.models import AppUser, SystemSetting
from SHARED.auth_service import get_current_user, require_role
from REPAIR.app.services.repair_report_service import RepairReportService

router = APIRouter(prefix="/api/v1/repair/reports", tags=["Repair Reports"])


@router.get("/data")
def get_repair_report_json(
    report_type: Optional[str] = Query("general", description="general | condition_repairs"),
    period: Optional[str] = Query("all", description="all | current_year | current_month | custom"),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD для custom периода"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD для custom периода"),
    condition_filter: Optional[str] = Query(None, description="working | broken | all"),
    asset_type_filter: Optional[str] = Query(None),
    repair_count_filter: Optional[str] = Query(None, description="all | has_repairs | frequent | no_repairs"),
    branch_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user)
):
    """
    Получение аналитических данных и сводки по оборудованию в формате JSON.
    Поддерживает периоды (общий, текущий год, текущий месяц, произвольный период)
    и отчет по ремонтам (надёжности оборудования).
    """
    try:
        data = RepairReportService.get_report_data(
            db=db,
            current_user=current_user,
            report_type=report_type or "general",
            period=period or "all",
            start_date=start_date,
            end_date=end_date,
            condition_filter=condition_filter,
            asset_type_filter=asset_type_filter,
            repair_count_filter=repair_count_filter,
            branch_id=branch_id,
            search_query=search
        )
        return {"success": True, "report": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка формирования отчета: {str(e)}")


@router.get("/export/excel")
def export_repair_report_excel(
    report_type: Optional[str] = Query("general"),
    period: Optional[str] = Query("all"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    condition_filter: Optional[str] = Query(None),
    asset_type_filter: Optional[str] = Query(None),
    repair_count_filter: Optional[str] = Query(None),
    branch_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user)
):
    """
    Сформировать и скачать стилизованный отчет по технике и ремонтам в формате Excel (.xlsx).
    """
    try:
        report_data = RepairReportService.get_report_data(
            db=db,
            current_user=current_user,
            report_type=report_type or "general",
            period=period or "all",
            start_date=start_date,
            end_date=end_date,
            condition_filter=condition_filter,
            asset_type_filter=asset_type_filter,
            repair_count_filter=repair_count_filter,
            branch_id=branch_id,
            search_query=search
        )

        org_setting = db.query(SystemSetting).filter(SystemSetting.key == "org_name").first()
        org_name = org_setting.value if org_setting and org_setting.value else "IT Служба Предприятия"

        stream = RepairReportService.generate_excel(report_data=report_data, org_name=org_name)

        now_str = datetime.utcnow().strftime("%Y%m%d_%H%M")
        type_prefix = "Отчет_по_ремонтам" if report_type == "condition_repairs" else "Реестр_техники"
        ascii_prefix = "repairs_report" if report_type == "condition_repairs" else "equipment_report"
        
        raw_filename = f"{type_prefix}_{period}_{now_str}.xlsx"
        ascii_filename = f"{ascii_prefix}_{period}_{now_str}.xlsx"
        encoded_filename = quote(raw_filename)

        headers = {
            "Content-Disposition": f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded_filename}"
        }

        return StreamingResponse(
            stream,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка генерации Excel: {str(e)}")
