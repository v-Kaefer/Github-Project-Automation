from __future__ import annotations

import argparse
import os
from pathlib import Path

from .auto_label import apply_auto_labels
from .discovery import SUPPORTED_PROJECT_TYPES, run_discovery
from .github import (
    GitHubClient,
    get_project_pat,
    get_token,
    load_env_file,
    require_client,
    require_project_client,
)
from .installer import PROFILE_FILES, install_repository
from .issue_milestones import sync_issue_milestones
from .issues import generate_issues
from .labels import sync_labels
from .milestones import sync_milestones
from .project import create_project, sync_project
from .pr_validation import upsert_validation_comment, validate_pull_request
from .runner import load_project_setup_config, run_project_setup


def repo_arg(value: str | None) -> str:
    repository = value or os.getenv("GITHUB_REPOSITORY")
    if not repository:
        raise SystemExit(
            "Missing target repository.\n"
            "Fix: pass `--repo owner/repository`, use `REPO=owner/repository` with Make, "
            "or set GITHUB_REPOSITORY in .env."
        )
    return repository


def optional_client() -> GitHubClient | None:
    return GitHubClient(token) if (token := get_token()) else None


def cmd_init(args: argparse.Namespace) -> int:
    install_repository(
        args.target,
        source=args.source,
        profile=args.profile,
        force=args.force,
        dry_run=args.dry_run,
    )
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    environment_path = load_env_file()
    project_pat = get_project_pat()
    github_token = get_token()
    failures = 0

    print("==> Environment")
    print(f"python_module=project_setup")
    print(f"working_directory={Path.cwd()}")
    print(f"env_file={environment_path or (Path.cwd() / '.env')} exists={'yes' if environment_path else 'no'}")
    print(f"github_repository={os.getenv('GITHUB_REPOSITORY') or 'missing'}")
    print(f"github_token={'configured' if github_token else 'missing'}")
    print(f"project_setup_pat={'configured' if project_pat else 'missing'}")

    if not environment_path:
        print("WARNING: .env was not found.")
        print("  Fix: copy .env.example to .env and fill only the values required for your workflow.")
    if not github_token:
        print("WARNING: no GitHub authentication is available for live repository operations.")
        print("  Fix: set PROJECT_SETUP_PAT in .env, set GITHUB_TOKEN/GH_TOKEN, or run `gh auth login`.")
    if not project_pat:
        print("INFO: PROJECT_SETUP_PAT is required only for GitHub Projects v2 creation or synchronization.")
        print("  Setup: Settings > Developer settings > Personal access tokens > Tokens (classic).")
        print("  Required scopes: repo and project. Save the token as PROJECT_SETUP_PAT in .env.")

    print("==> Configuration")
    print(f"config={config_path.resolve()}")
    print(f"config_exists={'yes' if config_path.is_file() else 'no'}")
    if not config_path.is_file():
        print(f"ERROR: configuration file is missing: {config_path}")
        print("  Fix: restore project_setup.json or pass --config <path>.")
        return 1

    try:
        config = load_project_setup_config(str(config_path))
    except (OSError, ValueError) as exc:
        print(f"ERROR: configuration could not be loaded: {exc}")
        print("  Fix: correct project_setup.json and run `make doctor` again.")
        return 1

    for key in ("labelsFile", "milestonesFile", "projectDefinitionFile", "backlogManifestFile"):
        path = Path(config[key])
        exists = path.is_file()
        print(f"{key}={path} exists={'yes' if exists else 'no'}")
        if not exists:
            failures += 1
            print(f"  ERROR: referenced file is missing: {path}")
            print(f"  Fix: create the file or update `{key}` in {config_path}.")

    defaults = config.get("defaults", {})
    if defaults.get("runProjectCreation", False) and not project_pat:
        failures += 1
        print("ERROR: runProjectCreation is enabled but PROJECT_SETUP_PAT is missing.")
        print("  Fix: configure PROJECT_SETUP_PAT in .env or disable runProjectCreation until the token is ready.")

    if failures:
        print(f"Doctor found {failures} blocking problem(s). No GitHub API changes were made.")
        return 1
    print("Doctor completed. Local files are valid; no GitHub API changes were made.")
    return 0


def cmd_labels_sync(args: argparse.Namespace) -> int:
    sync_labels(GitHubClient("") if args.dry_run else require_client(), repo_arg(args.repo), args.file, args.dry_run)
    return 0


def cmd_milestones_sync(args: argparse.Namespace) -> int:
    sync_milestones(GitHubClient("") if args.dry_run else require_client(), repo_arg(args.repo), args.file, args.dry_run)
    return 0


def cmd_issues_generate(args: argparse.Namespace) -> int:
    generate_issues(
        None if args.dry_run else require_client(),
        repo_arg(args.repo),
        args.file,
        args.dry_run,
        args.link_subissues,
    )
    return 0


