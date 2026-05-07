from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import subprocess
import sys

from .bootstrap import load_bootstrap_config, run_bootstrap
from .github import GitHubClient, get_token, require_client


SUPPORTED_PROJECT_TYPES = ["python", "node", "go", "java", "rust", "dotnet", "generic"]
PROJECT_MARKERS = {
    "python": ["pyproject.toml", "requirements.txt", "setup.py", "Pipfile"],
    "node": ["package.json", "pnpm-lock.yaml", "package-lock.json", "yarn.lock"],
    "go": ["go.mod"],
    "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
    "rust": ["Cargo.toml"],
    "dotnet": ["*.csproj", "*.sln"],
}


@dataclass(frozen=True)
class AuthStatus:
    configured: bool
    source: str
    detail: str


@dataclass(frozen=True)
class ProjectMatch:
    project_type: str
    markers: tuple[str, ...]


def detect_auth_status() -> AuthStatus:
    token = get_token()
    if token:
        return AuthStatus(True, "environment", "GITHUB_TOKEN or GH_TOKEN is set")

    gh = shutil.which("gh")
    if gh:
        result = subprocess.run([gh, "auth", "status", "--hostname", "github.com"], capture_output=True, text=True)
        if result.returncode == 0:
            return AuthStatus(True, "gh", "gh auth status succeeded")
        detail = (result.stderr or result.stdout or "gh auth status failed").strip()
        return AuthStatus(False, "gh", detail)

    return AuthStatus(False, "missing", "No GITHUB_TOKEN/GH_TOKEN and gh CLI not found")


def _collect_markers(root: Path, patterns: list[str]) -> list[str]:
    markers: list[str] = []
    for pattern in patterns:
        if "*" in pattern:
            markers.extend(sorted(str(path.relative_to(root)) for path in root.glob(pattern) if path.is_file()))
            continue
        candidate = root / pattern
        if candidate.exists():
            markers.append(pattern)
    return markers


def detect_project_matches(root: str | os.PathLike[str]) -> list[ProjectMatch]:
    root_path = Path(root)
    if not root_path.exists():
        raise FileNotFoundError(f"Project root does not exist: {root_path}")

    matches: list[ProjectMatch] = []
    for project_type in ("python", "node", "go", "java", "rust", "dotnet"):
        markers = _collect_markers(root_path, PROJECT_MARKERS[project_type])
        if markers:
            matches.append(ProjectMatch(project_type, tuple(markers)))

    if matches:
        return matches
    return [ProjectMatch("generic", tuple())]


def resolve_project_match(root: str | os.PathLike[str], override: str | None = None) -> ProjectMatch:
    if override:
        if override not in SUPPORTED_PROJECT_TYPES:
            raise ValueError(f"Unsupported project type override: {override}")
        matches = detect_project_matches(root)
        markers = matches[0].markers if matches and matches[0].project_type == override else tuple()
        return ProjectMatch(override, markers)

    matches = detect_project_matches(root)
    if len(matches) == 1:
        return matches[0]

    if not sys.stdin.isatty():
        return matches[0]

    print("Multiple project types detected:")
    for index, match in enumerate(matches, start=1):
        print(f"  {index}. {match.project_type} ({', '.join(match.markers)})")
    print("  0. generic")

    while True:
        choice = input("Choose project type [1]: ").strip()
        if choice in {"", "1"}:
            return matches[0]
        if choice == "0":
            return ProjectMatch("generic", tuple())
        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= len(matches):
                return matches[index - 1]
        print("Invalid choice, try again.")


def _prompt_bool(question: str, default: bool) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        answer = input(f"{question} {suffix} ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes", "true", "1"}:
            return True
        if answer in {"n", "no", "false", "0"}:
            return False
        print("Please answer yes or no.")


def _prompt_confirm(message: str) -> bool:
    while True:
        answer = input(f"{message} [y/N] ").strip().lower()
        if not answer:
            return False
        if answer in {"y", "yes", "true", "1"}:
            return True
        if answer in {"n", "no", "false", "0"}:
            return False
        print("Please answer yes or no.")


