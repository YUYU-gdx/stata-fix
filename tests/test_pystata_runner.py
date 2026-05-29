import sys
import types

from stata_fix.discovery import StataInstallation
from stata_fix.pystata_runner import PyStataRunner


def install_fake_pystata(monkeypatch):
    calls = []

    pystata = types.ModuleType("pystata")
    config = types.ModuleType("pystata.config")
    stata = types.SimpleNamespace()

    def init(edition, splash=False):
        calls.append(("init", edition, splash))

    def run(code, echo=False):
        calls.append(("run", code, echo))
        print("fake stata output")

    config.init = init
    stata.run = run
    pystata.config = config
    pystata.stata = stata

    monkeypatch.setitem(sys.modules, "pystata", pystata)
    monkeypatch.setitem(sys.modules, "pystata.config", config)

    return calls


def test_pystata_runner_adds_utilities_path_and_runs_code(tmp_path, monkeypatch):
    calls = install_fake_pystata(monkeypatch)
    install = StataInstallation(
        binary=tmp_path / "StataMP-64.exe",
        root=tmp_path,
        edition="mp",
        diagnostics="",
    )

    result = PyStataRunner(install).run("display 2+2")

    assert str(tmp_path / "utilities") in sys.path
    assert calls == [("init", "mp", False), ("run", "display 2+2", False)]
    assert result.rc == 0
    assert "fake stata output" in result.output


def test_pystata_runner_returns_error_when_no_binary():
    install = StataInstallation(binary=None, root=None, edition=None, diagnostics="not found")

    result = PyStataRunner(install).run("display 2+2")

    assert result.rc == 601
    assert "not found" in result.error
