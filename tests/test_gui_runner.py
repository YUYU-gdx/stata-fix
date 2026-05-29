from pathlib import Path

from stata_fix.discovery import StataInstallation
from stata_fix.gui_runner import GuiStataRunner, GuiWindowInfo


class FakeGuiAutomation:
    def __init__(self, log_path: Path | None = None):
        self.log_path = log_path
        self.sent = []
        self.wrapper_text = ""
        self.windows = [GuiWindowInfo(hwnd=100, pid=200, title="Stata/MP 18.0", process_name="StataMP-64")]

    def list_windows(self):
        return self.windows

    def send_command(self, hwnd, command):
        self.sent.append((hwnd, command))
        wrapper = Path(command.removeprefix('do "').removesuffix('"'))
        if wrapper.exists():
            self.wrapper_text = wrapper.read_text(encoding="utf-8")
        if self.log_path is not None:
            self.log_path.write_text("display 42\n42\nstata_fix_rc=0\n", encoding="utf-8")

    def inspect_window(self, hwnd, max_chars=4000):
        return {"hwnd": hwnd, "title": "Stata/MP 18.0", "elements": [{"name": "命令窗口", "text": ""}]}


def test_gui_runner_sends_wrapper_do_to_attached_window_and_returns_log(tmp_path):
    log_path = tmp_path / "result.log"
    code_path = tmp_path / "user.do"
    wrapper_path = tmp_path / "wrapper.do"
    automation = FakeGuiAutomation(log_path)
    install = StataInstallation(binary=tmp_path / "StataMP-64.exe", root=tmp_path, edition="mp", diagnostics="")
    runner = GuiStataRunner(
        install,
        hwnd=100,
        automation=automation,
        log_path_factory=lambda: log_path,
        code_path_factory=lambda: code_path,
        wrapper_path_factory=lambda: wrapper_path,
    )

    result = runner.run("display 42")

    assert result.rc == 0
    assert result.output == "display 42\n42\nstata_fix_rc=0\n"
    assert automation.sent == [(100, f'do "{str(wrapper_path).replace("\\", "/")}"')]
    assert 'log using "' in automation.wrapper_text
    assert "capture noisily do " in automation.wrapper_text


def test_gui_runner_returns_stata_rc_from_log(tmp_path):
    log_path = tmp_path / "result.log"
    automation = FakeGuiAutomation(log_path)

    def send_error_log(hwnd, command):
        automation.sent.append((hwnd, command))
        log_path.write_text("some stata error\nstata_fix_rc=198\n", encoding="utf-8")

    automation.send_command = send_error_log
    install = StataInstallation(binary=tmp_path / "StataMP-64.exe", root=tmp_path, edition="mp", diagnostics="")
    runner = GuiStataRunner(install, hwnd=100, automation=automation, log_path_factory=lambda: log_path)

    result = runner.run("bad command")

    assert result.rc == 198
    assert "some stata error" in result.output


def test_gui_runner_reports_missing_window_without_sending(tmp_path):
    automation = FakeGuiAutomation()
    automation.windows = []
    install = StataInstallation(binary=tmp_path / "StataMP-64.exe", root=tmp_path, edition="mp", diagnostics="")
    runner = GuiStataRunner(install, hwnd=999, automation=automation)

    status = runner.attach()

    assert status.available is False
    assert "not found" in status.reason
    assert automation.sent == []


def test_gui_runner_inspects_uia_visible_content(tmp_path):
    automation = FakeGuiAutomation()
    install = StataInstallation(binary=tmp_path / "StataMP-64.exe", root=tmp_path, edition="mp", diagnostics="")
    runner = GuiStataRunner(install, hwnd=100, automation=automation)

    assert runner.inspect() == {
        "hwnd": 100,
        "title": "Stata/MP 18.0",
        "elements": [{"name": "命令窗口", "text": ""}],
    }
