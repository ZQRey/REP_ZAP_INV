"""Versioned password hashes; existing legacy hashes remain verifiable."""
import hashlib
import secrets

ITERATIONS = 600_000


def hash_password(password):
    if not 12 <= len(password) <= 1024:
        raise ValueError("Password length must be between 12 and 1024 characters")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITERATIONS).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"


def verify_password(password, hashed):
    if not password or len(password) > 1024 or not hashed:
        return False
    try:
        parts = hashed.split("$")
        if len(parts) == 2:
            salt, expected = parts
            iterations = 100_000
        else:
            algorithm, count, salt, expected = parts
            if algorithm != "pbkdf2_sha256":
                return False
            iterations = int(count)
            if not 100_000 <= iterations <= 2_000_000:
                return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()
        return secrets.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


_DUMMY = hash_password(secrets.token_urlsafe(24))


def consume_dummy_check(password):
    verify_password(password, _DUMMY)
