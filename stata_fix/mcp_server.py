from __future__ import annotations

import os
import subprocess
from functools import lru_cache

from mcp.server.fastmcp import FastMCP

from .com_runner import ComStataRunner, is_com_available
from .discovery import discover_stata
from .gui_runner import GuiStataRunner, Win32GuiAutomation
from .paths import runtime_dir
from .pystata_runner import PyStataRunner


mcp = FastMCP("stata-fix")
_runner_override = None


@lru_cache(maxsize=1)
def get_runner():
    if _runner_override is not None:
        return _runner_override
    return create_runner(discover_stata())


def create_runner(installation, *, attach_existing: bool = False):
    if os.name == "nt":
        if is_com_available():
            return ComStataRunner(installation, attach_existing=attach_existing)
        if register_stata_com(installation) and is_com_available():
            return ComStataRunner(installation, attach_existing=attach_existing)
    return PyStataRunner(installation)


def register_stata_com(installation) -> bool:
    if os.name != "nt" or installation.binary is None:
        return False

    try:
        completed = subprocess.run(
            [str(installation.binary), "/Register"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
    except Exception:
        return False
    return completed.returncode == 0


@mcp.tool(structured_output=True)
async def stata_detect() -> dict[str, object]:
    """Detect the local Stata installation used by this MCP server."""
    installation = discover_stata()
    runner = create_runner(installation)
    return {
        "found": installation.binary is not None,
        "binary": str(installation.binary) if installation.binary is not None else None,
        "root": str(installation.root) if installation.root is not None else None,
        "edition": installation.edition,
        "backend": getattr(runner, "backend", "pystata"),
        "runtime_dir": str(runtime_dir()),
        "diagnostics": installation.diagnostics,
    }


@mcp.tool(structured_output=True)
async def stata_run(code: str, echo: bool = False) -> dict[str, object]:
    """Run Stata code through the configured local Stata backend."""
    result = get_runner().run(code, echo=echo)
    return {"rc": result.rc, "output": result.output, "error": result.error}


@mcp.tool(structured_output=True)
async def stata_attach_existing() -> dict[str, object]:
    """Explicitly attach to an existing Stata Automation GUI session on Windows."""
    global _runner_override

    installation = discover_stata()
    if os.name != "nt" or not is_com_available():
        return {
            "attached": False,
            "backend": "pystata",
            "error": "Attaching to an existing Stata GUI requires Windows Stata Automation COM.",
        }

    get_runner.cache_clear()
    runner = create_runner(installation, attach_existing=True)
    status = runner.attach()
    if not status.available:
        return {
            "attached": False,
            "backend": getattr(runner, "backend", "com"),
            "error": status.reason,
        }

    _runner_override = runner
    return {
        "attached": True,
        "backend": getattr(runner, "backend", "com"),
        "warning": "Attached to an existing Stata Automation session. Previous Results-window history is not guaranteed to be readable unless it was logged.",
    }


@mcp.tool(structured_output=True)
async def stata_gui_windows() -> dict[str, object]:
    """List visible Stata GUI windows that can be targeted by the GUI backend."""
    windows = Win32GuiAutomation().list_windows()
    return {
        "windows": [
            {
                "hwnd": window.hwnd,
                "pid": window.pid,
                "title": window.title,
                "process_name": window.process_name,
            }
            for window in windows
        ]
    }


@mcp.tool(structured_output=True)
async def stata_attach_gui_window(hwnd: int) -> dict[str, object]:
    """Attach future stata_run calls to a visible Stata GUI window by HWND."""
    global _runner_override

    runner = GuiStataRunner(discover_stata(), hwnd=hwnd)
    status = runner.attach()
    if not status.available:
        return {"attached": False, "backend": "gui", "error": status.reason}

    get_runner.cache_clear()
    _runner_override = runner
    return {
        "attached": True,
        "backend": "gui",
        "hwnd": hwnd,
        "warning": "GUI backend controls the selected Stata window by sending commands to its UI. It reads new command output from a temporary log, not from prior Results-window history.",
    }


@mcp.tool(structured_output=True)
async def stata_gui_inspect(hwnd: int, max_chars: int = 4000) -> dict[str, object]:
    """Return UI Automation/Win32-visible content for a Stata GUI window."""
    return Win32GuiAutomation().inspect_window(hwnd, max_chars=max_chars)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