def cmd_project_create(args: argparse.Namespace) -> int:
    client = GitHubClient("") if args.dry_run else require_project_client()
    create_project(client, repo_arg(args.repo), args.file, args.dry_run)
    return 0


def cmd_project_sync(args: argparse.Namespace) -> int:
    sync_project(
        require_project_client(),
        repo_arg(args.repo),
        args.file,
        args.project_number,
        owner=args.owner,
        issue_state=args.issue_state,
        dry_run=args.dry_run,
    )
    return 0


def cmd_issue_milestones_sync(args: argparse.Namespace) -> int:
    sync_issue_milestones(require_client(), repo_arg(args.repo), args.clear_not_planned, args.dry_run)
    return 0


def cmd_auto_label_apply(args: argparse.Namespace) -> int:
    event_path = args.event_path or os.getenv("GITHUB_EVENT_PATH")
    if not event_path:
        raise SystemExit(
            "Missing GitHub event payload.\n"
            "Fix: pass --event-path <file> locally. GitHub Actions provides GITHUB_EVENT_PATH automatically."
        )
    return apply_auto_labels(repo_arg(args.repo), event_path, args.labels_file, optional_client(), args.dry_run)


def cmd_validate_pr(args: argparse.Namespace) -> int:
    body = args.body
    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")
    if body is None:
        body = os.getenv("PR_BODY", "")
    findings = validate_pull_request(args.branch, body, args.base_branch)
    for finding in findings:
        print(f"{finding.section}: {finding.problem}")
        print(f"  Fix: {finding.fix}")
    if args.comment:
        if not args.repo or not args.pr_number:
            raise SystemExit("--comment requires --repo and --pr-number")
        upsert_validation_comment(require_client(), args.repo, args.pr_number, findings)
    return 1 if findings else 0


def cmd_apply(args: argparse.Namespace) -> int:
    config = load_project_setup_config(args.config)
    defaults = config.get("defaults", {})
    values = {
        "dry_run": args.dry_run if args.dry_run is not None else defaults.get("dryRun", True),
        "run_labels": args.run_labels if args.run_labels is not None else defaults.get("runLabels", True),
        "run_milestones": args.run_milestones if args.run_milestones is not None else defaults.get("runMilestones", True),
        "run_project_creation": args.run_project_creation if args.run_project_creation is not None else defaults.get("runProjectCreation", False),
        "run_issue_generation": args.run_issue_generation if args.run_issue_generation is not None else defaults.get("runIssueGeneration", False),
        "link_subissues": args.link_subissues if args.link_subissues is not None else defaults.get("linkSubissues", False),
    }
    if values["dry_run"]:
        client = GitHubClient("")
    elif values["run_project_creation"]:
        client = require_project_client()
    else:
        client = require_client()
    run_project_setup(client, repo_arg(args.repo), config, **values)
    return 0


def add_bool_pair(parser: argparse.ArgumentParser, name: str, destination: str, help_text: str) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument(f"--{name}", dest=destination, action="store_true", default=None, help=help_text)
    group.add_argument(f"--skip-{name.removeprefix('run-')}", dest=destination, action="store_false")


