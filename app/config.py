"""
Shared environment loading for all scripts. Loads .env once, at import
time, so every script picks up real values automatically instead of
relying on $env: variables being manually set in the current terminal
session (which don't persist across new terminals — the recurring
problem this file exists to fix).

Import this BEFORE reading any os.environ values:
    from app.config import load_env
    load_env()
"""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"


def load_env() -> None:
    if not ENV_PATH.exists():
        print(f"Warning: no .env file found at {ENV_PATH}")
        return
    load_dotenv(dotenv_path=ENV_PATH)


def require_env(*names: str) -> dict:
    """
    Fetch required env vars after load_env() has run. Raises a clear
    error listing every missing var at once, rather than failing on the
    first one — same behavior the scripts already had, just centralized.
    """
    values = {name: os.environ.get(name) for name in names}
    missing = [name for name, val in values.items() if not val]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")
    return values
