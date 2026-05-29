import asyncio

from stata_fix.discovery import StataInstallation
from stata_fix.com_runner import ComStataRunner
from stata_fix.gui_runner import GuiWindowInfo
from stata_fix.mcp_server import (
    create_runner,
    stata_attach_existing,
    stata_attach_gui_window,
    stata_detect,
    stata_gui_inspect,
    stata_gui_windows,
    stata_run,
)
from stata_fix.pystata_runner import StataRunResult


class FakeRunner:
    def run(self, code, *, echo=False):
        return StataRunResult(rc=0, output=f"ran: {code}", error="")


def test_stata_run_returns_structured_result(monkeypatch):
    monkeypatch.setattr("stata_fix.mcp_server.get_runner", lambda: FakeRunner())

    result = asyncio.run(stata_run("display 2+2"))

    assert result == {"rc": 0, "output": "ran: display 2+2", "error": ""}


def test_stata_detect_returns_discovered_installation(monkeypatch, tmp_path):
    binary = tmp_path / "StataNowMP-64.exe"
    monkeypatch.setattr(
        "stata_fix.mcp_server.discover_stata",
        lambda: StataInstallation(binary=binary, root=tmp_path, edition="mp", diagnostics=""),
    )
    monkeypatch.setattr("stata_fix.mcp_server.is_com_available", lambda: True)
    monkeypatch.setattr("stata_fix.mcp_server.runtime_dir", lambda: tmp_path / ".stata-fix")

    result = asyncio.run(stata_detect())

    assert result == {
        "found": True,
        "binary": str(binary),
        "root": str(tmp_path),
        "edition": "mp",
        "backend": "com",
        "runtime_dir": str(tmp_path / ".stata-fix"),
        "diagnostics": "",
    }


def test_create_runner_defaults_to_com_on_windows_when_available(monkeypatch, tmp_path):
    install = StataInstallation(
        binary=tmp_path / "StataMP-64.exe",
        root=tmp_path,
        edition="mp",
        diagnostics="",
    )
    monkeypatch.setattr("stata_fix.mcp_server.os.name", "nt")
    monkeypatch.setattr("stata_fix.mcp_server.is_com_available", lambda: True)

    runner = create_runner(install)

    assert isinstance(runner, ComStataRunner)


def test_create_runner_registers_stata_com_before_falling_back(monkeypatch, tmp_path):
    install = StataInstallation(
        binary=tmp_path / "StataMP-64.exe",
        root=tmp_path,
        edition="mp",
        diagnostics="",
    )
    calls = []

    monkeypatch.setattr("stata_fix.mcp_server.os.name", "nt")
    monkeypatch.setattr("stata_fix.mcp_server.is_com_available", lambda: len(calls) > 0)
    monkeypatch.setattr("stata_fix.mcp_server.register_stata_com", lambda installation: calls.append(installation) or True)

    runner = create_runner(install)

    assert isinstance(runner, ComStataRunner)
    assert calls == [install]


def test_create_runner_falls_back_to_pystata_when_registration_fails(monkeypatch, tmp_path):
    install = StataInstallation(
        binary=tmp_path / "StataMP-64.exe",
        root=tmp_path,
        edition="mp",
        diagnostics="",
    )

    monkeypatch.setattr("stata_fix.mcp_server.os.name", "nt")
    monkeypatch.setattr("stata_fix.mcp_server.is_com_available", lambda: False)
    monkeypatch.setattr("stata_fix.mcp_server.register_stata_com", lambda installation: False)

    runner = create_runner(install)

    assert runner.backend == "pystata"


def test_stata_attach_existing_switches_cached_runner_to_existing_gui(monkeypatch, tmp_path):
    install = StataInstallation(
        binary=tmp_path / "StataMP-64.exe",
        root=tmp_path,
        edition="mp",
        diagnostics="",
    )
    created = []

    monkeypatch.setattr("stata_fix.mcp_server.discover_stata", lambda: install)
    monkeypatch.setattr("stata_fix.mcp_server.os.name", "nt")
    monkeypatch.setattr("stata_fix.mcp_server.is_com_available", lambda: True)

    def fake_runner(installation, *, attach_existing=False):
        created.append((installation, attach_existing))
        runner = FakeRunner()
        runner.attach = lambda: type("Status", (), {"available": True, "reason": ""})()
        return runner

    monkeypatch.setattr("stata_fix.mcp_server.ComStataRunner", fake_runner)

    result = asyncio.run(stata_attach_existing())

    assert result["attached"] is True
    assert created == [(install, True)]


