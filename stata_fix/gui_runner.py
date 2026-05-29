from __future__ import annotations

import time
import uuid
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from .com_runner import ComBackendStatus
from .discovery import StataInstallation
from .paths import runtime_path
from .pystata_runner import StataRunResult


@dataclass(frozen=True)
class GuiWindowInfo:
    hwnd: int
    pid: int
    title: str
    process_name: str


class GuiAutomation(Protocol):
    def list_windows(self) -> list[GuiWindowInfo]: ...

    def send_command(self, hwnd: int, command: str) -> None: ...

    def inspect_window(self, hwnd: int, max_chars: int = 4000) -> dict[str, object]: ...


class Win32GuiAutomation:
    def list_windows(self) -> list[GuiWindowInfo]:
        import win32gui
        import win32process

        windows: list[GuiWindowInfo] = []

        def callback(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if not title or "Stata" not in title:
                return
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process_name = _process_name(pid)
            if "stata" not in process_name.lower() and "stata" not in title.lower():
                return
            windows.append(GuiWindowInfo(hwnd=hwnd, pid=pid, title=title, process_name=process_name))

        win32gui.EnumWindows(callback, None)
        return windows

    def send_command(self, hwnd: int, command: str) -> None:
        import time as _time

        import win32api
        import win32clipboard
        import win32con
        import win32gui

        if not win32gui.IsWindow(hwnd):
            raise RuntimeError(f"Stata window not found: hwnd={hwnd}")

        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        _time.sleep(0.1)

        previous_clipboard = _get_clipboard_text(win32clipboard)
        try:
            _set_clipboard_text(win32clipboard, command)
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(ord("V"), 0, 0, 0)
            win32api.keybd_event(ord("V"), 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
            _time.sleep(0.05)
            win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
            win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
        finally:
            if previous_clipboard is not None:
                _set_clipboard_text(win32clipboard, previous_clipboard)

    def inspect_window(self, hwnd: int, max_chars: int = 4000) -> dict[str, object]:
        return _inspect_with_win32(hwnd, max_chars=max_chars)


class GuiStataRunner:
    backend = "gui"

    def __init__(
        self,
        installation: StataInstallation,
        *,
        hwnd: int,
        automation: GuiAutomation | None = None,
        log_path_factory: Callable[[], Path] | None = None,
        code_path_factory: Callable[[], Path] | None = None,
        wrapper_path_factory: Callable[[], Path] | None = None,
        log_timeout: float = 10,
        poll_interval: float = 0.1,
    ):
        self.installation = installation
        self.hwnd = hwnd
        self.automation = automation or Win32GuiAutomation()
        self.log_path_factory = log_path_factory or self._default_log_path
        self.code_path_factory = code_path_factory or self._default_code_path
        self.wrapper_path_factory = wrapper_path_factory or self._default_wrapper_path
        self.log_timeout = log_timeout
        self.poll_interval = poll_interval

    def attach(self) -> ComBackendStatus:
        if any(window.hwnd == self.hwnd for window in self.automation.list_windows()):
            return ComBackendStatus(True, "")
        return ComBackendStatus(False, f"Stata GUI window not found: hwnd={self.hwnd}")

    def inspect(self, max_chars: int = 4000) -> dict[str, object]:
        return self.automation.inspect_window(self.hwnd, max_chars=max_chars)

    def run(self, code: str, *, echo: bool = False) -> StataRunResult:
        status = self.attach()
        if not status.available:
            return StataRunResult(rc=1, output="", error=status.reason)

        log_path = self.log_path_factory()
        code_path = self.code_path_factory()
        wrapper_path = self.wrapper_path_factory()
        try:
            code_path.write_text(code.rstrip() + "\n", encoding="utf-8")
            wrapper_path.write_text(self._wrapper_code(code_path, log_path), encoding="utf-8")
            self.automation.send_command(self.hwnd, f'do "{_stata_path(wrapper_path)}"')
            output = self._read_log(log_path)
            rc = _parse_stata_rc(output)
        except Exception as exc:
            return StataRunResult(rc=1, output="", error=str(exc))
        finally:
            _cleanup(code_path)
            _cleanup(wrapper_path)
            _cleanup(log_path)

        return StataRunResult(rc=rc, output=output, error="")

    def _wrapper_code(self, code_path: Path, log_path: Path) -> str:
        return "\n".join(
            [
                "capture log close stata_fix_mcp",
                f'log using "{_stata_path(log_path)}", name(stata_fix_mcp) replace text',
                f'capture noisily do "{_stata_path(code_path)}"',
                "local stata_fix_rc = _rc",
                'display as text "stata_fix_rc=`stata_fix_rc\'"',
                "log close stata_fix_mcp",
                "",
            ]
        )

    def _read_log(self, log_path: Path) -> str:
        deadline = time.monotonic() + self.log_timeout
        while not log_path.exists() and time.monotonic() < deadline:
            time.sleep(self.poll_interval)
        if not log_path.exists():
            return "Sent command to Stata GUI, but no log file was produced."
        return log_path.read_text(encoding="utf-8", errors="replace")

    def _default_log_path(self) -> Path:
        return runtime_path("stata-fix-gui", ".log")

    def _default_code_path(self) -> Path:
        return runtime_path("stata-fix-gui-code", ".do")

    def _default_wrapper_path(self) -> Path:
        return runtime_path("stata-fix-gui-wrapper", ".do")


def _process_name(pid: int) -> str:
    try:
        import win32api
        import win32con
        import win32process

        handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        try:
            return Path(win32process.GetModuleFileNameEx(handle, 0)).stem
        finally:
            handle.Close()
    except Exception:
        return ""


def _get_clipboard_text(win32clipboard) -> str | None:
    try:
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(1):
                return win32clipboard.GetClipboardData(1)
            return None
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        return None


def _set_clipboard_text(win32clipboard, text: str) -> None:
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text)
    finally:
        win32clipboard.CloseClipboard()


def _inspect_with_win32(hwnd: int, *, max_chars: int) -> dict[str, object]:
    import win32gui

    elements: list[dict[str, str]] = []

    def callback(child_hwnd, _):
        if len(elements) >= 200:
            return
        text = win32gui.GetWindowText(child_hwnd)
        class_name = win32gui.GetClassName(child_hwnd)
        if text or class_name:
            elements.append(
                {
                    "hwnd": str(child_hwnd),
                    "class": class_name,
                    "text": text[:max_chars],
                }
            )

    win32gui.EnumChildWindows(hwnd, callback, None)
    return {"hwnd": hwnd, "title": win32gui.GetWindowText(hwnd), "elements": elements}


def _stata_path(path: Path) -> str:
    return str(path).replace("\\", "/")


def _cleanup(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _parse_stata_rc(output: str) -> int:
    matches = re.findall(r"stata_fix_rc=(\d+)", output)
    if not matches:
        return 0
    return int(matches[-1])
