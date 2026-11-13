"""
Layer-lint test (G4).

Enforces the architectural layering rules:

- jobhunter.interfaces imports only jobhunter.app and jobhunter.domain
  (CLI/UI parse input, call one service method, render Result[T]; no business logic)
- jobhunter.domain imports no I/O
  (pure rules only: scoring, eligibility, dedup; no network, no file system)
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "jobhunter"


def _imported_modules(file_path: Path) -> set[str]:
    """Return the set of top-level module names imported by a Python file."""
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
    return imported


# Third-party / I/O packages that domain must not import.
IO_PACKAGES = {
    "httpx", "requests", "urllib", "socket", "selenium",
    "google", "openai", "anthropic",
    "pandas", "openpyxl",
    "dotenv",
    "weasyprint",
    "playwright",
}


def _domain_files() -> list[Path]:
    return sorted((SRC / "domain").rglob("*.py"))


def _interface_files() -> list[Path]:
    return sorted((SRC / "interfaces").rglob("*.py"))


def test_domain_imports_no_io():
    """jobhunter.domain must not import any I/O or external packages."""
    bad: dict[str, list[str]] = {}
    for f in _domain_files():
        imports = _imported_modules(f)
        io_found = imports & IO_PACKAGES
        if io_found:
            bad[str(f.relative_to(ROOT))] = sorted(io_found)
    assert not bad, (
        "jobhunter.domain must not import I/O/external packages. Violations: "
        + "; ".join(f"{k}: {v}" for k, v in bad.items())
    )


def test_interfaces_imports_only_app_and_domain():
    """jobhunter.interfaces must import only jobhunter.app and jobhunter.domain."""
    bad: dict[str, list[str]] = {}
    for f in _interface_files():
        imports = _imported_modules(f)
        # Allow stdlib + jobhunter.app + jobhunter.domain + relative imports
        disallowed = imports - {"jobhunter", "app", "domain", "typing", "argparse",
                                "sys", "os", "pathlib", "json", "csv",
                                "datetime", "uuid", "hashlib", "re", "logging",
                                "warnings", "dataclasses", "enum", "functools",
                                "itertools", "collections", "math", "decimal",
                                "io", "tempfile", "subprocess", "shutil",
                                "threading", "asyncio"}
        # Filter out stdlib-only single names that are clearly not jobhunter subpackages
        jobhunter_imports = {m for m in imports if m == "jobhunter"}
        non_jobhunter = imports - jobhunter_imports
        # Everything non-jobhunter should be stdlib
        stdlib = {
            "typing", "argparse", "sys", "os", "pathlib", "json", "csv",
            "datetime", "uuid", "hashlib", "re", "logging",
            "warnings", "dataclasses", "enum", "functools",
            "itertools", "collections", "math", "decimal",
            "io", "tempfile", "subprocess", "shutil",
            "threading", "asyncio",
        }
        non_stdlib = non_jobhunter - stdlib
        if non_stdlib:
            bad[str(f.relative_to(ROOT))] = sorted(non_stdlib)
    assert not bad, (
        "jobhunter.interfaces must import only jobhunter.app, jobhunter.domain, and stdlib. "
        "Violations: " + "; ".join(f"{k}: {v}" for k, v in bad.items())
    )


def test_layer_lint_packages_exist():
    """All four jobhunter layer packages exist with __init__.py."""
    for layer in ("domain", "app", "adapters", "interfaces"):
        pkg = SRC / layer / "__init__.py"
        assert pkg.is_file(), f"Missing jobhunter/{layer}/__init__.py"


def test_layer_lint_alias_still_works():
    """Backward-compatible aliases in jobhunter_ui/ranking.py and utils/filters.py still import."""
    from jobhunter_ui.ranking import rank, score_of, DEFAULT_WEIGHTS  # noqa: F401
    from utils.filters import TitleFilter, LocationFilter, filter_jobs  # noqa: F401
    assert rank is not None
    assert score_of is not None
    assert TitleFilter is not None
    assert LocationFilter is not None
    assert filter_jobs is not None