def test_stata_run_uses_attached_runner_after_attach(monkeypatch, tmp_path):
    install = StataInstallation(
        binary=tmp_path / "StataMP-64.exe",
        root=tmp_path,
        edition="mp",
        diagnostics="",
    )
    attached_runner = FakeRunner()
    attached_runner.attach = lambda: type("Status", (), {"available": True, "reason": ""})()

    monkeypatch.setattr("stata_fix.mcp_server.discover_stata", lambda: install)
    monkeypatch.setattr("stata_fix.mcp_server.os.name", "nt")
    monkeypatch.setattr("stata_fix.mcp_server.is_com_available", lambda: True)
    monkeypatch.setattr("stata_fix.mcp_server.create_runner", lambda installation, *, attach_existing=False: attached_runner)

    asyncio.run(stata_attach_existing())
    result = asyncio.run(stata_run("display 9"))

    assert result == {"rc": 0, "output": "ran: display 9", "error": ""}


def test_stata_attach_existing_does_not_override_runner_when_attach_fails(monkeypatch, tmp_path):
    install = StataInstallation(
        binary=tmp_path / "StataMP-64.exe",
        root=tmp_path,
        edition="mp",
        diagnostics="",
    )
    runner = FakeRunner()
    runner.attach = lambda: type("Status", (), {"available": False, "reason": "no active object"})()

    monkeypatch.setattr("stata_fix.mcp_server.discover_stata", lambda: install)
    monkeypatch.setattr("stata_fix.mcp_server.os.name", "nt")
    monkeypatch.setattr("stata_fix.mcp_server.is_com_available", lambda: True)
    monkeypatch.setattr("stata_fix.mcp_server.create_runner", lambda installation, *, attach_existing=False: runner)

    result = asyncio.run(stata_attach_existing())

    assert result == {
        "attached": False,
        "backend": "com",
        "error": "no active object",
    }


def test_stata_gui_windows_returns_discovered_windows(monkeypatch):
    class FakeAutomation:
        def list_windows(self):
            return [GuiWindowInfo(hwnd=101, pid=202, title="Stata/MP 18.0", process_name="StataMP-64")]

    monkeypatch.setattr("stata_fix.mcp_server.Win32GuiAutomation", lambda: FakeAutomation())

    result = asyncio.run(stata_gui_windows())

    assert result == {
        "windows": [{"hwnd": 101, "pid": 202, "title": "Stata/MP 18.0", "process_name": "StataMP-64"}]
    }


def test_stata_attach_gui_window_switches_runner(monkeypatch, tmp_path):
    install = StataInstallation(
        binary=tmp_path / "StataMP-64.exe",
        root=tmp_path,
        edition="mp",
        diagnostics="",
    )
    runner = FakeRunner()
    runner.attach = lambda: type("Status", (), {"available": True, "reason": ""})()

    monkeypatch.setattr("stata_fix.mcp_server.discover_stata", lambda: install)
    monkeypatch.setattr("stata_fix.mcp_server.GuiStataRunner", lambda installation, hwnd: runner)

    result = asyncio.run(stata_attach_gui_window(101))
    run_result = asyncio.run(stata_run("display 5"))

    assert result["attached"] is True
    assert result["backend"] == "gui"
    assert run_result == {"rc": 0, "output": "ran: display 5", "error": ""}


def test_stata_gui_inspect_returns_accessible_elements(monkeypatch):
    class FakeAutomation:
        def inspect_window(self, hwnd, max_chars=4000):
            return {"hwnd": hwnd, "title": "Stata/MP 18.0", "elements": [{"name": "结果窗口", "text": ""}]}

    monkeypatch.setattr("stata_fix.mcp_server.Win32GuiAutomation", lambda: FakeAutomation())

    result = asyncio.run(stata_gui_inspect(101))

    assert result == {"hwnd": 101, "title": "Stata/MP 18.0", "elements": [{"name": "结果窗口", "text": ""}]}
