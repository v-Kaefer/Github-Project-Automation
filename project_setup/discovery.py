from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import sys

from .github import GitHubClient, get_token, require_client
from .runner import load_project_setup_config, run_project_setup


SUPPORTED_PROJECT_TYPES = ("python", "node", "go", "java", "rust", "dotnet", "generic")
PROJECT_MARKERS = {
    "python": ("pyproject.toml", "requirements.txt", "setup.py", "Pipfile"),
    "node": ("package.json", "pnpm-lock.yaml", "package-lock.json", "yarn.lock"),
    "go": ("go.mod",),
    "java": ("pom.xml", "build.gradle", "build.gradle.kts"),
    "rust": ("Cargo.toml",),
    "dotnet": ("*.csproj", "*.sln"),
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
        source = "environment" if any(os.getenv(name) for name in ("GITHUB_TOKEN", "GH_TOKEN", "PROJECT_SETUP_PAT")) else "gh"
        return AuthStatus(True, source, "A GitHub token is available")
    if shutil.which("gh"):
        return AuthStatus(False, "gh", "gh CLI is installed but no authenticated token was returned")
    return AuthStatus(False, "missing", "No environment token and gh CLI was not found")


def _collect_markers(root: Path, patterns: tuple[str, ...]) -> tuple[str, ...]:
    markers: list[str] = []
    for pattern in patterns:
        if "*" in pattern:
            markers.extend(str(path.relative_to(root)) for path in sorted(root.glob(pattern)) if path.is_file())
        elif (root / pattern).is_file():
            markers.append(pattern)
    return tuple(markers)


def detect_project_matches(root: str | os.PathLike[str]) -> list[ProjectMatch]:
    root_path = Path(root)
    if not root_path.exists():
        raise FileNotFoundError(f"Project root does not exist: {root_path}")
    matches = [
        ProjectMatch(project_type, markers)
        for project_type in SUPPORTED_PROJECT_TYPES[:-1]
        if (markers := _collect_markers(root_path, PROJECT_MARKERS[project_type]))
    ]
    return matches or [ProjectMatch("generic", tuple())]


def resolve_project_match(root: str | os.PathLike[str], override: str | None = None) -> ProjectMatch:
    if override:
        if override not in SUPPORTED_PROJECT_TYPES:
            raise ValueError(f"Unsupported project type: {override}")
        match = next((item for item in detect_project_matches(root) if item.project_type == override), None)
        return match or ProjectMatch(override, tuple())
    matches = detect_project_matches(root)
    if len(matches) == 1 or not sys.stdin.isatty():
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
        if choice.isdigit() and 1 <= int(choice) <= len(matches):
            return matches[int(choice) - 1]
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


def build_apply_command(
    repo: str,
    config_path: str,
    dry_run: bool,
    run_labels: bool,
    run_milestones: bool,
    run_project_creation: bool,
    run_issue_generation: bool,
    link_subissues: bool,
) -> str:
    parts = ["python -m project_setup apply", f"--repo {repo}", f"--config {config_path}"]
    parts.append("--dry-run" if dry_run else "--no-dry-run")
    parts.append("--run-labels" if run_labels else "--skip-labels")
    parts.append("--run-milestones" if run_milestones else "--skip-milestones")
    parts.append("--run-project-creation" if run_project_creation else "--skip-project-creation")
    parts.append("--run-issue-generation" if run_issue_generation else "--skip-issue-generation")
    parts.append("--link-subissues" if link_subissues else "--no-link-subissues")
    return " ".join(parts)


def run_discovery(args) -> int:
    config = load_project_setup_config(args.config)
    repo = args.repo or os.getenv("GITHUB_REPOSITORY")
    if not repo:
        print("Missing --repo and GITHUB_REPOSITORY")
        return 1

    auth = detect_auth_status()
    print("==> GitHub auth")
    print(f"Configured: {'yes' if auth.configured else 'no'} ({auth.source})")
    if not auth.configured:
        print(auth.detail)
        print(f"Expected workflow secret: {config.get('secretName', 'PROJECT_SETUP_PAT')}")
        return 1

    print("==> Project detection")
    try:
        project = resolve_project_match(args.root, args.project_type)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc))
        return 1
    print(f"Detected project type: {project.project_type}")
    if project.markers:
        print(f"Markers: {', '.join(project.markers)}")

    defaults = config.get("defaults", {})
    values = {
        "dry_run": defaults.get("dryRun", True),
        "run_labels": defaults.get("runLabels", True),
        "run_milestones": defaults.get("runMilestones", True),
        "run_project_creation": defaults.get("runProjectCreation", False),
        "run_issue_generation": defaults.get("runIssueGeneration", False),
        "link_subissues": defaults.get("linkSubissues", False),
    }
    interactive = sys.stdin.isatty() and not args.auto
    if interactive:
        values["dry_run"] = _prompt_bool("Run in dry-run mode?", values["dry_run"])
        values["run_labels"] = _prompt_bool("Sync labels?", values["run_labels"])
        values["run_milestones"] = _prompt_bool("Sync milestones?", values["run_milestones"])
        values["run_project_creation"] = _prompt_bool("Create Project v2?", values["run_project_creation"])
        values["run_issue_generation"] = _prompt_bool("Generate issues and tasks?", values["run_issue_generation"])
        values["link_subissues"] = _prompt_bool("Link generated tasks as sub-issues?", values["link_subissues"])
    else:
        print("Using configuration defaults (non-interactive).")

    print("==> Recommended command")
    print(build_apply_command(repo, args.config, **values))
    if not args.apply:
        return 0
    if not args.yes:
        if not sys.stdin.isatty() or not _prompt_bool("Run the selected setup now?", False):
            print("Confirmation required; no changes were applied.")
            return 1
    client = GitHubClient("") if values["dry_run"] else require_client()
    run_project_setup(client, repo, config, **values)
    return 0
