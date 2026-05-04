from __future__ import annotations

import argparse
import json
import os

from .auto_label import apply_auto_labels
from .github import GitHubClient, get_token, require_client
from .issue_milestones import sync_issue_milestones
from .issues import generate_issues
from .labels import sync_labels
from .milestones import sync_milestones
from .project import create_project, sync_project


def load_bootstrap_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def repo_arg(value: str | None) -> str:
    repo = value or os.getenv("GITHUB_REPOSITORY")
    if not repo:
        raise SystemExit("Missing --repo and GITHUB_REPOSITORY")
    return repo


def optional_client() -> GitHubClient | None:
    token = get_token()
    return GitHubClient(token) if token else None


def cmd_labels_sync(args) -> int:
    client = GitHubClient("") if args.dry_run else require_client()
    sync_labels(client, repo_arg(args.repo), args.file, dry_run=args.dry_run)
    return 0


def cmd_milestones_sync(args) -> int:
    client = GitHubClient("") if args.dry_run else require_client()
    sync_milestones(client, repo_arg(args.repo), args.file, dry_run=args.dry_run)
    return 0


def cmd_issues_generate(args) -> int:
    generate_issues(repo_arg(args.repo), args.file, dry_run=args.dry_run, link_subissues=args.link_subissues)
    return 0


def cmd_project_create(args) -> int:
    client = GitHubClient("") if args.dry_run else require_client()
    create_project(client, repo_arg(args.repo), args.file, dry_run=args.dry_run)
    return 0


def cmd_project_sync(args) -> int:
    sync_project(
        require_client(),
        repo_arg(args.repo),
        args.file,
        args.project_number,
        owner=args.owner,
        issue_state=args.issue_state,
        link_subissue_items=args.link_subissues,
        only_link_subissues=args.only_link_subissues,
        dry_run=args.dry_run,
    )
    return 0


def cmd_issue_milestones_sync(args) -> int:
    sync_issue_milestones(require_client(), repo_arg(args.repo), clear_not_planned=args.clear_not_planned, dry_run=args.dry_run)
    return 0


def cmd_auto_label_apply(args) -> int:
    event_path = args.event_path or os.getenv("GITHUB_EVENT_PATH")
    if not event_path:
        print("Missing --event-path or GITHUB_EVENT_PATH")
        return 1
    return apply_auto_labels(repo_arg(args.repo), event_path, args.labels_file, optional_client(), dry_run=args.dry_run)


def cmd_bootstrap(args) -> int:
    config = load_bootstrap_config(args.config)
    defaults = config.get("defaults", {})
    dry_run = args.dry_run if args.dry_run is not None else defaults.get("dryRun", True)
    repo = repo_arg(args.repo)
    client = GitHubClient("") if dry_run else require_client()

    run_labels = args.run_labels if args.run_labels is not None else defaults.get("runLabels", True)
    run_milestones = args.run_milestones if args.run_milestones is not None else defaults.get("runMilestones", True)
    run_project_creation = args.run_project_creation if args.run_project_creation is not None else defaults.get("runProjectCreation", False)
    run_issue_generation = args.run_issue_generation if args.run_issue_generation is not None else defaults.get("runIssueGeneration", True)
    link_subissues = args.link_subissues if args.link_subissues is not None else defaults.get("linkSubissues", False)

    if run_labels:
        print("==> Sync labels")
        sync_labels(client, repo, config["labelsFile"], dry_run=dry_run)
    if run_milestones:
        print("==> Sync milestones")
        sync_milestones(client, repo, config["milestonesFile"], dry_run=dry_run)
    if run_project_creation:
        print("==> Create project v2")
        create_project(client, repo, config["projectDefinitionFile"], dry_run=dry_run)
    if run_issue_generation:
        print("==> Generate issues/tasks")
        generate_issues(repo, config["backlogManifestFile"], dry_run=dry_run, link_subissues=link_subissues and not dry_run)

    print("Governance bootstrap finished.")
    return 0


