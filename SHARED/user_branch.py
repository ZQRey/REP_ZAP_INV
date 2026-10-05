"""Derive ordinary users' branch from their own cartridge records."""
from sqlalchemy import func
from SHARED.models import Cartridge

def sync_cartridge_owner_branch(db, user):
    if user.role != "user":
        return False
    branches = {row[0] for row in db.query(Cartridge.branch_id).filter(
        func.lower(Cartridge.current_user_id) == user.username.lower(),
        Cartridge.branch_id.is_not(None)).distinct().all()}
    if len(branches) != 1:
        return False
    branch = next(iter(branches))
    if user.branch_id == branch:
        return False
    user.branch_id = branch
    return True
