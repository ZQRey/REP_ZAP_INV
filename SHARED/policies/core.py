import ipaddress
from dataclasses import dataclass
from fastapi import HTTPException
from sqlalchemy import select, or_, and_, false, func, inspect
from SHARED import models as m

ROLES = frozenset({"superadmin", "admin", "technician", "operator", "viewer", "user"})
LOWER_ROLES = frozenset({"technician", "operator", "viewer", "user"})


@dataclass(frozen=True)
class Principal:
    id: int
    username: str
    role: str
    branch_id: int | None

    @classmethod
    def from_user(cls, user):
        if not user.is_active or user.role not in ROLES:
            raise HTTPException(403, "Account has no authorized role")
        return cls(user.id, user.username, user.role, user.branch_id)


def require_branch_access(principal, branch_id):
    if principal.role != "superadmin" and (principal.branch_id is None or branch_id != principal.branch_id):
        raise HTTPException(403, "Branch access denied")
    return branch_id


DIRECT = {m.AppUser, m.Cartridge, m.Batch, m.Asset, m.RepairBatch, m.Floor, m.SparePartsWarehouse, m.Notification}
GLOBAL = {m.SystemSetting, m.ADUser, m.CartridgeModel, m.EquipmentModel, m.AuditLog, m.DocumentCounter}
PARENTS = {m.Zone: ("floor_id", m.Floor), m.CablePath: ("floor_id", m.Floor),
           m.NetworkSwitch: ("asset_id", m.Asset), m.SwitchPort: ("switch_id", m.NetworkSwitch),
           m.HistoryLog: ("cartridge_id", m.Cartridge), m.EquipmentHistoryLog: ("asset_id", m.Asset),
           m.BatchItem: ("batch_id", m.Batch), m.RepairBatchItem: ("batch_id", m.RepairBatch),
           m.RepairPartUsed: ("repair_item_id", m.RepairBatchItem)}
SCOPED = DIRECT | set(PARENTS) | {m.Branch}


def scope_criteria(principal, branch_id):
    """Core subqueries avoid recursive ORM options; all aliases/loaders get the same scope."""
    if principal.role == "superadmin" and branch_id is None:
        return {}
    if branch_id is None:
        return {model: false() for model in SCOPED | {m.AuditLog}}
    tables = {model: model.__table__ for model in SCOPED}
    criteria = {model: model.branch_id == branch_id for model in DIRECT}
    criteria[m.Branch] = m.Branch.id == branch_id
    if principal.role == "user":
        for model in (m.Asset, m.Cartridge):
            criteria[model] = and_(criteria[model], func.lower(model.current_user_id) == principal.username.lower())
    if principal.role != "superadmin":
        criteria[m.AppUser] = and_(criteria[m.AppUser], m.AppUser.role != "superadmin")
        if principal.role != "admin":
            criteria[m.AppUser] = m.AppUser.id == principal.id
    ids = {model: select(tables[model].c.id).where(expr) for model, expr in criteria.items()}
    # Dependency order is fixed: location parents, assets, then network and history.
    for model in (m.Zone, m.CablePath):
        field, parent = PARENTS[model]
        criteria[model] = getattr(model, field).in_(ids[parent])
        ids[model] = select(tables[model].c.id).where(criteria[model])
    criteria[m.Asset] = and_(criteria[m.Asset],
        or_(m.Asset.floor_id.is_(None), m.Asset.floor_id.in_(ids[m.Floor])),
        or_(m.Asset.zone_id.is_(None), m.Asset.zone_id.in_(ids[m.Zone])))
    ids[m.Asset] = select(tables[m.Asset].c.id).where(criteria[m.Asset])
    for model in (m.NetworkSwitch, m.SwitchPort, m.HistoryLog, m.EquipmentHistoryLog, m.BatchItem, m.RepairBatchItem, m.RepairPartUsed):
        field, parent = PARENTS[model]
        expression = getattr(model, field).in_(ids[parent])
        if model is m.BatchItem:
            expression = and_(expression, m.BatchItem.cartridge_id.in_(ids[m.Cartridge]))
        elif model is m.RepairBatchItem:
            expression = and_(expression, m.RepairBatchItem.asset_id.in_(ids[m.Asset]))
        elif model is m.SwitchPort:
            expression = and_(expression,
                or_(m.SwitchPort.connected_asset_id.is_(None), m.SwitchPort.connected_asset_id.in_(ids[m.Asset])),
                or_(m.SwitchPort.zone_id.is_(None), m.SwitchPort.zone_id.in_(ids[m.Zone])))
        criteria[model] = expression
        ids[model] = select(tables[model].c.id).where(expression)
    if principal.role != "superadmin":
        criteria[m.AuditLog] = false()
    return criteria


def require_object_access(db, principal, model, object_id):
    # Query, not Session.get: a cached identity must never bypass a scoped SELECT.
    branch = db.info.get("scope_branch", None if principal.role == "superadmin" else principal.branch_id)
    expression = scope_criteria(principal, branch).get(model)
    query = db.query(model).filter(model.id == object_id)
    if expression is not None:
        query = query.filter(expression)
    obj = query.first()
    if obj is None:
        raise HTTPException(404, "Object not found in authorized scope")
    return obj


