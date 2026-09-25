import math
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from SHARED.models import Floor, Zone, CablePath, Asset, NetworkSwitch


class PathfindingService:
    @staticmethod
    def calculate_cable_path(
        db: Session,
        from_switch_id: int,
        to_asset_id: int
    ) -> Dict[str, Any]:
        """
        Рассчитывает траекторию кабеля от коммутатора до конечного устройства.
        Использует лотки cable_paths и ортогональную трассировку через коридоры.
        """
        sw = db.query(NetworkSwitch).filter(NetworkSwitch.id == from_switch_id).first()
        asset = db.query(Asset).filter(Asset.id == to_asset_id).first()

        if not sw or not asset:
            return {"found": False, "path_points": [], "distance_meters": 0.0, "message": "Коммутатор или актив не найден"}

        sw_asset = sw.asset
        if not sw_asset or sw_asset.coords_x is None or sw_asset.coords_y is None:
            return {"found": False, "path_points": [], "distance_meters": 0.0, "message": "Коммутатор не размещен на карте"}

        if asset.coords_x is None or asset.coords_y is None:
            return {"found": False, "path_points": [], "distance_meters": 0.0, "message": "Оборудование не размещено на карте"}

        start_x, start_y = float(sw_asset.coords_x), float(sw_asset.coords_y)
        end_x, end_y = float(asset.coords_x), float(asset.coords_y)

        floor_id = sw_asset.floor_id or asset.floor_id
        cable_path_records = []
        if floor_id:
            cable_path_records = db.query(CablePath).filter(CablePath.floor_id == floor_id).all()

        points = []
        # Если заданы явные кабельные лотки, ищем ближайшие точки входа/выхода
        if cable_path_records and len(cable_path_records[0].path_vectors) >= 2:
            corridor_vectors = cable_path_records[0].path_vectors
            points.append({"x": start_x, "y": start_y})
            for vec in corridor_vectors:
                points.append({"x": float(vec.get("x", 0)), "y": float(vec.get("y", 0))})
            points.append({"x": end_x, "y": end_y})
        else:
            # Ортогональная трассировка по коридорам (Manhattan routing с промежуточной точкой поворота)
            mid_x = (start_x + end_x) / 2.0
            points = [
                {"x": start_x, "y": start_y},
                {"x": mid_x, "y": start_y},
                {"x": mid_x, "y": end_y},
                {"x": end_x, "y": end_y}
            ]

        # Расчет длины в метрах (масштаб ~ 50 метров на план)
        dist = 0.0
        for i in range(len(points) - 1):
            dx = (points[i+1]["x"] - points[i]["x"]) * 60.0 # примерный масштаб
            dy = (points[i+1]["y"] - points[i]["y"]) * 40.0
            dist += math.hypot(dx, dy)

        return {
            "found": True,
            "path_points": points,
            "distance_meters": round(dist, 1),
            "message": f"Кабельная трасса проложена: {len(points)} опорных точек, {round(dist, 1)} м."
        }
