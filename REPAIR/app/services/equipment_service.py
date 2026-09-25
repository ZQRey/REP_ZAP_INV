from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from SHARED.models import (
    Asset,
    AssetType,
    AssetStatus,
    AssetCondition,
    RepairBatch,
    RepairBatchItem,
    EquipmentHistoryLog,
    SystemSetting,
    Branch,
    ADUser
)


class EquipmentService:
    @staticmethod
    def generate_act_number(db: Session) -> str:
        """Генерирует следующий номер акта передачи в СЦ: АКТ-РЕМ-2026-0001."""
        prefix_setting = db.query(SystemSetting).filter(SystemSetting.key == "repair_act_prefix").first()
        prefix = prefix_setting.value if prefix_setting and prefix_setting.value else "АКТ-РЕМ-"
        
        year_str = datetime.utcnow().strftime("%Y")
        pattern = f"{prefix}{year_str}-%"
        
        last_batch = db.query(RepairBatch).filter(
            RepairBatch.act_number.like(pattern)
        ).order_by(desc(RepairBatch.id)).first()

        next_seq = 1
        if last_batch and last_batch.act_number:
            try:
                parts = last_batch.act_number.split("-")
                last_num_str = parts[-1]
                next_seq = int(last_num_str) + 1
            except Exception:
                next_seq = db.query(RepairBatch).count() + 1

        return f"{prefix}{year_str}-{next_seq:04d}"

    @staticmethod
    def log_history(
        db: Session,
        asset_id: int,
        action: str,
        user_name: Optional[str] = None,
        details: Optional[str] = None
    ) -> EquipmentHistoryLog:
        """Создает запись в журнале истории оборудования."""
        log = EquipmentHistoryLog(
            asset_id=asset_id,
            action=action,
            user_name=user_name,
            details=details,
            timestamp=datetime.utcnow()
        )
        db.add(log)
        return log

    @staticmethod
    def accept_equipment(
        db: Session,
        inventory_number: str,
        name: str,
        asset_type: AssetType,
        cabinet: str,
        branch_id: Optional[int],
        current_user_id: Optional[str],
        serial_number: Optional[str] = None,
        reported_issue: str = "Неисправность",
        condition: AssetCondition = AssetCondition.BROKEN,
        notes: Optional[str] = None,
        operator_name: Optional[str] = "Оператор IT"
    ) -> Asset:
        """
        ЭТАП 1: Приемка оборудования в IT-отделе.
        Оборудование переходит в статус pending_sc (Ожидает СЦ) и condition (В нерабочем состоянии).
        """
        inv = inventory_number.strip()
        asset = db.query(Asset).filter(Asset.inventory_number.ilike(inv)).first()
        now = datetime.utcnow()

        user_display = "Не указан"
        if current_user_id:
            ad_user = db.query(ADUser).filter(ADUser.samaccountname == current_user_id).first()
            if ad_user:
                user_display = f"{ad_user.display_name} ({ad_user.samaccountname})"

        if not asset:
            # Создаем новую единицу техники
            asset = Asset(
                inventory_number=inv,
                serial_number=serial_number.strip() if serial_number else None,
                name=name.strip(),
                asset_type=asset_type,
                status=AssetStatus.PENDING_SC,
                condition=condition,
                cabinet=cabinet.strip(),
                branch_id=branch_id,
                current_user_id=current_user_id,
                notes=notes,
                created_at=now,
                updated_at=now
            )
            db.add(asset)
            db.flush()
            EquipmentService.log_history(
                db=db,
                asset_id=asset.id,
                action="Приемка в IT-отдел (Первичная)",
                user_name=operator_name,
                details=f"Принято от сотрудника: {user_display}. Заявленная неисправность: {reported_issue}. Кабинет: {cabinet}."
            )
        else:
            # Обновляем существующую технику
            asset.status = AssetStatus.PENDING_SC
            asset.condition = condition
            asset.name = name.strip()
            if serial_number:
                asset.serial_number = serial_number.strip()
            if cabinet:
                asset.cabinet = cabinet.strip()
            if branch_id is not None:
                asset.branch_id = branch_id
            if current_user_id:
                asset.current_user_id = current_user_id
            if notes:
                asset.notes = notes
            asset.updated_at = now

            EquipmentService.log_history(
                db=db,
                asset_id=asset.id,
                action="Приемка в IT-отдел",
                user_name=operator_name,
                details=f"Принято в ремонт от: {user_display}. Неисправность: {reported_issue}. Кабинет: {cabinet}."
            )

        db.commit()
        db.refresh(asset)
        return asset