def require_user_management(principal, target=None, role=None, branch_id=None):
    if role is not None and role not in ROLES:
        raise HTTPException(422, "Unknown role")
    if principal.role == "superadmin":
        return
    if principal.role != "admin" or principal.branch_id is None:
        raise HTTPException(403, "User administration denied")
    if target is not None and (target.id == principal.id or target.role not in LOWER_ROLES):
        raise HTTPException(403, "Cannot administer self, peer administrator or superadmin")
    if role is not None and role not in LOWER_ROLES:
        raise HTTPException(403, "Cannot grant an administrator role")
    if branch_id is not None:
        require_branch_access(principal, branch_id)
    if target is not None:
        require_branch_access(principal, target.branch_id)


def branch_of(db, obj, seen=None):
    if obj is None: return None
    model = type(obj)
    if model is m.Branch: return obj.id
    if model in DIRECT: return obj.branch_id
    if model in PARENTS:
        field, parent = PARENTS[model]
        value = getattr(obj, field)
        related = db.query(parent).filter(parent.id == value).first() if value is not None else None
        return branch_of(db, related)
    return None


LINKS = {
        m.Asset: [("floor_id", m.Floor), ("zone_id", m.Zone)],
        m.BatchItem: [("cartridge_id", m.Cartridge)],
        m.RepairBatchItem: [("asset_id", m.Asset)],
        m.SwitchPort: [("zone_id", m.Zone), ("connected_asset_id", m.Asset)],
}


def validate_links(db, obj):
    """Structural consistency applies even to superadmins; cross-branch access is not a cross-link grant."""
    model = type(obj)
    own_branch = branch_of(db, obj)
    for field, parent in LINKS.get(model, []):
        value = getattr(obj, field)
        if value is None: continue
        related = db.query(parent).filter(parent.id == value).first()
        if related is None or branch_of(db, related) != own_branch:
            raise HTTPException(403, "Cross-branch relationship denied")
        if model is m.Asset and parent is m.Zone and obj.floor_id != related.floor_id:
            raise HTTPException(409, "Asset zone must belong to its floor")


def _branch_expression(model, table):
    if model in DIRECT:
        return table.c.branch_id
    field, parent = PARENTS[model]
    parent_table = parent.__table__.alias()
    return select(_branch_expression(parent, parent_table)).where(parent_table.c.id == table.c[field]).scalar_subquery()


def require_consistent_references(db, obj, visited=None):
    """Preflight legacy corruption before deletion/cascades or external side effects.

    This deliberately uses a trusted Core connection to see hidden incoming links.
    It returns no data to callers and never changes records. Ordinary request SQL
    remains forbidden. Inconsistent legacy records need a separate reviewed repair.
    """
    visited = set() if visited is None else visited
    model, oid = type(obj), obj.id
    if (model, oid) in visited or oid is None:
        return
    visited.add((model, oid))
    branch = branch_of(db, obj)
    for child, links in LINKS.items():
        for field, parent in links:
            if parent is not model:
                continue
            table = child.__table__
            home = _branch_expression(child, table)
            mismatch = home.is_not(None) if branch is None else or_(home != branch, home.is_(None))
            query = select(table.c.id).where(table.c[field] == oid, mismatch).limit(1)
            if db.connection().execute(query).first() is not None:
                raise HTTPException(409, "Existing cross-branch relationship requires reviewed data repair")
    # Validate children owned by this parent, including links hidden by read scope.
    for child, (field, parent) in PARENTS.items():
        if parent is model:
            table = child.__table__
            for link_field, target in LINKS.get(child, []):
                target_table = target.__table__.alias()
                target_branch = select(_branch_expression(target, target_table)).where(target_table.c.id == table.c[link_field]).scalar_subquery()
                mismatch = target_branch.is_not(None) if branch is None else or_(target_branch != branch, target_branch.is_(None))
                query = select(table.c.id).where(table.c[field] == oid, table.c[link_field].is_not(None), mismatch).limit(1)
                if db.connection().execute(query).first() is not None:
                    raise HTTPException(409, "Existing cross-branch relationship requires reviewed data repair")
            if child in {m.Zone, m.NetworkSwitch}:
                for related in db.query(child).filter(getattr(child, field) == oid).all():
                    require_consistent_references(db, related, visited)


def require_network_target(db, principal, address, allow_registered=True):
    if principal.role == "superadmin": return
    try: ip = ipaddress.ip_address(address)
    except (TypeError, ValueError): raise HTTPException(403, "Branch network operation requires an authorized IP address") from None
    branch = require_object_access(db, principal, m.Branch, principal.branch_id)
    try:
        if any(ip in ipaddress.ip_network(value, strict=False) for value in (branch.network_subnets or [])):
            return
    except (TypeError, ValueError):
        raise HTTPException(403, "Branch network configuration invalid") from None
    if not allow_registered or db.query(m.NetworkSwitch.id).filter(m.NetworkSwitch.ip_address == str(ip)).first() is None:
        raise HTTPException(403, "Network target is outside the branch allowlist")

