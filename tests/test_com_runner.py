import sys
import types
from pathlib import Path

from stata_fix.com_runner import ComStataRunner
from stata_fix.discovery import StataInstallation


class FakeComApp:
    def __init__(self):
        self.commands = []

    def DoCommand(self, code):
        self.commands.append(code)


def install_fake_win32com(monkeypatch):
    calls = []
    app = FakeComApp()

    win32com = types.ModuleType("win32com")
    client = types.ModuleType("win32com.client")

    def dispatch_ex(prog_id):
        calls.append(("DispatchEx", prog_id))
        return app

    def get_active_object(prog_id):
        calls.append(("GetActiveObject", prog_id))
        return app

    client.DispatchEx = dispatch_ex
    client.GetActiveObject = get_active_object
    win32com.client = client

    monkeypatch.setitem(sys.modules, "win32com", win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", client)

    return calls, app


def test_com_runner_uses_dispatch_ex_to_create_isolated_gui_session(monkeypatch, tmp_path):
    calls, app = install_fake_win32com(monkeypatch)
    install = StataInstallation(
        binary=tmp_path / "StataMP-64.exe",
        root=tmp_path,
        edition="mp",
        diagnostics="",
    )

    result = ComStataRunner(install, log_timeout=0).run("display 2+2")

    assert calls == [("DispatchEx", "stata.StataOLEApp")]
    assert any("display 2+2" in command for command in app.commands)
    assert result.rc == 0
    assert "Sent code to Stata GUI" in result.output


def test_com_runner_can_attach_to_existing_gui_session(monkeypatch, tmp_path):
    calls, app = install_fake_win32com(monkeypatch)
    install = StataInstallation(
        binary=tmp_path / "StataMP-64.exe",
        root=tmp_path,
        edition="mp",
        diagnostics="",
    )

    result = ComStataRunner(install, attach_existing=True, log_timeout=0).run("display 2+2")

    assert calls == [("GetActiveObject", "stata.StataOLEApp")]
    assert any("display 2+2" in command for command in app.commands)
    assert result.rc == 0


def test_com_runner_attach_reports_failure_when_no_active_gui(monkeypatch, tmp_path):
    win32com = types.ModuleType("win32com")
    client = types.ModuleType("win32com.client")

    def get_active_object(prog_id):
        raise RuntimeError("Operation unavailable")

    client.GetActiveObject = get_active_object
    win32com.client = client
    monkeypatch.setitem(sys.modules, "win32com", win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", client)
    install = StataInstallation(
        binary=tmp_path / "StataMP-64.exe",
        root=tmp_path,
        edition="mp",
        diagnostics="",
    )

    status = ComStataRunner(install, attach_existing=True).attach()

    assert status.available is False
    assert "Operation unavailable" in status.reason


def test_com_runner_wraps_code_with_log_and_returns_log_text(monkeypatch, tmp_path):
    calls, app = install_fake_win32com(monkeypatch)
    log_path = tmp_path / "stata.log"
    install = StataInstallation(
        binary=tmp_path / "StataMP-64.exe",
        root=tmp_path,
        edition="mp",
        diagnostics="",
    )

    def write_fake_log(code):
        app.commands.append(code)
        if code == "log close stata_fix_mcp":
            log_path.write_text("summarize price\n\nVariable | Obs Mean\n", encoding="utf-8")

    app.DoCommand = write_fake_log

    result = ComStataRunner(install, log_path_factory=lambda: log_path).run("summarize price", echo=True)

    assert calls == [("DispatchEx", "stata.StataOLEApp")]
    assert any('log using "' in command for command in app.commands)
    assert "summarize price" in app.commands
    assert "log close stata_fix_mcp" in app.commands
    assert result.rc == 0
    assert "Variable | Obs Mean" in result.output


def test_com_runner_uses_named_log_without_closing_user_logs(monkeypatch, tmp_path):
    calls, app = install_fake_win32com(monkeypatch)
    install = StataInstallation(
        binary=tmp_path / "StataMP-64.exe",
        root=tmp_path,
        edition="mp",
        diagnostics="",
    )

    ComStataRunner(install, attach_existing=True, log_timeout=0).run("display 1")

    assert calls == [("GetActiveObject", "stata.StataOLEApp")]
    assert "capture log close stata_fix_mcp" in app.commands
    assert "log close stata_fix_mcp" in app.commands
    assert "capture log close _all" not in app.commands
    assert "log close _all" not in app.commands


def test_com_runner_waits_for_delayed_log_file(monkeypatch, tmp_path):
    calls, app = install_fake_win32com(monkeypatch)
    log_path = tmp_path / "stata.log"
    checks = []
    install = StataInstallation(
        binary=tmp_path / "StataMP-64.exe",
        root=tmp_path,
        edition="mp",
        diagnostics="",
    )

    real_exists = Path.exists

    def delayed_exists(path):
        if path == log_path:
            checks.append(path)
            if len(checks) == 2:
                log_path.write_text("delayed log text", encoding="utf-8")
            return real_exists(path)
        return real_exists(path)

    monkeypatch.setattr(Path, "exists", delayed_exists)

    result = ComStataRunner(install, log_path_factory=lambda: log_path, poll_interval=0).run("display 1")

    assert calls == [("DispatchEx", "stata.StataOLEApp")]
    assert result.rc == 0
    assert result.output == "delayed log text"


def test_com_runner_returns_setup_error_when_pywin32_missing(monkeypatch, tmp_path):
    import builtins

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "win32com.client":
            raise ModuleNotFoundError("No module named 'win32com'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    install = StataInstallation(
        binary=tmp_path / "StataMP-64.exe",
        root=tmp_path,
        edition="mp",
        diagnostics="",
    )

    result = ComStataRunner(install).run("display 2+2")

    assert result.rc == 1
    assert "pywin32" in result.error


def test_com_runner_default_log_path_uses_workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    install = StataInstallation(
        binary=tmp_path / "StataMP-64.exe",
        root=tmp_path,
        edition="mp",
        diagnostics="",
    )

    path = ComStataRunner(install)._default_log_path()

    assert path.parent == tmp_path / ".stata-fix"
    assert path.name.startswith("stata-fix-com-")
