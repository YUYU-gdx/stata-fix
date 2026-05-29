from __future__ import annotations

import os
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class StataInstallation:
    binary: Path | None
    root: Path | None
    edition: str | None
    diagnostics: str


WINDOWS_BINARY_NAMES = (
    "StataNowMP-64.exe",
    "StataNowSE-64.exe",
    "StataNowBE-64.exe",
    "StataMP-64.exe",
    "StataSE-64.exe",
    "StataBE-64.exe",
    "Stata-64.exe",
)

POSIX_BINARY_NAMES = (
    "stata-mp",
    "stata-se",
    "stata-be",
    "stata",
)


def discover_stata(search_roots: Iterable[Path | str] | None = None) -> StataInstallation:
    diagnostics: list[str] = []

    env_path = os.environ.get("STATA_PATH")
    if env_path:
        found = _from_stata_path(env_path, diagnostics)
        if found.binary is not None:
            return found

    found = _from_path(diagnostics)
    if found.binary is not None:
        return found

    roots = [Path(root) for root in search_roots] if search_roots is not None else _default_search_roots()
    for root in roots:
        for binary in _candidate_binaries(root):
            if _is_usable_file(binary):
                return _installation_from_binary(binary, diagnostics)

    diagnostics.append("No Stata executable found in searched locations.")
    if roots:
        diagnostics.append("Searched roots: " + ", ".join(str(root) for root in roots))
    return StataInstallation(None, None, None, "\n".join(diagnostics))


def _from_stata_path(raw_path: str, diagnostics: list[str]) -> StataInstallation:
    path = Path(os.path.expandvars(raw_path.strip().strip("\"'"))).expanduser()
    diagnostics.append(f"STATA_PATH={path}")

    if path.is_file():
        return _installation_from_binary(path, diagnostics)

    if path.is_dir():
        for binary in _binaries_in_directory(path):
            if _is_usable_file(binary):
                return _installation_from_binary(binary, diagnostics)
        diagnostics.append(f"STATA_PATH directory contains no known Stata binary: {path}")
        return StataInstallation(None, None, None, "\n".join(diagnostics))

    diagnostics.append(f"STATA_PATH does not exist: {path}")
    return StataInstallation(None, None, None, "\n".join(diagnostics))


def _from_path(diagnostics: list[str]) -> StataInstallation:
    path_value = os.environ.get("PATH", "")
    if not path_value:
        diagnostics.append("PATH is empty.")
        return StataInstallation(None, None, None, "\n".join(diagnostics))

    for entry in path_value.split(os.pathsep):
        if not entry:
            continue
        directory = Path(os.path.expandvars(entry.strip().strip("\"'"))).expanduser()
        for binary in _binaries_in_directory(directory):
            if _is_usable_file(binary):
                diagnostics.append(f"Found Stata on PATH: {binary}")
                return _installation_from_binary(binary, diagnostics)

    diagnostics.append("No known Stata executable found on PATH.")
    return StataInstallation(None, None, None, "\n".join(diagnostics))


def _default_search_roots() -> list[Path]:
    if os.name == "nt":
        roots: list[Path] = []
        for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
            if base:
                roots.append(Path(base))
        for drive in string.ascii_uppercase:
            root = Path(f"{drive}:\\")
            if root.exists():
                roots.append(root)
        return roots

    if os.uname().sysname == "Darwin":
        return [Path("/Applications"), Path.home() / "Applications"]

    return [Path("/usr/local/stata"), Path("/usr/local"), Path("/opt"), Path("/usr/bin")]


def _candidate_binaries(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return

    for binary in _binaries_in_directory(root):
        yield binary

    if not root.is_dir():
        return

    for child in root.iterdir():
        if not child.is_dir():
            continue
        child_name = child.name.lower()
        if "stata" not in child_name:
            continue
        for binary in _binaries_in_directory(child):
            yield binary
        for grandchild in child.iterdir():
            if not grandchild.is_dir():
                continue
            if "stata" not in grandchild.name.lower():
                continue
            for binary in _binaries_in_directory(grandchild):
                yield binary
        yield from _mac_app_binaries(child)

    if os.name != "nt":
        names = POSIX_BINARY_NAMES
        for name in names:
            yield root / name


def _binaries_in_directory(directory: Path) -> Iterable[Path]:
    names = WINDOWS_BINARY_NAMES if os.name == "nt" else POSIX_BINARY_NAMES
    for name in names:
        yield directory / name


def _mac_app_binaries(stata_dir: Path) -> Iterable[Path]:
    editions = (("StataMP.app", "stata-mp"), ("StataSE.app", "stata-se"), ("StataBE.app", "stata-be"))
    for app_name, binary_name in editions:
        yield stata_dir / app_name / "Contents" / "MacOS" / binary_name


def _is_usable_file(path: Path) -> bool:
    if not path.is_file():
        return False
    if os.name == "nt":
        return True
    return os.access(path, os.X_OK)


def _installation_from_binary(binary: Path, diagnostics: list[str]) -> StataInstallation:
    binary = binary.resolve()
    return StataInstallation(
        binary=binary,
        root=_root_from_binary(binary),
        edition=_edition_from_name(binary.name),
        diagnostics="\n".join(diagnostics),
    )


def _root_from_binary(binary: Path) -> Path:
    parts = binary.parts
    if len(parts) >= 4 and parts[-3:] and parts[-3] == "Contents" and parts[-2] == "MacOS":
        return binary.parents[3]
    return binary.parent


def _edition_from_name(name: str) -> str:
    normalized = name.lower()
    if "mp" in normalized:
        return "mp"
    if "se" in normalized:
        return "se"
    if "be" in normalized:
        return "be"
    return "mp"
