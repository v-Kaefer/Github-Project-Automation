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
    "scripts/validation/repo_quality.py",
    "scripts/validation/validate_pr_body.py",
    "tests/test_project_setup.py",
)

# Build legacy names at runtime so this validation file does not contain the exact
# forbidden strings it is responsible for finding.
LEGACY_NAMESPACE = "governance"
FORBIDDEN_REFERENCES = (
    f"{LEGACY_NAMESPACE}_bootstrap",
    f"{LEGACY_NAMESPACE}_bootstarp",
    f"{LEGACY_NAMESPACE}.bootstrap.json",
    f"{LEGACY_NAMESPACE}-bootstrap",
)

SCRIPT_REFERENCES = {
    "scripts/validation/repo_quality.py": (
        "Makefile",
    ),
    "scripts/validation/validate_pr_body.py": (
        ".github/workflows/pr-metadata.yml",
    ),
}
INSTALLER_MANIFEST = "project_setup/installer.py"
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


def read_text(relative_path: str, failures: list[str]) -> str | None:
    path = ROOT / relative_path
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(
            f"Script reference owner is missing: {relative_path}",
            failures,
            "Restore the file or remove its script-reference contract from repo_quality.py.",
        )
    except UnicodeDecodeError:
        fail(
            f"Script reference owner is not valid UTF-8 text: {relative_path}",
            failures,
            "Save the file as UTF-8 and run `make check` again.",
        )
    return None


def validate_script_references(failures: list[str]) -> None:
    print("==> Validating script entry points")
    installer_text = read_text(INSTALLER_MANIFEST, failures)

    for script_path, owners in SCRIPT_REFERENCES.items():
        script = ROOT / script_path
        if not script.is_file():
            fail(
                f"Referenced script is missing: {script_path}",
                failures,
                "Restore the script before using its Makefile or workflow entry point.",
            )
            continue

        print(f"script={script_path} exists=yes")
        for owner in owners:
            owner_text = read_text(owner, failures)
            if owner_text is None:
                continue
            if script_path not in owner_text:
                fail(
                    f"{owner} no longer references {script_path}",
                    failures,
                    f"Restore the `{script_path}` invocation in {owner} or update SCRIPT_REFERENCES intentionally.",
                )
            else:
                print(f"  referenced_by={owner} status=ok")

        if installer_text is not None:
            if script_path not in installer_text:
                fail(
                    f"Installer does not copy required script: {script_path}",
                    failures,
                    f"Add `{script_path}` to CORE_TEMPLATE_FILES in {INSTALLER_MANIFEST}.",
                )
            else:
                print(f"  installer={INSTALLER_MANIFEST} status=ok")


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

    validate_script_references(failures)

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
        expected_entry_points = {
            "project-setup": "project_setup.cli:main",
            "project_setup": "project_setup.cli:main",
        }
        for command, expected in expected_entry_points.items():
            if scripts.get(command) != expected:
                fail(
                    f"pyproject.toml does not expose `{command} = {expected}`.",
                    failures,
                    f"Restore the {command} entry point under [project.scripts].",
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

    print(
        "Repository quality checks passed: required files, committed artifacts, script references, JSON, "
        "and package metadata are valid."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
