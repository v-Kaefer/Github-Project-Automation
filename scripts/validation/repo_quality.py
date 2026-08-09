#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tomllib


SELF = Path(__file__).resolve()
ROOT = SELF.parents[2]
TOOL_REPOSITORY_MARKER = "tests/test_project_setup.py"

# Files that are part of the reusable embedded project_setup contract.
CORE_REQUIRED_PATHS = (
    ".env.example",
    "Makefile",
    "AI_SETUP_GUIDE.md",
    ".github/ISSUE_TEMPLATE/bug-report.yml",
    ".github/ISSUE_TEMPLATE/task-sub-issue.yml",
    ".github/ISSUE_TEMPLATE/user-story.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/pull_request_template.md",
    ".github/workflows/project-setup.yml",
    ".github/workflows/auto-label.yml",
    ".github/workflows/pr-metadata.yml",
    ".github/workflows/qa-source-branch.yml",
    ".github/workflows/main-source-branch.yml",
    "config/project/labels.json",
    "config/project/milestones.json",
    "config/project/project-definition.json",
    "config/stories/backlog-manifest.json",
    "project_setup.json",
    "project_setup/__init__.py",
    "project_setup/__main__.py",
    "project_setup/cli.py",
    "project_setup/discovery.py",
    "project_setup/runner.py",
    "project_setup/installer.py",
    "project_setup/github.py",
    "scripts/validation/repo_quality.py",
    "scripts/validation/validate_pr_body.py",
)

# Files that exist only in the source repository of GitHub Project Setup.
TOOL_REPOSITORY_REQUIRED_PATHS = (
    "README.md",
    "README.pt-BR.md",
    "LICENSE",
    "NOTICE",
    "pyproject.toml",
    ".github/workflows/repo-quality.yml",
    ".github/workflows/qa-validation.yml",
    ".github/workflows/qa-live.yml",
    ".github/workflows/qa-issue-generation.yml",
    "docs/repo/qa-policy.md",
    "docs/repo/qa-policy.pt-BR.md",
    "tests/test_project_setup.py",
    "tests/test_script_references.py",
    "tests/test_branch_promotion.py",
    "tests/test_qa_workflows.py",
    "tests/qa/test_cli_e2e.py",
    "tests/qa/live_sandbox.py",
    "tests/qa/live_issue_generation.py",
)

