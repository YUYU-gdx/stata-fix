from __future__ import annotations

import os
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .discovery import StataInstallation
from .pystata_runner import StataRunResult


DEFAULT_COM_PROG_ID = "stata.StataOLEApp"


@dataclass(frozen=True)
class ComBackendStatus:
    available: bool
    reason: str


def is_com_available() -> bool:
    if os.name != "nt":
        return False

    try:
        import win32com.client  # noqa: F401
    except ModuleNotFoundError:
        return False

    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, DEFAULT_COM_PROG_ID):
            return True
    except OSError:
        return False

    return True


class ComStataRunner:
    backend = "com"

    def __init__(
        self,
        installation: StataInstallation,
        *,
        prog_id: str = DEFAULT_COM_PROG_ID,
        log_path_factory: Callable[[], Path] | None = None,
        log_timeout: float = 10,
        poll_interval: float = 0.1,
        attach_existing: bool = False,
    ):
        self.installation = installation
        self.prog_id = prog_id
        self.log_path_factory = log_path_factory or self._default_log_path
        self.log_timeout = log_timeout
        self.poll_interval = poll_interval
        self.attach_existing = attach_existing
        self._app = None

    def attach(self) -> ComBackendStatus:
        try:
            self._ensure_app()
        except ModuleNotFoundError:
            return ComBackendStatus(False, "Windows COM backend requires pywin32. Install it with: uv add pywin32")
        except Exception as exc:
            return ComBackendStatus(False, str(exc))
        return ComBackendStatus(True, "")

    def run(self, code: str, *, echo: bool = False) -> StataRunResult:
        if self.installation.binary is None:
            return StataRunResult(rc=601, output="", error=self.installation.diagnostics)

        log_path = self.log_path_factory()
        try:
            app = self._ensure_app()
            for command in self._logged_commands(code, log_path, echo=echo):
                app.DoCommand(command)
            output = self._read_log(log_path)
        except ModuleNotFoundError:
            return StataRunResult(
                rc=1,
                output="",
                error="Windows COM backend requires pywin32. Install it with: uv add pywin32",
            )
        except Exception as exc:
            return StataRunResult(rc=1, output="", error=str(exc))
        finally:
            self._cleanup_log(log_path)

        return StataRunResult(
            rc=0,
            output=output,
            error="",
        )

    def _ensure_app(self):
        if self._app is not None:
            return self._app

        import win32com.client

        if self.attach_existing:
            self._app = win32com.client.GetActiveObject(self.prog_id)
        else:
            # DispatchEx intentionally creates a separate Automation instance
            # instead of attaching to a user's active Stata GUI session.
            self._app = win32com.client.DispatchEx(self.prog_id)
        return self._app

    def _logged_commands(self, code: str, log_path: Path, *, echo: bool) -> list[str]:
        escaped_log = str(log_path).replace("\\", "/")
        return [
            "capture log close stata_fix_mcp",
            f'log using "{escaped_log}", name(stata_fix_mcp) replace text',
            *[line for line in code.splitlines() if line.strip()],
            "log close stata_fix_mcp",
        ]

    def _read_log(self, log_path: Path) -> str:
        deadline = time.monotonic() + self.log_timeout
        while not log_path.exists() and time.monotonic() < deadline:
            time.sleep(self.poll_interval)

        if not log_path.exists():
            return "Sent code to Stata GUI through Windows COM, but no log file was produced."
        return log_path.read_text(encoding="utf-8", errors="replace")

    def _cleanup_log(self, log_path: Path) -> None:
        try:
            log_path.unlink(missing_ok=True)
        except OSError:
            pass

    def _default_log_path(self) -> Path:
        return Path(tempfile.gettempdir()) / f"stata-fix-{uuid.uuid4().hex}.log"
