from __future__ import annotations

import json

from .github import GitHubClient
from .issue_milestones import sync_issue_milestones
from .issues import generate_issues
from .labels import sync_labels
from .milestones import sync_milestones
from .project import create_project, sync_project


def load_bootstrap_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_bootstrap(
    client: GitHubClient,
    repo: str,
    config: dict,
    *,
    dry_run: bool,
    run_labels: bool,
    run_milestones: bool,
    run_project_creation: bool,
    run_issue_generation: bool,
    link_subissues: bool,
) -> None:
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

