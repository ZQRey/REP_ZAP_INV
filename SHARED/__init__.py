"""Shared package with lazy compatibility exports and no eager database/auth cycle."""
from importlib import import_module

_EXPORTS = {
    **{name: "SHARED.config" for name in ("DATABASE_URL", "SECRET_KEY", "DEFAULT_SETTINGS")},
    **{name: "SHARED.database" for name in ("engine", "SessionLocal", "Base", "get_db", "init_db", "session_scope")},
    **{name: "SHARED.models" for name in ("Branch", "AppUser", "SystemSetting", "ADUser", "Cartridge", "Asset", "Floor", "Zone")},
    **{name: "SHARED.auth_service" for name in ("AuthService", "get_current_user", "require_role", "require_superadmin")},
}
__all__ = list(_EXPORTS)


def __getattr__(name):
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(name)
    value = getattr(import_module(module), name)
    globals()[name] = value
    return value
