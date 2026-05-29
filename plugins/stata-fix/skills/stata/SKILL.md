---
name: stata
description: Use when running Stata code, checking Stata availability, or helping a user analyze data with the local stata-fix MCP server.
---

# Stata via stata-fix MCP

Use this skill whenever the user asks to run Stata, inspect whether Stata is available, or execute a Stata analysis workflow.

## Default Path

Prefer the local MCP server tools exposed by this repository:

1. Call `stata_detect` when you need to confirm which Stata installation will be used.
2. Call `stata_run` to execute Stata code.
3. Do not call any attach tool for ordinary Stata analysis requests.
4. Call `stata_attach_existing` only when the user explicitly asks to attach to an existing Stata Automation COM session.
5. Call `stata_gui_windows` and `stata_attach_gui_window` only when the user explicitly asks to control, take over, or attach to a manually opened Stata GUI window.
6. Use `stata_gui_inspect` to report GUI-accessible window/control text, while explaining that Results history is usually not exposed like browser DOM text.
7. Report the returned `rc`, `output`, and `error` fields clearly.

Do not ask the user to create temporary do-files or manually configure Stata paths before trying the MCP. The MCP is responsible for local discovery.

On Windows, expect the default backend to be `com` when Stata Automation COM and `pywin32` are available. If Stata is found but COM is not registered, the MCP attempts Stata's `/Register` step automatically before falling back, but only when no Stata process is already running. Do not auto-register while the user is actively using Stata. This backend creates a dedicated Stata GUI instance for the MCP server and does not attach to a Stata window the user already has open. It also wraps each run in a temporary Stata log so the command is visible in the GUI and the log text is returned to Codex.

Runtime do-files and logs are written under the MCP process working directory in `.stata-fix` by default. `stata_detect` reports this as `runtime_dir`.

Priority rule: default to COM. Use the GUI backend only after the user explicitly asks to control a manually opened Stata window. Do not switch to GUI merely because a Stata GUI is visible.

## Discovery Contract

The MCP discovers Stata automatically in this order:

1. `STATA_PATH`, if already present in the environment.
2. Known Stata executable names on the system `PATH`.
3. Common install roots for the operating system.

`STATA_PATH` is an override for advanced troubleshooting, not the normal setup path. Do not require ordinary users to set it.

Recognized Windows executable names include:

```text
StataNowMP-64.exe
StataNowSE-64.exe
StataNowBE-64.exe
StataMP-64.exe
StataSE-64.exe
StataBE-64.exe
Stata-64.exe
```

Recognized POSIX executable names include:

```text
stata-mp
stata-se
stata-be
stata
```

## Running Code

Use `stata_run` with complete Stata code:

```stata
clear all
sysuse auto, clear
summarize price mpg weight
```

If the user gives a file path, use Stata commands such as `use`, `import delimited`, or `import excel` inside `stata_run`. Prefer absolute paths when they are known.

When `stata_detect` reports `backend="com"`, commands are sent to the dedicated Stata GUI and the temporary Stata log is returned in `output`.

When `stata_detect` reports `backend="pystata"`, Stata runs inside the MCP server process and output is captured directly for Codex.

## Attaching to an Existing GUI

Do not attach to a user's existing Stata GUI by default. Only call `stata_attach_existing` when the user explicitly requests it.

After attachment, use `stata_run` for read-only status queries first:

```stata
describe
capture noisily estimates replay
return list
ereturn list
macro list _all
pwd
```

Explain the limitation clearly: attaching can query the current Stata state, but it cannot reliably recover all Results-window text that appeared before attachment unless that text was already written to a Stata log file.

## Controlling a Manual GUI Window

Use this path only when the user explicitly asks to control, take over, or attach to a manually opened Stata GUI window:

1. Call `stata_gui_windows`.
2. Pick the target HWND. If there are multiple windows, ask the user which one to use.
3. Call `stata_attach_gui_window` with that HWND.
4. Run code with `stata_run`.

This backend controls the selected GUI through the Windows UI. It sends a temporary wrapper do-file to Stata and reads back the temporary text log. It does not close the selected Stata window.

Do not promise direct Results-window history extraction. `stata_gui_inspect` can show controls and accessible text, but Stata's Results pane is not exposed like a web page DOM.

## Diagnostics

If `stata_detect` returns `found=false` or `stata_run` returns a nonzero `rc`:

1. Show the diagnostic text returned by the MCP.
2. Explain that Stata must be installed locally and licensed on the user's machine.
3. If Windows reports `backend="pystata"` even though Stata is installed, explain that automatic COM registration is skipped while Stata is already running. Suggest closing Stata and running Stata `/Register` from elevated PowerShell if needed.
4. Suggest adding Stata's install directory to the system `PATH` only if automatic install-root discovery failed.
5. Mention `STATA_PATH` only as a last-resort override for unusual installations.

## Output Handling

For successful runs, summarize the important statistical results rather than pasting all output unless the user asks for raw logs. Preserve exact numbers for regression tables, test statistics, p-values, and sample sizes.

For errors, include the Stata return code and the smallest useful excerpt of the error message. If the error is caused by missing data files, bad variable names, or package availability, propose the next concrete command to diagnose it.

## Installing the MCP

For portable use, install the package so MCP clients can launch the console script directly:

```powershell
uv tool install .
```

Then the server command is:

```text
stata-fix-mcp
```

Avoid MCP client examples that point at a developer's local repository path. If a source checkout must be used during development, describe it as `<repo-path>` rather than a real machine-specific path.
