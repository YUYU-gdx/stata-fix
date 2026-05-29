from pathlib import Path

from stata_fix.discovery import discover_stata


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    return path


def test_discover_stata_prefers_valid_stata_path_file(tmp_path, monkeypatch):
    binary = touch(tmp_path / "StataMP-64.exe")
    monkeypatch.setenv("STATA_PATH", str(binary))

    found = discover_stata(search_roots=[])

    assert found.binary == binary
    assert found.root == tmp_path
    assert found.edition == "mp"


def test_discover_stata_accepts_valid_stata_path_directory(tmp_path, monkeypatch):
    binary = touch(tmp_path / "StataSE-64.exe")
    monkeypatch.setenv("STATA_PATH", str(tmp_path))

    found = discover_stata(search_roots=[])

    assert found.binary == binary
    assert found.root == tmp_path
    assert found.edition == "se"


def test_discover_stata_scans_search_roots_when_env_missing(tmp_path, monkeypatch):
    install = tmp_path / "Stata18"
    binary = touch(install / "StataMP-64.exe")
    monkeypatch.delenv("STATA_PATH", raising=False)

    found = discover_stata(search_roots=[tmp_path])

    assert found.binary == binary
    assert found.root == install
    assert found.edition == "mp"


def test_discover_stata_finds_binary_on_path_without_user_config(tmp_path, monkeypatch):
    binary = touch(tmp_path / "StataMP-64.exe")
    monkeypatch.delenv("STATA_PATH", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))

    found = discover_stata(search_roots=[])

    assert found.binary == binary
    assert found.root == tmp_path
    assert found.edition == "mp"


def test_discover_stata_finds_statanow_binary_in_nested_vendor_directory(tmp_path, monkeypatch):
    install = tmp_path / "StataCorp" / "StataNow19"
    binary = touch(install / "StataNowMP-64.exe")
    monkeypatch.delenv("STATA_PATH", raising=False)

    found = discover_stata(search_roots=[tmp_path])

    assert found.binary == binary
    assert found.root == install
    assert found.edition == "mp"


def test_discover_stata_reports_checked_locations(tmp_path, monkeypatch):
    monkeypatch.setenv("STATA_PATH", str(tmp_path / "missing.exe"))

    found = discover_stata(search_roots=[])

    assert found.binary is None
    assert "STATA_PATH" in found.diagnostics
    assert "missing.exe" in found.diagnostics