def add_apply_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    parser.add_argument("--config", default=os.getenv("PROJECT_SETUP_CONFIG", "project_setup.json"))
    dry_run = parser.add_mutually_exclusive_group()
    dry_run.add_argument("--dry-run", dest="dry_run", action="store_true", default=None)
    dry_run.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    add_bool_pair(parser, "run-labels", "run_labels", "Synchronize labels")
    add_bool_pair(parser, "run-milestones", "run_milestones", "Synchronize milestones")
    add_bool_pair(parser, "run-project-creation", "run_project_creation", "Create Project v2")
    add_bool_pair(parser, "run-issue-generation", "run_issue_generation", "Generate issues and tasks")
    links = parser.add_mutually_exclusive_group()
    links.add_argument("--link-subissues", dest="link_subissues", action="store_true", default=None)
    links.add_argument("--no-link-subissues", dest="link_subissues", action="store_false")
    parser.set_defaults(func=cmd_apply)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="project-setup", description="Set up and automate GitHub repositories")
    subcommands = parser.add_subparsers(dest="command", required=True)

    init = subcommands.add_parser("init", help="Copy project setup tooling into a target repository")
    init.add_argument("--target", required=True)
    init.add_argument("--source")
    init.add_argument("--profile", choices=sorted(PROFILE_FILES), default="core")
    init.add_argument("--force", action="store_true")
    init.add_argument("--dry-run", action="store_true")
    init.set_defaults(func=cmd_init)

    discover = subcommands.add_parser("discover", help="Inspect a repository and recommend setup options")
    discover.add_argument("--repo")
    discover.add_argument("--config", default=os.getenv("PROJECT_SETUP_CONFIG", "project_setup.json"))
    discover.add_argument("--root", default=".")
    discover.add_argument("--project-type", choices=SUPPORTED_PROJECT_TYPES)
    discover.add_argument("--auto", action="store_true", help="Use configuration defaults without prompts")
    discover.add_argument("--apply", action="store_true", help="Apply the selected setup after review")
    discover.add_argument("--yes", action="store_true", help="Confirm --apply in non-interactive environments")
    discover.set_defaults(func=run_discovery)

    doctor = subcommands.add_parser("doctor", help="Check local project setup prerequisites")
    doctor.add_argument("--config", default=os.getenv("PROJECT_SETUP_CONFIG", "project_setup.json"))
    doctor.set_defaults(func=cmd_doctor)

    labels = subcommands.add_parser("labels")
    labels_sub = labels.add_subparsers(dest="labels_command", required=True)
    labels_sync = labels_sub.add_parser("sync")
    labels_sync.add_argument("--repo")
    labels_sync.add_argument("--file", default="config/project/labels.json")
    labels_sync.add_argument("--dry-run", action="store_true")
    labels_sync.set_defaults(func=cmd_labels_sync)

    milestones = subcommands.add_parser("milestones")
    milestones_sub = milestones.add_subparsers(dest="milestones_command", required=True)
    milestones_sync = milestones_sub.add_parser("sync")
    milestones_sync.add_argument("--repo")
    milestones_sync.add_argument("--file", default="config/project/milestones.json")
    milestones_sync.add_argument("--dry-run", action="store_true")
    milestones_sync.set_defaults(func=cmd_milestones_sync)

    issues = subcommands.add_parser("issues")
    issues_sub = issues.add_subparsers(dest="issues_command", required=True)
    issues_generate = issues_sub.add_parser("generate")
    issues_generate.add_argument("--repo")
    issues_generate.add_argument("--file", default="config/stories/backlog-manifest.json")
    issues_generate.add_argument("--dry-run", action="store_true")
    issues_generate.add_argument("--link-subissues", action="store_true")
    issues_generate.set_defaults(func=cmd_issues_generate)

    project = subcommands.add_parser("project")
    project_sub = project.add_subparsers(dest="project_command", required=True)
    project_create = project_sub.add_parser("create")
    project_create.add_argument("--repo")
    project_create.add_argument("--file", default="config/project/project-definition.json")
    project_create.add_argument("--dry-run", action="store_true")
    project_create.set_defaults(func=cmd_project_create)
    project_sync = project_sub.add_parser("sync")
    project_sync.add_argument("--repo")
    project_sync.add_argument("--owner")
    project_sync.add_argument("--file", default="config/project/project-definition.json")
    project_sync.add_argument("--project-number", type=int, required=True)
    project_sync.add_argument("--issue-state", choices=("open", "closed", "all"), default="open")
    project_sync.add_argument("--dry-run", action="store_true")
    project_sync.set_defaults(func=cmd_project_sync)

    issue_milestones = subcommands.add_parser("issue-milestones")
    issue_milestones_sub = issue_milestones.add_subparsers(dest="issue_milestones_command", required=True)
    issue_milestones_sync = issue_milestones_sub.add_parser("sync")
    issue_milestones_sync.add_argument("--repo")
    issue_milestones_sync.add_argument("--clear-not-planned", action="store_true")
    issue_milestones_sync.add_argument("--dry-run", action="store_true")
    issue_milestones_sync.set_defaults(func=cmd_issue_milestones_sync)

    auto_label = subcommands.add_parser("auto-label")
    auto_label_sub = auto_label.add_subparsers(dest="auto_label_command", required=True)
    auto_label_apply = auto_label_sub.add_parser("apply")
    auto_label_apply.add_argument("--repo")
    auto_label_apply.add_argument("--event-path")
    auto_label_apply.add_argument("--labels-file", default="config/project/labels.json")
    auto_label_apply.add_argument("--dry-run", action="store_true")
    auto_label_apply.set_defaults(func=cmd_auto_label_apply)

    validate_pr = subcommands.add_parser("validate-pr")
    validate_pr.add_argument("--branch")
    validate_pr.add_argument("--base-branch")
    validate_pr.add_argument("--body")
    validate_pr.add_argument("--body-file")
    validate_pr.add_argument("--repo")
    validate_pr.add_argument("--pr-number", type=int)
    validate_pr.add_argument("--comment", action="store_true")
    validate_pr.set_defaults(func=cmd_validate_pr)

    apply = subcommands.add_parser("apply", help="Apply configured repository setup")
    add_apply_arguments(apply)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        load_env_file()
        args = build_parser().parse_args(argv)
        return int(args.func(args))
    except ValueError as exc:
        raise SystemExit(f"Configuration error: {exc}\nFix the referenced file and run the command again.") from exc


if __name__ == "__main__":
    raise SystemExit(main())
