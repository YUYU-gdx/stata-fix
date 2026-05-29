from pathlib import Path

from stata_fix.paths import runtime_path


def test_runtime_path_defaults_to_current_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    path = runtime_path("example", ".log")

    assert path.parent == tmp_path / ".stata-fix"
    assert path.name.startswith("example-")
    assert path.suffix == ".log"


def test_runtime_path_can_be_overridden(tmp_path, monkeypatch):
    override = tmp_path / "stata-runtime"
    monkeypatch.setenv("STATA_FIX_WORKDIR", str(override))

    path = runtime_path("example", ".do")

    assert path.parent == override
    assert path.suffix == ".do"
