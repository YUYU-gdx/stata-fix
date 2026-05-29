from __future__ import annotations

import contextlib
import io
import sys
from dataclasses import dataclass

from .discovery import StataInstallation


@dataclass(frozen=True)
class StataRunResult:
    rc: int
    output: str
    error: str


class PyStataRunner:
    backend = "pystata"

    def __init__(self, installation: StataInstallation):
        self.installation = installation
        self._initialized = False

    def run(self, code: str, *, echo: bool = False) -> StataRunResult:
        if self.installation.binary is None or self.installation.root is None or self.installation.edition is None:
            return StataRunResult(rc=601, output="", error=self.installation.diagnostics)

        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                self._ensure_initialized()
                from pystata import stata

                stata.run(code, echo=echo)
        except Exception as exc:
            return StataRunResult(rc=1, output=output.getvalue(), error=str(exc))

        return StataRunResult(rc=0, output=output.getvalue(), error="")

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        utilities = str(self.installation.root / "utilities")
        if utilities not in sys.path:
            sys.path.insert(0, utilities)

        try:
            import stata_setup

            stata_setup.config(str(self.installation.root), self.installation.edition)
        except ModuleNotFoundError:
            import pystata.config

            pystata.config.init(self.installation.edition, splash=False)

        self._initialized = True
