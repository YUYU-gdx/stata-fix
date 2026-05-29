from __future__ import annotations

import os
import uuid
from pathlib import Path


def runtime_dir() -> Path:
    override = os.environ.get("STATA_FIX_WORKDIR")
    directory = Path(override).expanduser() if override else Path.cwd() / ".stata-fix"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def runtime_path(prefix: str, suffix: str) -> Path:
    return runtime_dir() / f"{prefix}-{uuid.uuid4().hex}{suffix}"