# License/attribution are installed under a namespace so target repositories keep
# their own top-level licensing model.
EMBEDDED_REPOSITORY_REQUIRED_PATHS = (
    "licenses/project_setup/LICENSE",
    "licenses/project_setup/NOTICE",
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
SCRIPT_SUFFIXES = {".py", ".sh", ".ps1"}


def fail(message: str, failures: list[str], fix: str | None = None) -> None:
    failures.append(message)
    print(f"ERROR: {message}", file=sys.stderr)
    if fix:
        print(f"  Fix: {fix}", file=sys.stderr)


def is_tool_repository() -> bool:
    return (ROOT / TOOL_REPOSITORY_MARKER).is_file()


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


def validate_script_references(failures: list[str], *, strict_repository_scan: bool) -> None:
    print("==> Validating project_setup script entry points")
    installer_text = read_text(INSTALLER_MANIFEST, failures)
    registered_scripts = set(SCRIPT_REFERENCES)

    # Only the tool's own source repository owns every script under scripts/. A
    # target repository may legitimately have unrelated scripts of its own.
    if strict_repository_scan:
        discovered_scripts = {
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "scripts").rglob("*")
            if path.is_file() and path.suffix.lower() in SCRIPT_SUFFIXES
        }
        for script_path in sorted(discovered_scripts - registered_scripts):
            fail(
                f"Script has no registered caller contract: {script_path}",
                failures,
                "Add the script and its Makefile/workflow caller to SCRIPT_REFERENCES in repo_quality.py.",
            )
        for script_path in sorted(registered_scripts - discovered_scripts):
            fail(
                f"Registered script is missing from the scripts directory: {script_path}",
                failures,
                "Restore the script or remove the obsolete SCRIPT_REFERENCES entry.",
            )

    for script_path, owners in SCRIPT_REFERENCES.items():
        script = ROOT / script_path
        if not script.is_file():
            fail(
                f"Required project_setup script is missing: {script_path}",
                failures,
                "Restore the managed validation script or rerun the installer.",
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


def validate_json_configuration(failures: list[str], *, tool_repository: bool) -> None:
    print("==> Validating JSON configuration")
    if tool_repository:
        json_paths = [ROOT / "project_setup.json", *sorted((ROOT / "config").rglob("*.json"))]
    else:
        json_paths = [
            ROOT / "project_setup.json",
            ROOT / "config/project/labels.json",
            ROOT / "config/project/milestones.json",
            ROOT / "config/project/project-definition.json",
            ROOT / "config/stories/backlog-manifest.json",
        ]

    for path in json_paths:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            fail(
                f"JSON configuration is missing: {path.relative_to(ROOT)}",
                failures,
                "Restore the managed file or update project_setup.json to reference an existing manifest.",
            )
        except json.JSONDecodeError as exc:
            fail(
                f"Invalid JSON in {path.relative_to(ROOT)} at line {exc.lineno}, column {exc.colno}: {exc.msg}",
                failures,
                "Correct the JSON syntax and run `make check` again.",
            )


def validate_tool_package_metadata(failures: list[str]) -> None:
    print("==> Validating Python package metadata")
    try:
        with (ROOT / "pyproject.toml").open("rb") as file:
            pyproject = tomllib.load(file)
        project = pyproject.get("project", {})
        if project.get("name") != "github-project-setup":
            fail(
                "pyproject.toml does not identify the source package as github-project-setup.",
                failures,
                "Restore the project name under [project].",
            )
        scripts = project.get("scripts", {})
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


def main() -> int:
    failures: list[str] = []
    tool_repository = is_tool_repository()
    mode = "tool-source" if tool_repository else "embedded-target"
    print(f"repository_quality_mode={mode}")

    required_paths = [*CORE_REQUIRED_PATHS]
    required_paths.extend(TOOL_REPOSITORY_REQUIRED_PATHS if tool_repository else EMBEDDED_REPOSITORY_REQUIRED_PATHS)

    print("==> Checking required repository files")
    for relative_path in required_paths:
        if not (ROOT / relative_path).is_file():
            fail(
                f"Required file is missing: {relative_path}",
                failures,
                "Restore the managed file or rerun the project_setup installer.",
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

        # Legacy namespace cleanup is a source-repository migration contract. Do
        # not impose it on unrelated files owned by target repositories.
        if tool_repository:
            for forbidden in FORBIDDEN_REFERENCES:
                if forbidden in relative:
                    fail(
                        f"Legacy reference '{forbidden}' found in path: {relative}",
                        failures,
                        "Rename or remove the legacy path so only project_setup remains.",
                    )
            if path.is_file():
                try:
                    text = path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue
                for forbidden in FORBIDDEN_REFERENCES:
                    if forbidden in text:
                        fail(
                            f"Legacy reference '{forbidden}' found in {relative}",
                            failures,
                            "Replace the reference with project_setup or remove obsolete documentation.",
                        )

    validate_script_references(failures, strict_repository_scan=tool_repository)
    validate_json_configuration(failures, tool_repository=tool_repository)

    if tool_repository:
        validate_tool_package_metadata(failures)
    else:
        print("==> Skipping source-package metadata checks in embedded target mode")

    if failures:
        print("", file=sys.stderr)
        print(f"Repository quality failed with {len(failures)} error(s).", file=sys.stderr)
        print("Review each `Fix:` line above. No remote GitHub changes were made.", file=sys.stderr)
        return 1

    print(
        f"Repository quality checks passed in {mode} mode: required files, committed artifacts, "
        "project_setup script references, and managed JSON are valid."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
