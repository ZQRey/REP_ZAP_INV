"""Application-level encryption for credentials persisted in PostgreSQL."""
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from SHARED.security_config import NETWORK_CREDENTIAL_KEY

PREFIX = "enc:v1:"


def _fernet() -> Fernet | None:
    if not NETWORK_CREDENTIAL_KEY:
        return None
    key = base64.urlsafe_b64encode(hashlib.sha256(NETWORK_CREDENTIAL_KEY.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(value: str | None) -> str | None:
    if not value or value.startswith(PREFIX):
        return value
    cipher = _fernet()
    if cipher is None:
        return value
    return PREFIX + cipher.encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str | None) -> str | None:
    if not value or not value.startswith(PREFIX):
        return value
    cipher = _fernet()
    if cipher is None:
        raise RuntimeError("NETWORK_CREDENTIAL_KEY is required to decrypt stored credentials")
    try:
        return cipher.decrypt(value[len(PREFIX):].encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Stored network credential cannot be decrypted with the configured key") from exc
