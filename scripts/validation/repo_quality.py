#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys
import tomllib


SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
REQUIRED_PATHS = (
    "Makefile",
    "README.md",
    "LICENSE",
    "pyproject.toml",
    "project_setup.json",
    "project_setup/__init__.py",
    "project_setup/__main__.py",
    "project_setup/cli.py",
    "project_setup/discovery.py",
    "project_setup/runner.py",
    "project_setup/installer.py",
    "project_setup/github.py",
    ".github/workflows/project-setup.yml",
    ".github/workflows/auto-label.yml",
    ".github/workflows/pr-metadata.yml",
    ".github/workflows/repo-quality.yml",
    "scripts/validation/validate_pr_body.py",
    "tests/test_project_setup.py",
)
FORBIDDEN_REFERENCES = (
    "governance_bootstrap",
    "governance_bootstarp",
    "governance.bootstrap.json",
    "governance-bootstrap",
)
TEXT_SUFFIXES = {".py", ".md", ".yml", ".yaml", ".json", ".toml", ".txt", ".sh"}


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)
    print(f"ERROR: {message}", file=sys.stderr)


def main() -> int:
    failures: list[str] = []
    for relative_path in REQUIRED_PATHS:
        if not (ROOT / relative_path).is_file():
            fail(f"required file is missing: {relative_path}", failures)

    for path in ROOT.rglob("*"):
        if path.resolve() == SELF or ".git" in path.parts or not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            fail(f"generated Python artifact is tracked: {path.relative_to(ROOT)}", failures)
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != "Makefile":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative = str(path.relative_to(ROOT))
        for forbidden in FORBIDDEN_REFERENCES:
            if forbidden in text or forbidden in relative:
                fail(f"legacy reference '{forbidden}' found in {relative}", failures)

    for path in [ROOT / "project_setup.json", *sorted((ROOT / "config").rglob("*.json"))]:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            fail(f"invalid JSON in {path.relative_to(ROOT)}: {exc}", failures)

    try:
        with (ROOT / "pyproject.toml").open("rb") as file:
            pyproject = tomllib.load(file)
        scripts = pyproject.get("project", {}).get("scripts", {})
        if scripts.get("project-setup") != "project_setup.cli:main":
            fail("pyproject.toml does not expose project-setup = project_setup.cli:main", failures)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        fail(f"invalid pyproject.toml: {exc}", failures)

    if failures:
        print(f"Repository quality failed with {len(failures)} error(s).", file=sys.stderr)
        return 1
    print("Repository quality checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
