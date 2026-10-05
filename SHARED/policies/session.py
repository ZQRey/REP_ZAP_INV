"""Request-scoped ORM enforcement shared by routers, services, aggregates and loaders."""
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session, with_loader_criteria
from fastapi import HTTPException
from SHARED import models as m
from .core import DIRECT, GLOBAL, SCOPED, PARENTS, LOWER_ROLES, scope_criteria, branch_of, validate_links, require_user_management, require_network_target


def bind_scope(db, principal, policy, branch_id):
    db.info.update(principal=principal, policy=policy, scope_branch=branch_id)


@event.listens_for(Session, "do_orm_execute")
def scoped_execution(state):
    principal = state.session.info.get("principal")
    if principal is None:
        return  # startup/CLI/login are trusted non-request entry points, not public data APIs
    if not state.is_orm_statement:
        raise HTTPException(403, "Unscoped SQL is forbidden in authenticated requests")
    criteria = scope_criteria(principal, state.session.info["scope_branch"])
    if state.is_select:
        state.statement = state.statement.options(*[
            with_loader_criteria(model, expression, include_aliases=True) for model, expression in criteria.items()
        ])
    elif state.is_update or state.is_delete:
        model = state.bind_mapper.class_ if state.bind_mapper else None
        if model is m.DocumentCounter and state.is_update:
            if state.session.info["policy"]["action"] != "write":
                raise HTTPException(403, "Number allocation requires write permission")
            return
        # Bulk DML skips before_flush; restrict it to reviewed cleanup-only deletes/NULL updates.
        if state.session.info["policy"]["action"] != "write" or model not in SCOPED:
            raise HTTPException(403, "Bulk operation denied")
        if state.is_update:
            values = getattr(state.statement, "_values", {})
            if not values or any(getattr(value, "value", object()) is not None for value in values.values()):
                raise HTTPException(403, "Bulk reassignment requires an explicit object policy")
            allowed = {m.Asset: {"floor_id", "zone_id", "coords_x", "coords_y"},
                       m.SwitchPort: {"connected_asset_id"}}
            if principal.role == "superadmin" and state.session.info["policy"]["domain"] == "branches":
                allowed[m.AppUser] = {"branch_id"}
            if not {column.key for column in values} <= allowed.get(model, set()):
                raise HTTPException(403, "Bulk update is not a reviewed cleanup operation")
        if model in criteria:
            state.statement = state.statement.where(criteria[model])


@event.listens_for(Session, "before_flush")
def scoped_writes(db, flush_context, instances):
    principal = db.info.get("principal")
    if principal is None: return
    policy = db.info["policy"]
    for obj in list(db.new) + list(db.dirty) + list(db.deleted):
        if obj in db.dirty and not db.is_modified(obj, include_collections=False): continue
        model = type(obj)
        if policy["action"] not in {"write", "wa_self"}:
            raise HTTPException(403, "Read endpoint cannot modify objects")
        if model not in SCOPED | GLOBAL:
            raise HTTPException(403, "Entity has no scope policy")
        if model in DIRECT and obj in db.new and obj.branch_id is None:
            obj.branch_id = db.info.get("create_branch", principal.branch_id)
        if model is m.Branch and principal.role != "superadmin" and inspect(obj).attrs.network_subnets.history.has_changes():
            raise HTTPException(403, "Only superadmin can change the branch network allowlist")
        if model is m.NetworkSwitch:
            changed = {a.key for a in inspect(obj).attrs if a.history.has_changes()}
            credential_fields = {"asset_id", "ip_address", "management_type", "mgmt_port", "username", "password", "snmp_community", "extra_params"}
            if (obj in db.new or changed & credential_fields) and principal.role not in {"superadmin", "admin", "technician"}:
                raise HTTPException(403, "Network configuration permission required")
            if obj in db.new or "ip_address" in changed:
                require_network_target(db, principal, obj.ip_address, allow_registered=False)
        if model in SCOPED:
            branch = branch_of(db, obj)
            if principal.role != "superadmin" and (branch is None or branch != principal.branch_id):
                raise HTTPException(403, "Write outside authorized branch")
            if model in DIRECT and obj not in db.new and model is not m.AppUser:
                if inspect(obj).attrs.branch_id.history.has_changes() and not (
                    model is m.Asset and obj.id in db.info.get("network_transfers", set())
                    and principal.role == "superadmin" and policy["network"] and policy["domain"] == "location"
                ):
                    raise HTTPException(403, "Branch transfer requires a dedicated reviewed operation")
            if model in PARENTS and obj not in db.new:
                field, parent = PARENTS[model]
                history = inspect(obj).attrs[field].history
                if history.has_changes():
                    old = db.query(parent).filter(parent.id == history.deleted[0]).first() if history.deleted else None
                    if old is None or branch_of(db, old) != branch:
                        raise HTTPException(403, "Cross-branch reparenting denied")
            validate_links(db, obj)
        if model is m.AppUser:
            changed = {a.key for a in inspect(obj).attrs if a.history.has_changes()}
            if policy["action"] == "wa_self" and obj.id == principal.id and changed <= {"wa_instance_name"}:
                continue
            if obj not in db.new and principal.role != "superadmin":
                prior_roles = inspect(obj).attrs.role.history.deleted
                prior_branches = inspect(obj).attrs.branch_id.history.deleted
                if any(role not in LOWER_ROLES for role in prior_roles) or any(branch != principal.branch_id for branch in prior_branches):
                    raise HTTPException(403, "Original user ownership/role cannot be bypassed by reassignment")
            require_user_management(principal, None if obj in db.new else obj, obj.role, obj.branch_id)
        elif model in GLOBAL and principal.role != "superadmin":
            raise HTTPException(403, "Global configuration/catalog mutation requires superadmin")
