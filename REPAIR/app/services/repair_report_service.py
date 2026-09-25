import io
import calendar
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, desc

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from SHARED.models import (
    Asset,
    AssetType,
    AssetStatus,
    AssetCondition,
    Branch,
    ADUser,
    AppUser,
    RepairBatch,
    RepairBatchItem,
    EquipmentHistoryLog
)

ASSET_TYPE_NAMES_RU = {
    AssetType.WORKSTATION: "Компьютер (ПК)",
    AssetType.LAPTOP: "Ноутбук",
    AssetType.MONITOR: "Монитор",
    AssetType.PRINTER: "Принтер / МФУ",
    AssetType.SERVER: "Сервер",
    AssetType.SWITCH: "Коммутатор",
    AssetType.UPS: "ИБП",
    AssetType.OTHER: "Прочее"
}

ASSET_STATUS_NAMES_RU = {
    AssetStatus.AT_WORKPLACE: "На рабочем месте",
    AssetStatus.PENDING_SC: "Принято в IT (Ожидает СЦ)",
    AssetStatus.AT_SC: "В сервисном центре",
    AssetStatus.RETURNED_IT: "Принято из СЦ (Готово к установке)",
    AssetStatus.DECOMMISSIONED: "Списано"
}

CONDITION_NAMES_RU = {
    AssetCondition.WORKING: "В рабочем состоянии",
    AssetCondition.BROKEN: "В нерабочем состоянии"
}

MONTH_NAMES_RU = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
]


