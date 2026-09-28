"""Defense in depth; credentials and upstream bodies must never be logged."""
import logging
import re
import threading
from SHARED.security_config import SECRET_KEY, DATABASE_URL, REDIS_URL, EVOLUTION_API_KEY, LDAP_BIND_PASSWORD

_sensitive = {v for v in (SECRET_KEY, DATABASE_URL, REDIS_URL, EVOLUTION_API_KEY, LDAP_BIND_PASSWORD) if v}
_lock = threading.Lock()


def register_secret(value):
    if value:
        with _lock:
            if len(_sensitive) < 4096:
                _sensitive.add(str(value))


def redact(message):
    with _lock:
        values = sorted(_sensitive, key=len, reverse=True)
    for value in values:
        message = message.replace(value, "[REDACTED]")
    message = re.sub(r"(?i)(bearer\s+)\S+", r"\1[REDACTED]", message)
    message = re.sub(r"(?i)((?:password|passwd|api[_-]?key|apikey|secret[_-]?key|snmp_community|token)\s*[=:]\s*)[^\s,&}]+", r"\1[REDACTED]", message)
    message = re.sub(r"(://)[^\s/@]+:[^\s/@]+@", r"\1[REDACTED]@", message)
    return message


def install():
    if getattr(logging.getLogRecordFactory(), "_security_redactor", False):
        return
    previous = logging.getLogRecordFactory()
    def factory(*args, **kwargs):
        record = previous(*args, **kwargs)
        record.msg = redact(record.getMessage())
        record.args = ()
        # Exception messages may contain credentials outside structured fields.
        if record.exc_info:
            record.msg += " [exception: " + record.exc_info[0].__name__ + "]"
            record.exc_info = None
            record.exc_text = None
        return record
    factory._security_redactor = True
    logging.setLogRecordFactory(factory)
    logging.getLogger("uvicorn.access").disabled = True
    for name in ("httpx", "httpcore", "paramiko", "ldap3"):
        logging.getLogger(name).setLevel(logging.WARNING)