def build_bootstrap_command(repo: str, config_path: str, dry_run: bool, run_labels: bool, run_milestones: bool, run_project_creation: bool, run_issue_generation: bool, link_subissues: bool) -> str:
    parts = [
        "python -m governance_bootstrap bootstrap",
        f"--repo {repo}",
        f"--config {config_path}",
    ]
    parts.append("--dry-run" if dry_run else "--no-dry-run")
    parts.append("--run-labels" if run_labels else "--skip-labels")
    parts.append("--run-milestones" if run_milestones else "--skip-milestones")
    parts.append("--run-project-creation" if run_project_creation else "--skip-project-creation")
    parts.append("--run-issue-generation" if run_issue_generation else "--skip-issue-generation")
    parts.append("--link-subissues" if link_subissues else "--no-link-subissues")
    return " ".join(parts)


def cmd_discover(args) -> int:
    config = load_bootstrap_config(args.config)
    repo = args.repo or os.getenv("GITHUB_REPOSITORY")
    if not repo:
        print("Missing --repo and GITHUB_REPOSITORY")
        return 1

    auth = detect_auth_status()
    print("==> GitHub auth")
    if auth.configured:
        print(f"Configured: yes ({auth.source})")
    else:
        print(f"Configured: no ({auth.source})")
        print(auth.detail)
        print(f"Expected workflow secret: {config.get('secretName', 'GOVERNANCE_PAT')}")
        return 1

    print("==> Project detection")
    try:
        project = resolve_project_match(args.root, args.project_type)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc))
        return 1
    if project.project_type == "generic":
        print("Detected project type: generic")
        print("No common project markers found.")
    else:
        print(f"Detected project type: {project.project_type}")
        if project.markers:
            print(f"Markers: {', '.join(project.markers)}")

    defaults = config.get("defaults", {})
    interactive = sys.stdin.isatty() and not args.auto
    dry_run = defaults.get("dryRun", True)
    run_labels = defaults.get("runLabels", True)
    run_milestones = defaults.get("runMilestones", True)
    run_project_creation = defaults.get("runProjectCreation", False)
    run_issue_generation = defaults.get("runIssueGeneration", True)
    link_subissues = defaults.get("linkSubissues", False)

    print("==> Bootstrap options")
    if interactive:
        dry_run = _prompt_bool("Run in dry-run mode?", dry_run)
        run_labels = _prompt_bool("Sync labels?", run_labels)
        run_milestones = _prompt_bool("Sync milestones?", run_milestones)
        run_project_creation = _prompt_bool("Create GitHub Project v2?", run_project_creation)
        run_issue_generation = _prompt_bool("Generate issues/tasks?", run_issue_generation)
        link_subissues = _prompt_bool("Link sub-issues when generating tasks?", link_subissues)
    else:
        print("Using config defaults (non-interactive).")

    print(f"Dry-run: {'yes' if dry_run else 'no'}")
    print(f"Sync labels: {'yes' if run_labels else 'no'}")
    print(f"Sync milestones: {'yes' if run_milestones else 'no'}")
    print(f"Create project: {'yes' if run_project_creation else 'no'}")
    print(f"Generate issues: {'yes' if run_issue_generation else 'no'}")
    print(f"Link sub-issues: {'yes' if link_subissues else 'no'}")

    print("==> Recommended command")
    command = build_bootstrap_command(repo, args.config, dry_run, run_labels, run_milestones, run_project_creation, run_issue_generation, link_subissues)
    print(command)

    if args.apply:
        if not sys.stdin.isatty():
            print("Confirmation required to run the selected command interactively.")
            return 1
        if not _prompt_confirm("Run the selected bootstrap command now?"):
            print("Aborted.")
            return 1
        client = GitHubClient("") if dry_run else require_client()
        run_bootstrap(
            client,
            repo,
            config,
            dry_run=dry_run,
            run_labels=run_labels,
            run_milestones=run_milestones,
            run_project_creation=run_project_creation,
            run_issue_generation=run_issue_generation,
            link_subissues=link_subissues,
        )

    return 0
