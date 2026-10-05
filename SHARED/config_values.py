"""Read one configuration value without initializing unrelated runtime services."""
import os
from pathlib import Path


def secret(name: str, required: bool = False) -> str:
    value, filename = os.getenv(name, ""), os.getenv(name + "_FILE", "")
    if not filename:
        default_file = Path("/run/app-secrets") / name.lower()
        if default_file.is_file():
            filename = str(default_file)
    if value and filename:
        raise RuntimeError(f"Configure only {name} or {name}_FILE")
    if filename:
        try:
            value = Path(filename).read_text(encoding="utf-8").strip()
        except OSError:
            raise RuntimeError(f"Cannot read {name}_FILE") from None
    if required and not value:
        raise RuntimeError(f"Required configuration missing: {name}")
    return value
