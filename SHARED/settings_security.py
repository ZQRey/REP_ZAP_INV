"""Secret overrides are never serialized by the settings API."""
from SHARED.security_config import PRODUCTION, EVOLUTION_API_KEY, LDAP_BIND_PASSWORD

SECRET_SETTINGS = {"wa_api_key": EVOLUTION_API_KEY, "ad_bind_password": LDAP_BIND_PASSWORD}


def effective_settings(values):
    result = dict(values)
    for name, value in SECRET_SETTINGS.items():
        if PRODUCTION or value:
            result[name] = value
    from SHARED.logging_security import register_secret
    for name in SECRET_SETTINGS:
        register_secret(result.get(name))
    return result


def public_settings(values):
    from SHARED.config import DEFAULT_SETTINGS
    allowed = set(DEFAULT_SETTINGS) | {"ad_filter", "default_vendor", "act_prefix"}
    return {key: ("******" if value else "") if key in SECRET_SETTINGS else value
            for key, value in values.items() if key in allowed}
