import os
from pathlib import Path


def load_environment(path=".env"):
    """Load environment variables from .env without overwriting real env vars."""

    try:
        from dotenv import load_dotenv
    except ImportError:
        _load_env_fallback(path)
        return

    load_dotenv(path, override=False)


def _load_env_fallback(path):
    env_path = Path(path)

    if not env_path.exists():
        return

    for raw_line in env_path.read_text(errors="replace").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value
