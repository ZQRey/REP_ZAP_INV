from typing import Optional
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from SHARED.models import AppUser
from CARTRIDGE.app.services.ldap_service import LDAPService


class AuthService:
    from SHARED.passwords import hash_password as _hash, verify_password as _verify
    hash_password = staticmethod(_hash)
    verify_password = staticmethod(_verify)

    from SHARED.tokens import create_access_token as _create, decode_access_token as _decode
    create_access_token = staticmethod(_create)
    decode_access_token = staticmethod(_decode)

    @classmethod
    def authenticate_user(
        cls,
        db: Session,
        username: str,
        password: str,
        auth_type: str = "local",
    ) -> Optional[AppUser]:
        """Authenticate a local or Active Directory user."""
        if auth_type not in ("local", "ad") or not username.strip() or not password:
            return None
        clean_user = username.strip()

        if auth_type == "ad":
            success, sam_account, ad_profile = LDAPService.authenticate_ad_user(
                db=db,
                username=clean_user,
                password=password,
            )
            if not success or not sam_account:
                return None

            from SHARED.models import ADUser

            # Refresh the local AD cache from the already authenticated LDAP profile.
            ad_info = db.query(ADUser).filter(ADUser.samaccountname.ilike(sam_account)).first()
            if ad_profile:
                if not ad_info:
                    ad_info = ADUser(
                        samaccountname=ad_profile["samaccountname"],
                        display_name=ad_profile["display_name"],
                        department=ad_profile.get("department"),
                        cabinet=ad_profile.get("cabinet"),
                        phone=ad_profile.get("phone"),
                    )
                    db.add(ad_info)
                else:
                    ad_info.display_name = ad_profile.get("display_name") or ad_info.display_name
                    ad_info.department = ad_profile.get("department") or ad_info.department
                    ad_info.cabinet = ad_profile.get("cabinet") or ad_info.cabinet
                    ad_info.phone = ad_profile.get("phone") or ad_info.phone

            # A pre-existing local account can never be taken over via AD.
            user = db.query(AppUser).filter(
                or_(
                    func.lower(AppUser.username) == sam_account.lower(),
                    func.lower(AppUser.username) == clean_user.lower(),
                )
            ).first()

            if user is not None:
                if user.auth_type != "ad" or not user.is_active:
                    db.rollback()
                    return None
            else:
                # First successful AD login gets the least-privileged local profile.
                # branch_id=None intentionally grants no branch-scoped business data.
                display_name = (
                    (ad_profile.get("display_name") if ad_profile else None)
                    or (ad_info.display_name if ad_info else None)
                    or sam_account
                )
                user = AppUser(
                    username=sam_account,
                    full_name=display_name,
                    password_hash=None,
                    auth_type="ad",
                    role="user",
                    is_active=True,
                    branch_id=None,
                )
                db.add(user)

            from SHARED.user_branch import sync_cartridge_owner_branch
            sync_cartridge_owner_branch(db, user)
            db.commit()
            db.refresh(user)
            return user

        user = db.query(AppUser).filter(func.lower(AppUser.username) == clean_user.lower()).first()
        if not user or user.auth_type != "local" or not user.password_hash:
            from SHARED.passwords import consume_dummy_check
            consume_dummy_check(password)
            return None

        if not cls.verify_password(password, user.password_hash) or not user.is_active:
            return None
        return user


from SHARED.authentication import (
    require_authenticated_user,
    get_current_user,
    require_role,
    require_superadmin,
    require_admin,
    require_operator,
)

# Compatibility name is mandatory authentication now; no optional authorization bypass.
get_current_user_optional = require_authenticated_user
