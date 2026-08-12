from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .github import GitHubClient, get_project_pat, require_client
from .pr_sync import (
    apply_pr_sync,
    context_from_event,
    load_sync_config,
    project_number_from_value,
)
from .promotion_sync import apply_promotion_sync
from .related_prs import is_promotion_context


def load_event(path: str | os.PathLike[str]) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def apply_routed_pr_sync(
    client: GitHubClient,
    repo: str,
    event: dict,
    *,
    config_path: str | os.PathLike[str] = "project_setup.json",
    project_client: GitHubClient | None = None,
    project_number: int | None = None,
    owner: str | None = None,
    dry_run: bool = False,
) -> int:
    ctx = context_from_event(event, client=client, repo=repo)
    if is_promotion_context(ctx, config_path):
        return apply_promotion_sync(
            client,
            repo,
            event,
            config_path=config_path,
            project_client=project_client,
            project_number=project_number,
            owner=owner,
            dry_run=dry_run,
        )

    return apply_pr_sync(
        client,
        repo,
        event,
        load_sync_config(config_path),
        project_client=project_client,
        project_number=project_number,
        owner=owner,
        dry_run=dry_run,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Route PR Sync between implementation and promotion contexts")
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    parser.add_argument("--event-path", default=os.getenv("GITHUB_EVENT_PATH"))
    parser.add_argument("--config", default=os.getenv("PROJECT_SETUP_CONFIG", "project_setup.json"))
    parser.add_argument("--project-number", type=int)
    parser.add_argument("--owner")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.repo:
        raise SystemExit("Missing --repo or GITHUB_REPOSITORY")
    if not args.event_path:
        raise SystemExit("Missing --event-path or GITHUB_EVENT_PATH")

    client = require_client()
    project_pat = get_project_pat()
    project_client = GitHubClient(project_pat) if project_pat else None
    return apply_routed_pr_sync(
        client,
        args.repo,
        load_event(args.event_path),
        config_path=args.config,
        project_client=project_client,
        project_number=project_number_from_value(args.project_number),
        owner=args.owner,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
