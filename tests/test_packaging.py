import subprocess


def test_console_script_is_available_through_uv_run():
    result = subprocess.run(
        ["uv", "run", "--project", ".", "python", "-c", "import importlib.metadata as m; print(any(ep.name == 'stata-fix-mcp' for ep in m.entry_points(group='console_scripts')))"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True"
