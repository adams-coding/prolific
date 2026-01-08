from __future__ import annotations

import hashlib
import hmac
from pathlib import Path
import secrets

from prolific_agent.config import default_state_dir


def _salt_path() -> Path:
    # Local-only secret used to anonymize project identifiers in committed reports.
    return default_state_dir() / "salt.txt"


def get_or_create_local_salt() -> str:
    """
    Returns a local-only salt string.

    - Stored under ~/.prolific/salt.txt (NOT committed to any repo).
    - Used to compute stable pseudonymous IDs for watch folders.
    """
    p = _salt_path()
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    p.parent.mkdir(parents=True, exist_ok=True)
    salt = secrets.token_hex(16)
    p.write_text(salt, encoding="utf-8")
    return salt


def project_id_for_watch_path(watch_path: Path, *, salt: str) -> str:
    """
    Produce a stable pseudonymous ID for a watch folder.

    This prevents leaking actual folder names/paths into committed reports while
    still letting the UI/viz group events by "project".
    """
    try:
        resolved = str(watch_path.expanduser().resolve())
    except Exception:
        resolved = str(watch_path)
    digest = hmac.new(
        key=salt.encode("utf-8"),
        msg=resolved.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return f"Project-{digest[:10]}"


