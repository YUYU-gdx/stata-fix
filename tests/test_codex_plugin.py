import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "stata-fix"


def test_codex_plugin_manifest_is_valid_json():
    manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))

    assert manifest["name"] == "stata-fix"
    assert manifest["mcp"] == ".mcp.json"
    assert manifest["skills"] == "skills"
    assert manifest["author"] == {"name": "stata-fix contributors"}


def test_codex_plugin_mcp_launches_published_console_script():
    config = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))

    server = config["mcpServers"]["stata_fix"]
    assert server == {
        "command": "uvx",
        "args": ["--from", "git+https://github.com/YUYU-gdx/stata-fix.git", "stata-fix-mcp"],
    }


def test_plugin_skill_matches_root_skill():
    root_skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    plugin_skill = (PLUGIN / "skills" / "stata" / "SKILL.md").read_text(encoding="utf-8")

    assert plugin_skill == root_skill
