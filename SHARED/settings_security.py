"""Security boundary for settings returned by APIs and consumed internally."""
from SHARED.security_config import PRODUCTION, EVOLUTION_API_KEY
from SHARED.credential_crypto import decrypt_secret

# Environment-managed secrets remain outside the database.
ENV_SECRET_SETTINGS = {"wa_api_key": EVOLUTION_API_KEY}

# LDAP credentials are configured only through the web UI and encrypted at rest.
PERSISTED_ENCRYPTED_SETTINGS = {"ad_bind_user", "ad_bind_password"}

# Values that must never be returned verbatim by the public settings API.
MASKED_SETTINGS = {"wa_api_key", "ad_bind_password"}

# Compatibility name used by settings service/tests.
SECRET_SETTINGS = set(ENV_SECRET_SETTINGS) | PERSISTED_ENCRYPTED_SETTINGS


def effective_settings(values):
    result = dict(values)

    for name in PERSISTED_ENCRYPTED_SETTINGS:
        value = result.get(name)
        if value:
            result[name] = decrypt_secret(value)

    for name, value in ENV_SECRET_SETTINGS.items():
        if PRODUCTION or value:
            result[name] = value

    from SHARED.logging_security import register_secret
    for name in MASKED_SETTINGS:
        register_secret(result.get(name))
    return result


def public_settings(values):
    from SHARED.config import DEFAULT_SETTINGS

    allowed = set(DEFAULT_SETTINGS) | {"ad_filter", "default_vendor", "act_prefix"}
    return {
        key: ("******" if value else "") if key in MASKED_SETTINGS else value
        for key, value in values.items()
        if key in allowed
    }
