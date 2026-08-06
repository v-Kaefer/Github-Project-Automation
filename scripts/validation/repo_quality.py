#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tomllib


SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
REQUIRED_PATHS = (
    ".env.example",
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
TEXT_SUFFIXES = {".py", ".md", ".yml", ".yaml", ".json", ".toml", ".txt", ".sh", ".example"}


def fail(message: str, failures: list[str], fix: str | None = None) -> None:
    failures.append(message)
    print(f"ERROR: {message}", file=sys.stderr)
    if fix:
        print(f"  Fix: {fix}", file=sys.stderr)


def tracked_files(failures: list[str]) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        fail(
            "Git is not installed or is not available on PATH.",
            failures,
            "Install Git, open a new terminal, and run `make check` again.",
        )
        return []

    if result.returncode != 0:
        details = result.stderr.decode("utf-8", errors="replace").strip() or "unknown Git error"
        fail(
            f"Could not inspect committed files: {details}",
            failures,
            "Run this command from a Git working tree and confirm that `git status` succeeds.",
        )
        return []

    names = result.stdout.decode("utf-8", errors="surrogateescape").split("\0")
    return [ROOT / name for name in names if name]


def main() -> int:
    failures: list[str] = []

    print("==> Checking required repository files")
    for relative_path in REQUIRED_PATHS:
        if not (ROOT / relative_path).is_file():
            fail(
                f"Required file is missing: {relative_path}",
                failures,
                "Restore the file from the project_setup template or rerun the installer.",
            )

    print("==> Checking committed files")
    for path in tracked_files(failures):
        relative_path = path.relative_to(ROOT)
        relative = relative_path.as_posix()

        if "__pycache__" in relative_path.parts or path.suffix in {".pyc", ".pyo"}:
            fail(
                f"Generated Python artifact is committed: {relative}",
                failures,
                f"Run `git rm --cached -- {relative}` and then `make clean`. Local untracked cache files are allowed.",
            )
            continue

        for forbidden in FORBIDDEN_REFERENCES:
            if forbidden in relative:
                fail(
                    f"Legacy reference '{forbidden}' found in path: {relative}",
                    failures,
                    "Rename or remove the legacy path so only project_setup remains.",
                )

        if not path.is_file() or (path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"Makefile", ".env.example"}):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for forbidden in FORBIDDEN_REFERENCES:
            if forbidden in text:
                fail(
                    f"Legacy reference '{forbidden}' found in {relative}",
                    failures,
                    "Replace the reference with project_setup or remove obsolete documentation.",
                )

    print("==> Validating JSON configuration")
    json_paths = [ROOT / "project_setup.json", *sorted((ROOT / "config").rglob("*.json"))]
    for path in json_paths:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            fail(
                f"JSON configuration is missing: {path.relative_to(ROOT)}",
                failures,
                "Restore the file or update project_setup.json to reference an existing manifest.",
            )
        except json.JSONDecodeError as exc:
            fail(
                f"Invalid JSON in {path.relative_to(ROOT)} at line {exc.lineno}, column {exc.colno}: {exc.msg}",
                failures,
                "Correct the JSON syntax and run `make check` again.",
            )

    print("==> Validating Python package metadata")
    try:
        with (ROOT / "pyproject.toml").open("rb") as file:
            pyproject = tomllib.load(file)
        scripts = pyproject.get("project", {}).get("scripts", {})
        if scripts.get("project-setup") != "project_setup.cli:main":
            fail(
                "pyproject.toml does not expose `project-setup = project_setup.cli:main`.",
                failures,
                "Restore the project-setup entry point under [project.scripts].",
            )
    except FileNotFoundError:
        fail("pyproject.toml is missing.", failures, "Restore pyproject.toml before running the checks.")
    except tomllib.TOMLDecodeError as exc:
        fail(f"Invalid pyproject.toml: {exc}", failures, "Correct the TOML syntax and run `make check` again.")

    if failures:
        print("", file=sys.stderr)
        print(f"Repository quality failed with {len(failures)} error(s).", file=sys.stderr)
        print("Review each `Fix:` line above. No remote GitHub changes were made.", file=sys.stderr)
        return 1

    print("Repository quality checks passed: required files, committed artifacts, JSON, and package metadata are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
