"""Cartridge Tracker Application Package."""
from pathlib import Path
import sys

# Preserve `uvicorn app.main:app` when launched from CARTRIDGE in a full checkout.
_project_root = Path(__file__).resolve().parents[2]
if (_project_root / "SHARED").is_dir() and str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

__version__ = "1.0.0"
