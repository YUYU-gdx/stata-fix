# stata-fix

`stata-fix` is an MCP server for running local Stata code.
It is designed to work without asking users to hand-write a Stata install path.
On Windows, it defaults to controlling a separate Stata GUI through Stata Automation COM when available.
Temporary do-files and logs are written under the MCP process working directory in `.stata-fix` by default.

## Install

For a local checkout:

```powershell
uv tool install .
```

After publishing to a package index:

```powershell
uv tool install stata-fix
```

Or directly from a Git repository:

```powershell
uv tool install git+https://github.com/<owner>/<repo>.git
```

After installation, MCP clients can start the server with:

```text
stata-fix-mcp
```

During development, run it from a checkout with:

```powershell
uv run stata-fix-mcp
```

## Codex Plugin

This repository includes a Codex plugin artifact at:

```text
plugins/stata-fix
```

The plugin bundles:

- `skills/stata/SKILL.md`
- `.mcp.json`, which launches `uvx --from git+https://github.com/YUYU-gdx/stata-fix.git stata-fix-mcp`
- `.codex-plugin/plugin.json`

Codex users can install the plugin from the repository path:

```powershell
npx codex-marketplace add <owner>/<repo>/plugins/stata-fix --plugin
```

For local testing from this checkout:

```powershell
npx codex-marketplace add <repo-path>/plugins/stata-fix --plugin
```

The plugin is the preferred distribution path for Codex because it installs the skill and wires the MCP server together.

## MCP Client Configuration

After installing the tool, configure the MCP client to launch:

```json
{
  "mcpServers": {
    "stata_fix": {
      "command": "stata-fix-mcp",
      "args": []
    }
  }
}
```

For development from a source checkout, use:

```json
{
  "mcpServers": {
    "stata_fix": {
      "command": "uv",
      "args": ["run", "--project", "<repo-path>", "stata-fix-mcp"]
    }
  }
}
```

Do not hardcode a developer's local repository path in shared configuration. Use an installed `stata-fix-mcp` command for normal users.

## User Setup Checklist

1. Install Stata locally and make sure it can launch normally.
2. Install this MCP server.
3. Add the MCP client configuration above.
4. Restart the MCP client.
5. Ask the assistant to run `stata_detect`.

On Windows, the best default experience uses Stata Automation COM. If Stata is found but COM is not registered, the MCP server first attempts to run Stata's `/Register` step automatically, but only when no Stata process is already running. If a user is actively using Stata, the server will not auto-register in order to avoid disrupting that session.

If `stata_detect` still reports `backend="pystata"` even though Stata is installed, close Stata and register Stata Automation COM once from an elevated PowerShell:

```powershell
Start-Process -FilePath "<path-to-StataMP-64.exe>" -ArgumentList "/Register" -Verb RunAs -Wait
```

Most users should not need to set `STATA_PATH`. Use it only for unusual installations that automatic discovery cannot find.

By default, runtime files are written to:

```text
<codex-working-directory>/.stata-fix
```

Set `STATA_FIX_WORKDIR` only if you need to override that location.

## Stata Discovery

The server discovers Stata automatically in this order:

1. `STATA_PATH`, if it is already set.
2. Known Stata executable names on the system `PATH`.
3. Common install roots for Windows, macOS, and Linux.

Users should not need to write any configuration for ordinary Stata installs.
`STATA_PATH` is only an escape hatch for unusual installations.

## Execution Backends

Windows default: COM GUI backend.

When `pywin32` and Stata Automation COM are available, `stata_run` opens or reuses a dedicated Stata Automation instance created by the MCP server. It uses `DispatchEx`, so it does not attach to a Stata GUI window the user already has open for separate work.

Each command is wrapped with a temporary Stata log. The command is visible in the dedicated Stata GUI, and the log text is returned to the MCP client.

Fallback: `pystata`.

If COM is not available, the server falls back to Python `pystata`, which runs Stata inside the MCP server process and returns captured output to the client without showing commands in the user's Stata GUI.

Manual GUI backend: explicit only.

The GUI backend is used only after the user explicitly asks to control a manually opened Stata window and calls `stata_attach_gui_window`. A visible Stata window does not change the default backend.

## MCP Tools

`stata_detect`

Detects the local Stata installation, backend, and runtime directory that the server will use.

`stata_run`

Runs Stata code and returns:

- `rc`: return code
- `output`: captured Stata output
- `error`: error text, if execution failed

Example code sent to `stata_run`:

```stata
clear all
sysuse auto, clear
summarize price mpg weight
```

With the COM GUI backend, commands are visible in the dedicated Stata GUI and the temporary log is returned as `output`.

`stata_attach_existing`

Explicitly attaches the MCP server to an existing Stata Automation GUI session on Windows. This is never the default because commands sent after attachment can modify the user's active Stata state.

After attachment, `stata_run` targets that existing session and still captures new command output through a temporary log. It can query current state such as `describe`, `estimates replay`, `return list`, `ereturn list`, macros, matrices, and the current working directory.

It cannot reliably recover all text that was already shown in the Results window before attachment unless the user had already written that output to a Stata log file.

`stata_gui_windows`

Lists visible Stata GUI windows by HWND, PID, title, and process name. Use this when the user explicitly wants to target a manually opened Stata window.

`stata_attach_gui_window`

Switches future `stata_run` calls to a selected visible Stata GUI window. This bypasses COM active-object attachment by controlling the window UI directly. The backend sends a temporary wrapper do-file to the selected GUI and reads new command output from a temporary text log.

`stata_gui_inspect`

Returns Win32/UI-visible window content for a selected Stata GUI. This is not equivalent to browser DOM access: Stata's Results pane exposes window/control structure, but the Results text history is generally not available as accessible text. Use `stata_run` after GUI attachment to query current state or capture new output.
