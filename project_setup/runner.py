from __future__ import annotations

import json

from .github import GitHubClient
from .issues import generate_issues
from .labels import sync_labels
from .milestones import sync_milestones
from .project import create_project


def load_project_setup_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        config = json.load(file)
    required = ("labelsFile", "milestonesFile", "projectDefinitionFile", "backlogManifestFile")
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(f"project setup config is missing: {', '.join(missing)}")
    return config


def run_project_setup(
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
    owner_type: str | None = None,
) -> None:
    if run_labels:
        print("==> Sync labels")
        sync_labels(client, repo, config["labelsFile"], dry_run=dry_run)
    if run_milestones:
        print("==> Sync milestones")
        sync_milestones(client, repo, config["milestonesFile"], dry_run=dry_run)
    if run_project_creation:
        print("==> Create Project v2")
        create_project(
            client,
            repo,
            config["projectDefinitionFile"],
            dry_run=dry_run,
            owner_type=owner_type,
        )
    if run_issue_generation:
        print("==> Generate issues and tasks")
        generate_issues(
            None if dry_run else client,
            repo,
            config["backlogManifestFile"],
            dry_run=dry_run,
            link_subissues=link_subissues and not dry_run,
        )
    print("Project setup finished.")