def add_bool_pair(parser: argparse.ArgumentParser, name: str, dest: str, help_text: str) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument(f"--{name}", dest=dest, action="store_true", default=None, help=help_text)
    group.add_argument(f"--skip-{name.removeprefix('run-')}", dest=dest, action="store_false")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="governance", description="Reusable GitHub governance bootstrap CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    labels = sub.add_parser("labels")
    labels_sub = labels.add_subparsers(dest="labels_command", required=True)
    labels_sync = labels_sub.add_parser("sync")
    labels_sync.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    labels_sync.add_argument("--file", default="config/project/labels.json")
    labels_sync.add_argument("--dry-run", action="store_true")
    labels_sync.set_defaults(func=cmd_labels_sync)

    milestones = sub.add_parser("milestones")
    milestones_sub = milestones.add_subparsers(dest="milestones_command", required=True)
    milestones_sync = milestones_sub.add_parser("sync")
    milestones_sync.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    milestones_sync.add_argument("--file", default="config/project/milestones.json")
    milestones_sync.add_argument("--dry-run", action="store_true")
    milestones_sync.set_defaults(func=cmd_milestones_sync)

    issues = sub.add_parser("issues")
    issues_sub = issues.add_subparsers(dest="issues_command", required=True)
    issues_generate = issues_sub.add_parser("generate")
    issues_generate.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    issues_generate.add_argument("--file", default="config/stories/backlog-manifest.json")
    issues_generate.add_argument("--dry-run", action="store_true")
    issues_generate.add_argument("--link-subissues", action="store_true")
    issues_generate.set_defaults(func=cmd_issues_generate)

    project = sub.add_parser("project")
    project_sub = project.add_subparsers(dest="project_command", required=True)
    project_create = project_sub.add_parser("create")
    project_create.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    project_create.add_argument("--file", default="config/project/project-definition.json")
    project_create.add_argument("--dry-run", action="store_true")
    project_create.set_defaults(func=cmd_project_create)

    project_sync = project_sub.add_parser("sync")
    project_sync.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    project_sync.add_argument("--owner")
    project_sync.add_argument("--file", default="config/project/project-definition.json")
    project_sync.add_argument("--project-number", type=int, required=True)
    project_sync.add_argument("--issue-state", default="open", choices=["open", "closed", "all"])
    project_sync.add_argument("--link-subissues", action="store_true")
    project_sync.add_argument("--only-link-subissues", action="store_true")
    project_sync.add_argument("--dry-run", action="store_true")
    project_sync.set_defaults(func=cmd_project_sync)

    issue_milestones = sub.add_parser("issue-milestones")
    issue_milestones_sub = issue_milestones.add_subparsers(dest="issue_milestones_command", required=True)
    issue_milestones_sync = issue_milestones_sub.add_parser("sync")
    issue_milestones_sync.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    issue_milestones_sync.add_argument("--clear-not-planned", action="store_true")
    issue_milestones_sync.add_argument("--dry-run", action="store_true")
    issue_milestones_sync.set_defaults(func=cmd_issue_milestones_sync)

    auto_label = sub.add_parser("auto-label")
    auto_label_sub = auto_label.add_subparsers(dest="auto_label_command", required=True)
    auto_label_apply = auto_label_sub.add_parser("apply")
    auto_label_apply.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    auto_label_apply.add_argument("--event-path", default=os.getenv("GITHUB_EVENT_PATH"))
    auto_label_apply.add_argument("--labels-file", default="config/project/labels.json")
    auto_label_apply.add_argument("--dry-run", action="store_true")
    auto_label_apply.set_defaults(func=cmd_auto_label_apply)

    bootstrap = sub.add_parser("bootstrap")
    bootstrap.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    bootstrap.add_argument("--config", default="governance.bootstrap.json")
    dry_run_group = bootstrap.add_mutually_exclusive_group()
    dry_run_group.add_argument("--dry-run", dest="dry_run", action="store_true", default=None)
    dry_run_group.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    add_bool_pair(bootstrap, "run-labels", "run_labels", "Run labels sync")
    add_bool_pair(bootstrap, "run-milestones", "run_milestones", "Run milestones sync")
    add_bool_pair(bootstrap, "run-project-creation", "run_project_creation", "Create project v2")
    add_bool_pair(bootstrap, "run-issue-generation", "run_issue_generation", "Generate issues/tasks")
    link_group = bootstrap.add_mutually_exclusive_group()
    link_group.add_argument("--link-subissues", dest="link_subissues", action="store_true", default=None)
    link_group.add_argument("--no-link-subissues", dest="link_subissues", action="store_false")
    bootstrap.set_defaults(func=cmd_bootstrap)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
