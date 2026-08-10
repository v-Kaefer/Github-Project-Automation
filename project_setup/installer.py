from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil


CORE_TEMPLATE_FILES = (
    ".env.example",
    "Makefile",
    "AI_SETUP_GUIDE.md",
    ".github/ISSUE_TEMPLATE/bug-report.yml",
    ".github/ISSUE_TEMPLATE/task-sub-issue.yml",
    ".github/ISSUE_TEMPLATE/user-story.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/pull_request_template.md",
    ".github/workflows/auto-label.yml",
    ".github/workflows/qa-source-branch.yml",
    ".github/workflows/main-source-branch.yml",
    ".github/workflows/pr-metadata.yml",
    ".github/workflows/project-setup.yml",
    "config/project/labels.json",
    "config/project/milestones.json",
    "config/project/project-definition.json",
    "config/stories/backlog-manifest.json",
    "project_setup.json",
    "scripts/validation/repo_quality.py",
    "scripts/validation/validate_pr_body.py",
)

LICENSE_TEMPLATE_FILES = (
    ("LICENSE", "licenses/project_setup/LICENSE"),
    ("NOTICE", "licenses/project_setup/NOTICE"),
)

PROFILE_FILES = {
    "core": (),
}


@dataclass(frozen=True)
class InstallResult:
    copied: tuple[str, ...]
    skipped: tuple[str, ...]


def source_root_from_package() -> Path:
    return Path(__file__).resolve().parents[1]


def package_files(source_root: Path) -> tuple[tuple[str, str], ...]:
    package_root = source_root / "project_setup"
    return tuple(
        (relative, relative)
        for relative in (
            str(path.relative_to(source_root)).replace("\\", "/")
            for path in sorted(package_root.glob("*.py"))
        )
    )


def template_files(source_root: Path, profile: str) -> tuple[tuple[str, str], ...]:
    if profile not in PROFILE_FILES:
        raise ValueError(f"Unknown profile '{profile}'. Available profiles: {', '.join(PROFILE_FILES)}")
    core = tuple((path, path) for path in CORE_TEMPLATE_FILES)
    return (*core, *LICENSE_TEMPLATE_FILES, *package_files(source_root), *PROFILE_FILES[profile])


def install_repository(
    target: str | Path,
    *,
    source: str | Path | None = None,
    profile: str = "core",
    force: bool = False,
    dry_run: bool = False,
) -> InstallResult:
    source_root = Path(source).resolve() if source else source_root_from_package()
    target_root = Path(target).resolve()
    if target_root.exists() and not target_root.is_dir():
        raise ValueError(f"Target is not a directory: {target_root}")
    if not dry_run:
        target_root.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    skipped: list[str] = []
    for source_relative, destination_relative in template_files(source_root, profile):
        source_path = source_root / source_relative
        destination = target_root / destination_relative
        if not source_path.is_file():
            raise FileNotFoundError(
                f"Project setup template is missing: {source_path}. "
                "Restore the source file before retrying the installation."
            )
        if destination.exists() and not force:
            skipped.append(destination_relative)
            print(f"skipped existing: {destination_relative}")
            if destination_relative in {"Makefile", ".env.example", "AI_SETUP_GUIDE.md"}:
                print(
                    f"  Review the installed template manually before merging it into the existing {destination_relative}. "
                    "Use --force only after reviewing the differences."
                )
            continue
        if dry_run:
            copied.append(destination_relative)
            print(f"[DRY-RUN] Would copy: {destination_relative}")
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        copied.append(destination_relative)
        print(f"copied: {destination_relative}")

    print(f"Project setup installation finished: copied={len(copied)}, skipped={len(skipped)}")
    if ".env.example" in copied:
        print("Next: copy .env.example to .env, configure only required values, and run `make doctor`.")
    return InstallResult(tuple(copied), tuple(skipped))
