"""Encrypt legacy plaintext network credentials in place.

Run once after Alembic 0005 with NETWORK_CREDENTIAL_KEY configured. Idempotent.
"""
from SHARED.database import SessionLocal
from SHARED.models import NetworkSwitch
from SHARED.credential_crypto import PREFIX, encrypt_secret


def main():
    changed = 0
    with SessionLocal() as db:
        for switch in db.query(NetworkSwitch).all():
            for attr in ("_password", "_snmp_community"):
                value = getattr(switch, attr)
                if value and not value.startswith(PREFIX):
                    setattr(switch, attr, encrypt_secret(value))
                    changed += 1
        db.commit()
    print(f"Encrypted {changed} network credential values")


if __name__ == "__main__":
    main()