class RepairReportService:
    @staticmethod
    def calculate_date_range(
        period: Optional[str] = "all",
        start_date_str: Optional[str] = None,
        end_date_str: Optional[str] = None
    ) -> Tuple[Optional[datetime], Optional[datetime], str]:
        """
        Вычисляет границы диапазона дат (start_dt, end_dt) и текстовую метку периода.
        Поддерживаемые режимы:
        - "all": За всё время
        - "current_year": Текущий календарный год
        - "current_month": Текущий календарный месяц
        - "custom": Пользовательский интервал (start_date_str .. end_date_str)
        """
        now = datetime.utcnow()
        if period == "current_year":
            start_dt = datetime(now.year, 1, 1, 0, 0, 0)
            end_dt = datetime(now.year, 12, 31, 23, 59, 59)
            label = f"Текущий {now.year} год (01.01.{now.year} — {now.strftime('%d.%m.%Y')})"
            return start_dt, end_dt, label

        elif period == "current_month":
            last_day = calendar.monthrange(now.year, now.month)[1]
            m_name = MONTH_NAMES_RU[now.month] if now.month < len(MONTH_NAMES_RU) else ""
            start_dt = datetime(now.year, now.month, 1, 0, 0, 0)
            end_dt = datetime(now.year, now.month, last_day, 23, 59, 59)
            label = f"{m_name} {now.year} (01.{now.month:02d}.{now.year} — {now.strftime('%d.%m.%Y')})"
            return start_dt, end_dt, label

        elif period == "custom" and start_date_str:
            try:
                s_clean = start_date_str.strip()[:10]
                start_dt = datetime.strptime(s_clean, "%Y-%m-%d")
                if end_date_str and end_date_str.strip():
                    e_clean = end_date_str.strip()[:10]
                    end_dt = datetime.strptime(e_clean, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                else:
                    end_dt = datetime(now.year, now.month, now.day, 23, 59, 59)
                label = f"Период с {start_dt.strftime('%d.%m.%Y')} по {end_dt.strftime('%d.%m.%Y')}"
                return start_dt, end_dt, label
            except Exception:
                pass

        return None, None, "За всё время (общий)"

    @staticmethod
    def get_report_data(
        db: Session,
        current_user: Optional[AppUser] = None,
        report_type: str = "general",            # "general" | "condition_repairs"
        period: str = "all",                     # "all" | "current_year" | "current_month" | "custom"
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        condition_filter: Optional[str] = None,  # "working" | "broken" | None
        asset_type_filter: Optional[str] = None,
        repair_count_filter: Optional[str] = None, # "all" | "has_repairs" | "frequent" | "no_repairs"
        branch_id: Optional[int] = None,
        search_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Формирует расширенный аналитический отчет:
        1. Отчёт общий / за период (реестр оборудования и состояние)
        2. Отчёт об состоянии техники (количество отправок на ремонт, затраты в тенге ₸, надёжность)
        """
        start_dt, end_dt, period_label = RepairReportService.calculate_date_range(
            period=period,
            start_date_str=start_date,
            end_date_str=end_date
        )

        query = db.query(Asset).options(
            joinedload(Asset.branch),
            joinedload(Asset.responsible_ad_user)
        )

        # Филиальное разграничение
        effective_branch_id = branch_id
        if current_user and current_user.role not in ("superadmin", None) and current_user.branch_id:
            effective_branch_id = current_user.branch_id
            query = query.filter(Asset.branch_id == effective_branch_id)
        elif effective_branch_id:
            query = query.filter(Asset.branch_id == effective_branch_id)

        # Фильтр по техническому состоянию (Рабочее / Сломанное)
        if condition_filter:
            if condition_filter.lower() in ("working", "rabochee"):
                query = query.filter(Asset.condition == AssetCondition.WORKING)
            elif condition_filter.lower() in ("broken", "slomannoe"):
                query = query.filter(Asset.condition == AssetCondition.BROKEN)

        # Фильтр по категории оборудования
        if asset_type_filter:
            try:
                a_type = AssetType(asset_type_filter)
                query = query.filter(Asset.asset_type == a_type)
            except Exception:
                pass

        # Поиск по тексту
        if search_query and search_query.strip():
            sq = f"%{search_query.strip()}%"
            query = query.filter(
                or_(
                    Asset.inventory_number.ilike(sq),
                    Asset.serial_number.ilike(sq),
                    Asset.name.ilike(sq),
                    Asset.hostname.ilike(sq),
                    Asset.cabinet.ilike(sq)
                )
            )

        assets = query.order_by(Asset.inventory_number).all()

        # Предзагрузка истории ремонтов для оптимизации
        asset_ids = [a.id for a in assets]
        all_repair_items = (
            db.query(RepairBatchItem)
            .options(joinedload(RepairBatchItem.batch))
            .filter(RepairBatchItem.asset_id.in_(asset_ids))
            .all()
            if asset_ids else []
        )
        
        # Группировка позиций ремонта по asset_id
        repairs_by_asset: Dict[int, List[RepairBatchItem]] = {}
        for r_item in all_repair_items:
            repairs_by_asset.setdefault(r_item.asset_id, []).append(r_item)

        # Предзагрузка записей истории передач в СЦ (для обратной совместимости)
        sc_history_logs = (
            db.query(EquipmentHistoryLog)
            .filter(
                EquipmentHistoryLog.asset_id.in_(asset_ids),
                EquipmentHistoryLog.action.in_([
                    "Передача в сервисный центр",
                    "Приемка в IT-отдел",
                    "Приемка неисправной техники в IT-отдел"
                ])
            )
            .all()
            if asset_ids else []
        )
        logs_by_asset: Dict[int, List[EquipmentHistoryLog]] = {}
        for l in sc_history_logs:
            logs_by_asset.setdefault(l.asset_id, []).append(l)

        items = []
        for a in assets:
            user_str = "—"
            if a.responsible_ad_user:
                user_str = a.responsible_ad_user.display_name
            elif a.current_user_id:
                user_str = a.current_user_id

            a_repairs = repairs_by_asset.get(a.id, [])
            a_logs = logs_by_asset.get(a.id, [])

            # Разделение по периоду:
            # Считаем событие входящим в период, если дата акта или возврата попадает в [start_dt, end_dt]
            def is_in_period(dt: Optional[datetime]) -> bool:
                if not start_dt:
                    return True
                if not dt:
                    return False
                return start_dt <= dt <= end_dt

            period_repairs = []
            for r in a_repairs:
                r_date = r.batch.created_at if (r.batch and r.batch.created_at) else r.returned_at
                if is_in_period(r_date):
                    period_repairs.append(r)

            period_logs = [l for l in a_logs if is_in_period(l.timestamp)]

            # Количество ремонтов: максимум между элементами актов и журналом
            repairs_count_all = max(len(a_repairs), len(a_logs))
            repairs_count_period = max(len(period_repairs), len(period_logs))

            # Стоимость ремонтов
            cost_all = sum(float(r.cost or 0.0) for r in a_repairs)
            cost_period = sum(float(r.cost or 0.0) for r in period_repairs)

            # Последний ремонт
            last_date_str = "—"
            last_issue_str = "—"
            last_vendor_str = "—"

            if a_repairs:
                # Сортируем от самых свежих к старым
                sorted_repairs = sorted(
                    a_repairs,
                    key=lambda r: (r.batch.created_at if r.batch and r.batch.created_at else datetime.min),
                    reverse=True
                )
                latest = sorted_repairs[0]
                if latest.batch and latest.batch.created_at:
                    last_date_str = latest.batch.created_at.strftime("%d.%m.%Y")
                elif latest.returned_at:
                    last_date_str = latest.returned_at.strftime("%d.%m.%Y")
                last_issue_str = latest.reported_issue or latest.diagnostic_result or "—"
                if latest.batch and latest.batch.vendor_name:
                    last_vendor_str = latest.batch.vendor_name
            elif a_logs:
                sorted_logs = sorted(a_logs, key=lambda l: l.timestamp or datetime.min, reverse=True)
                latest_log = sorted_logs[0]
                if latest_log.timestamp:
                    last_date_str = latest_log.timestamp.strftime("%d.%m.%Y")
                last_issue_str = latest_log.details or latest_log.action

            # Детальная история ремонтов для карточки
            history_summary = []
            for r in a_repairs:
                b_date = r.batch.created_at.strftime("%d.%m.%Y") if (r.batch and r.batch.created_at) else "—"
                history_summary.append({
                    "id": r.id,
                    "date": b_date,
                    "act_number": r.batch.act_number if r.batch else "—",
                    "vendor": r.batch.vendor_name if r.batch else "—",
                    "issue": r.reported_issue or "—",
                    "diagnostic": r.diagnostic_result or "—",
                    "work": r.work_performed or "—",
                    "cost": float(r.cost or 0.0),
                    "cost_formatted": f"{float(r.cost or 0.0):,.0f}".replace(",", " ") + " ₸" if r.cost else "0 ₸",
                    "status": r.status
                })

            item_data = {
                "id": a.id,
                "inventory_number": a.inventory_number,
                "serial_number": a.serial_number or "—",
                "name": a.name,
                "asset_type": a.asset_type.value if hasattr(a.asset_type, "value") else str(a.asset_type),
                "asset_type_label": ASSET_TYPE_NAMES_RU.get(a.asset_type, str(a.asset_type)),
                "condition": a.condition.value if hasattr(a.condition, "value") else str(a.condition),
                "condition_label": CONDITION_NAMES_RU.get(a.condition, "В рабочем состоянии" if a.condition == AssetCondition.WORKING else "В нерабочем состоянии"),
                "status": a.status.value if hasattr(a.status, "value") else str(a.status),
                "status_label": ASSET_STATUS_NAMES_RU.get(a.status, str(a.status)),
                "branch_name": a.branch.name if a.branch else "Все филиалы",
                "cabinet": a.cabinet or "—",
                "user_name": user_str,
                "hostname": a.hostname or "—",
                "os_name": a.os_name or "—",
                "notes": a.notes or "",
                "updated_at": a.updated_at.strftime("%d.%m.%Y %H:%M") if a.updated_at else "—",

                # Метрики ремонтов
                "repairs_count": repairs_count_period if period != "all" else repairs_count_all,
                "repairs_count_period": repairs_count_period,
                "repairs_count_all": repairs_count_all,
                "repairs_cost": cost_period if period != "all" else cost_all,
                "repairs_cost_formatted": f"{cost_period:,.0f}".replace(",", " ") + " ₸" if cost_period > 0 else "0 ₸",
                "repairs_cost_all": cost_all,
                "repairs_cost_all_formatted": f"{cost_all:,.0f}".replace(",", " ") + " ₸" if cost_all > 0 else "0 ₸",
                "last_repair_date": last_date_str,
                "last_repair_issue": last_issue_str,
                "last_vendor_name": last_vendor_str,
                "repair_history": history_summary
            }

            # Фильтр по количеству ремонтов (в режиме отчета надёжности)
            if repair_count_filter:
                r_cnt = item_data["repairs_count"]
                if repair_count_filter == "has_repairs" and r_cnt == 0:
                    continue
                elif repair_count_filter == "frequent" and r_cnt < 2:
                    continue
                elif repair_count_filter == "no_repairs" and r_cnt > 0:
                    continue

            items.append(item_data)

        # Сводные показатели KPI
        total_repairs_period = sum(i["repairs_count_period"] for i in items)
        total_repairs_all = sum(i["repairs_count_all"] for i in items)
        total_cost_period = sum(i["repairs_cost"] for i in items)
        total_cost_all = sum(i["repairs_cost_all"] for i in items)

        summary = {
            "total_count": len(items),
            "working_count": sum(1 for i in items if i["condition"] == "working"),
            "broken_count": sum(1 for i in items if i["condition"] == "broken"),
            "at_workplace": sum(1 for i in items if i["status"] == "at_workplace"),
            "pending_sc": sum(1 for i in items if i["status"] == "pending_sc"),
            "at_sc": sum(1 for i in items if i["status"] == "at_sc"),
            "returned_it": sum(1 for i in items if i["status"] == "returned_it"),

            # Метрики ремонтов
            "total_repairs": total_repairs_period if period != "all" else total_repairs_all,
            "total_repairs_period": total_repairs_period,
            "total_repairs_all": total_repairs_all,
            "total_repair_cost": total_cost_period if period != "all" else total_cost_all,
            "total_repair_cost_formatted": f"{(total_cost_period if period != 'all' else total_cost_all):,.0f}".replace(",", " ") + " ₸",
            "total_cost_all": total_cost_all,
            "total_cost_all_formatted": f"{total_cost_all:,.0f}".replace(",", " ") + " ₸",
            "assets_with_repairs": sum(1 for i in items if i["repairs_count"] > 0),
            "frequent_repair_count": sum(1 for i in items if i["repairs_count"] >= 2),
            "never_repaired_count": sum(1 for i in items if i["repairs_count"] == 0),

            # Категории
            "workstations": sum(1 for i in items if i["asset_type"] in ("workstation", "laptop", "server")),
            "monitors": sum(1 for i in items if i["asset_type"] == "monitor"),
            "printers": sum(1 for i in items if i["asset_type"] == "printer"),
            "ups_count": sum(1 for i in items if i["asset_type"] == "ups"),
            "other_count": sum(1 for i in items if i["asset_type"] in ("switch", "other"))
        }

        branch_obj = db.query(Branch).filter(Branch.id == effective_branch_id).first() if effective_branch_id else None
        branch_title = branch_obj.name if branch_obj else "Все филиалы"

        report_title = "Отчёт об исправности и ремонтах техники" if report_type == "condition_repairs" else "Реестр и состояние компьютерной техники"

        return {
            "title": report_title,
            "report_type": report_type,
            "period": period,
            "period_label": period_label,
            "start_date": start_dt.strftime("%Y-%m-%d") if start_dt else None,
            "end_date": end_dt.strftime("%Y-%m-%d") if end_dt else None,
            "branch_name": branch_title,
            "condition_filter": condition_filter or "all",
            "repair_count_filter": repair_count_filter or "all",
            "generated_at": datetime.utcnow().strftime("%d.%m.%Y %H:%M"),
            "generated_by": current_user.full_name if current_user else "Система",
            "summary": summary,
            "items": items
        }

    @staticmethod
    def generate_excel(report_data: Dict[str, Any], org_name: str = "IT Отдел") -> io.BytesIO:
        """
        Генерирует стильный профессиональный файл Excel (.xlsx) с таблицей данных и сводкой.
        Поддерживает как общий отчет, так и отчет по ремонтам (надёжности техники).
        """
        wb = Workbook()
        ws = wb.active
        report_type = report_data.get("report_type", "general")
        ws.title = "Анализ ремонтов" if report_type == "condition_repairs" else "Реестр техники"
        ws.views.sheetView[0].showGridLines = True

        # Стили оформления
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")  # Dark slate
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

        green_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
        green_font = Font(name="Calibri", size=10, bold=True, color="166534")

        red_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
        red_font = Font(name="Calibri", size=10, bold=True, color="991B1B")

        amber_fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
        amber_font = Font(name="Calibri", size=10, bold=True, color="B45309")

        thin_side = Side(border_style="thin", color="CBD5E1")
        card_border = Border(top=thin_side, left=thin_side, right=thin_side, bottom=thin_side)
        row_border = Border(top=thin_side, left=thin_side, right=thin_side, bottom=thin_side)

        # 1. Шапка документа
        title_str = report_data.get("title", "Отчет по технике")
        ws["A1"] = f"{org_name} — {title_str}"
        ws["A1"].font = Font(name="Calibri", size=15, bold=True, color="0F172A")
        ws.row_dimensions[1].height = 24

        period_str = report_data.get("period_label", "За всё время")
        ws["A2"] = f"Филиал: {report_data.get('branch_name')} | Период: {period_str} | Сформирован: {report_data.get('generated_at')} | Составитель: {report_data.get('generated_by')}"
        ws["A2"].font = Font(name="Calibri", size=10, italic=True, color="475569")
        ws.row_dimensions[2].height = 18

        # 2. Карточки сводки (KPI) в строках 4..5
        summary = report_data.get("summary", {})

        if report_type == "condition_repairs":
            cards = [
                ("Всего единиц", summary.get("total_count", 0), "F1F5F9", "0F172A"),
                ("В рабочем состоянии", summary.get("working_count", 0), "DCFCE7", "166534"),
                ("В нерабочем состоянии", summary.get("broken_count", 0), "FEE2E2", "991B1B"),
                ("Отправок в ремонт (период)", summary.get("total_repairs", 0), "FEF3C7", "B45309"),
                ("Затраты на ремонт (₸)", summary.get("total_repair_cost_formatted", "0 ₸"), "EDE9FE", "6D28D9"),
                ("Частые ремонты (2+)", summary.get("frequent_repair_count", 0), "FFE4E6", "BE123C"),
            ]
        else:
            cards = [
                ("Всего единиц", summary.get("total_count", 0), "F1F5F9", "0F172A"),
                ("В рабочем состоянии", summary.get("working_count", 0), "DCFCE7", "166534"),
                ("В нерабочем состоянии", summary.get("broken_count", 0), "FEE2E2", "991B1B"),
                ("На рабочем месте", summary.get("at_workplace", 0), "E0F2FE", "0369A1"),
                ("В ремонте (СЦ / IT)", summary.get("pending_sc", 0) + summary.get("at_sc", 0), "FEF3C7", "B45309"),
                ("Готово к установке", summary.get("returned_it", 0), "F3E8FF", "7E22CE"),
            ]

        col_idx = 1
        for title, val, bg_hex, fg_hex in cards:
            c1 = ws.cell(row=4, column=col_idx, value=title)
            c1.font = Font(name="Calibri", size=9, bold=True, color="64748B")
            c1.alignment = Alignment(horizontal="center", vertical="center")
            c1.fill = PatternFill(start_color=bg_hex, end_color=bg_hex, fill_type="solid")
            c1.border = card_border

            c2 = ws.cell(row=5, column=col_idx, value=val)
            c2.font = Font(name="Calibri", size=14, bold=True, color=fg_hex)
            c2.alignment = Alignment(horizontal="center", vertical="center")
            c2.fill = PatternFill(start_color=bg_hex, end_color=bg_hex, fill_type="solid")
            c2.border = card_border

            col_idx += 1

        ws.row_dimensions[4].height = 18
        ws.row_dimensions[5].height = 28

        # 3. Заголовки таблицы данных
        if report_type == "condition_repairs":
            headers = [
                "№",
                "Инвентарный №",
                "Серийный №",
                "Наименование / Модель",
                "Категория",
                "Состояние",
                "Текущий статус",
                "Отправок в ремонт",
                "Затраты на ремонт (₸)",
                "Последняя неисправность / Причина",
                "Сервисный центр",
                "Дата последнего ремонта",
                "Филиал",
                "Кабинет",
                "Ответственный"
            ]
        else:
            headers = [
                "№",
                "Инвентарный №",
                "Серийный №",
                "Наименование / Модель",
                "Категория",
                "Состояние техники",
                "Статус",
                "Отправок в ремонт",
                "Филиал",
                "Кабинет",
                "Ответственный",
                "Имя ПК / AD",
                "Операционная система",
                "Примечание"
            ]

        start_row = 7
        ws.row_dimensions[start_row].height = 24
        for col_num, h_title in enumerate(headers, 1):
            cell = ws.cell(row=start_row, column=col_num, value=h_title)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = row_border

        # 4. Строки данных
        current_row = start_row + 1
        zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

        for idx, item in enumerate(report_data.get("items", []), 1):
            ws.row_dimensions[current_row].height = 20
            is_zebra = (idx % 2 == 0)
            cond_is_working = (item.get("condition") == "working")

            if report_type == "condition_repairs":
                row_values = [
                    idx,
                    item.get("inventory_number"),
                    item.get("serial_number"),
                    item.get("name"),
                    item.get("asset_type_label"),
                    item.get("condition_label"),
                    item.get("status_label"),
                    item.get("repairs_count", 0),
                    item.get("repairs_cost_formatted", "0 ₸"),
                    item.get("last_repair_issue", "—"),
                    item.get("last_vendor_name", "—"),
                    item.get("last_repair_date", "—"),
                    item.get("branch_name"),
                    item.get("cabinet"),
                    item.get("user_name")
                ]
            else:
                row_values = [
                    idx,
                    item.get("inventory_number"),
                    item.get("serial_number"),
                    item.get("name"),
                    item.get("asset_type_label"),
                    item.get("condition_label"),
                    item.get("status_label"),
                    item.get("repairs_count", 0),
                    item.get("branch_name"),
                    item.get("cabinet"),
                    item.get("user_name"),
                    item.get("hostname"),
                    item.get("os_name"),
                    item.get("notes")
                ]

            for c_idx, val in enumerate(row_values, 1):
                cell = ws.cell(row=current_row, column=c_idx, value=val)
                cell.border = row_border
                cell.font = Font(name="Calibri", size=10)

                # Выделение состояния техники
                if c_idx == 6:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                    if cond_is_working:
                        cell.fill = green_fill
                        cell.font = green_font
                    else:
                        cell.fill = red_fill
                        cell.font = red_font
                # Выделение отправок в ремонт
                elif report_type == "condition_repairs" and c_idx == 8:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                    cnt = item.get("repairs_count", 0)
                    if cnt >= 2:
                        cell.fill = red_fill
                        cell.font = red_font
                    elif cnt == 1:
                        cell.fill = amber_fill
                        cell.font = amber_font
                    elif is_zebra:
                        cell.fill = zebra_fill
                elif c_idx in (1, 2, 5, 7, 8, 12, 14):
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                    if is_zebra:
                        cell.fill = zebra_fill
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")
                    if is_zebra:
                        cell.fill = zebra_fill

            current_row += 1

        # Автоподбор ширины колонок
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                if cell.row < start_row:
                    continue
                v_str = str(cell.value or "")
                if len(v_str) > max_len:
                    max_len = len(v_str)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

        # Индивидуальная настройка ключевых колонок
        ws.column_dimensions["A"].width = 6   # №
        ws.column_dimensions["B"].width = 18  # Инв №
        ws.column_dimensions["D"].width = 28  # Модель
        ws.column_dimensions["F"].width = 22  # Состояние

        if report_type == "condition_repairs":
            ws.column_dimensions["H"].width = 18  # Отправок в ремонт
            ws.column_dimensions["I"].width = 20  # Затраты (₸)
            ws.column_dimensions["J"].width = 32  # Последняя неисправность
            ws.column_dimensions["K"].width = 22  # СЦ
            ws.column_dimensions["L"].width = 16  # Дата ремонта

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output
