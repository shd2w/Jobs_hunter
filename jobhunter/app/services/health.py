"""Health service — system health checks."""

from __future__ import annotations

import logging
from pathlib import Path

from jobhunter.app.result import Err, Ok, Result

logger = logging.getLogger(__name__)


class HealthService:
    """Checks the health of the application and its dependencies."""

    def __init__(self):
        self.checks: list[str] = []

    def check(self) -> Result[dict]:
        """Run all health checks.

        Returns Ok(health_report) with status and per-check results.
        """
        report: dict = {"status": "ok", "checks": {}}

        # Python version
        import sys

        py_ok = sys.version_info >= (3, 12)
        report["checks"]["python"] = {
            "ok": py_ok,
            "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        }
        if not py_ok:
            report["status"] = "degraded"

        # Config files
        for cfg in ("config/profile.yml", "config/portals.yml"):
            exists = Path(cfg).exists()
            report["checks"][cfg] = {"ok": exists, "exists": exists}
            if not exists:
                report["status"] = "degraded"

        # Data directory
        data_dir = Path("data")
        data_ok = data_dir.exists() and data_dir.is_dir()
        report["checks"]["data_dir"] = {"ok": data_ok, "exists": data_ok}
        if not data_ok:
            report["status"] = "degraded"

        # WeasyPrint availability
        try:
            import weasyprint  # noqa: F401

            report["checks"]["weasyprint"] = {"ok": True}
        except ImportError:
            report["checks"]["weasyprint"] = {"ok": False, "note": "not installed"}
            report["status"] = "degraded"

        # GTK/Pango runtime (Windows)
        import os

        gtk_dll = os.path.exists("C:\\msys64\\mingw64\\bin\\libgtk-3-0.dll")
        report["checks"]["gtk_runtime"] = {"ok": gtk_dll, "path": "C:\\msys64\\mingw64\\bin"}
        if not gtk_dll:
            report["status"] = "degraded"

        return Ok(report)
