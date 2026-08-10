from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Any

from .github import (
    API_BASE,
    GitHubClient,
    GitHubRequestError,
    get_project_pat,
    require_client,
    split_repo,
)
from .issues import add_sub_issue
from .project import (
    add_issue_to_project,
    find_project,
    issue_node_id,
    list_project_fields,
    list_project_items,
    option_id,
    update_single_select,
)


SYNC_MARKER = "<!-- project-setup-pr-sync -->"
LINKED_TASK_PATTERN = re.compile(r"\b(?:closes|fixes|resolves)\s*:?\s*#(\d+)\b", re.IGNORECASE)
PARENT_ISSUE_PATTERN = re.compile(
    r"\bParent\s+(?:story|issue|task)\s*:\s*[^\n#]*#(\d+)\b",
    re.IGNORECASE,
)

DEFAULT_SYNC_CONFIG: dict[str, Any] = {
    "enabled": True,
    "syncLabels": True,
    "labelPrefixes": ["type:", "priority:", "test:"],
    "syncMilestone": True,
    "syncAssignees": True,
    "assignAuthorWhenTaskUnassigned": True,
    "linkSubissues": True,
    "syncProject": True,
    "skipPromotionPullRequests": True,
    "promotionPaths": [
        {"head": "develop", "base": "Q.A"},
        {"head": "Q.A", "base": "main"},
    ],
    "projectStatusField": "Status",
    "projectStatus": {
        "draft": "In progress",
        "review": "In review",
        "closed": "In progress",
        "merged": "Done",
    },
}


@dataclass(frozen=True)
class PullRequestContext:
    number: int
    action: str
    body: str
    base_ref: str
    head_ref: str
    head_repo: str
    author: str
    draft: bool
    merged: bool


def load_event(path: str | os.PathLike[str]) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_sync_config(path: str | os.PathLike[str] = "project_setup.json") -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    configured = data.get("prAutomation", {}).get("sync", {})
    if configured is None:
        configured = {}
    if not isinstance(configured, dict):
        raise ValueError("project_setup.json prAutomation.sync must be an object")

    result = dict(DEFAULT_SYNC_CONFIG)
    result.update(configured)

    status = dict(DEFAULT_SYNC_CONFIG["projectStatus"])
    custom_status = configured.get("projectStatus", {})
    if custom_status is not None:
        if not isinstance(custom_status, dict):
            raise ValueError("prAutomation.sync.projectStatus must be an object")
        status.update(custom_status)
    result["projectStatus"] = status

    prefixes = result.get("labelPrefixes", [])
    if not isinstance(prefixes, list) or not all(isinstance(value, str) and value for value in prefixes):
        raise ValueError("prAutomation.sync.labelPrefixes must be a list of non-empty strings")
    promotions = result.get("promotionPaths", [])
    if not isinstance(promotions, list) or not all(
        isinstance(item, dict) and item.get("head") and item.get("base") for item in promotions
    ):
        raise ValueError("prAutomation.sync.promotionPaths must contain {head, base} objects")
    return result


def context_from_pull_request(pr: dict[str, Any], action: str = "") -> PullRequestContext:
    head = pr.get("head") or {}
    base = pr.get("base") or {}
    head_repo = (head.get("repo") or {}).get("full_name") or ""
    return PullRequestContext(
        number=int(pr["number"]),
        action=action,
        body=pr.get("body") or "",
        base_ref=base.get("ref") or "",
        head_ref=head.get("ref") or "",
        head_repo=head_repo,
        author=(pr.get("user") or {}).get("login") or "",
        draft=bool(pr.get("draft")),
        merged=bool(pr.get("merged")),
    )


def context_from_event(
    event: dict[str, Any],
    *,
    client: GitHubClient | None = None,
    repo: str | None = None,
) -> PullRequestContext:
    pr = event.get("pull_request")
    if pr:
        return context_from_pull_request(pr, event.get("action") or "")

    workflow_run = event.get("workflow_run")
    if workflow_run:
        if client is None or not repo:
            raise RuntimeError("workflow_run PR Sync requires a GitHub client and repository")
        related_prs = workflow_run.get("pull_requests") or []
        if not related_prs or related_prs[0].get("number") is None:
            raise RuntimeError("Unsupported workflow_run payload: no associated pull request")
        number = int(related_prs[0]["number"])
        live_pr = client.request_json("GET", f"{API_BASE}/repos/{repo}/pulls/{number}")
        return context_from_pull_request(live_pr, "synchronize")

    raise RuntimeError("Unsupported event payload: expected pull_request or workflow_run")


def linked_task_number(body: str) -> int | None:
    match = LINKED_TASK_PATTERN.search(body or "")
    return int(match.group(1)) if match else None


def parent_issue_number(body: str) -> int | None:
    match = PARENT_ISSUE_PATTERN.search(body or "")
    return int(match.group(1)) if match else None


def is_same_repository(ctx: PullRequestContext, repo: str) -> bool:
    return not ctx.head_repo or ctx.head_repo.casefold() == repo.casefold()


def is_promotion_pull_request(ctx: PullRequestContext, config: dict[str, Any]) -> bool:
    if not config.get("skipPromotionPullRequests", True):
        return False
    return any(
        ctx.head_ref == str(path.get("head")) and ctx.base_ref == str(path.get("base"))
        for path in config.get("promotionPaths", [])
    )


def project_status_for_context(ctx: PullRequestContext, config: dict[str, Any]) -> str:
    mapping = config["projectStatus"]
    if ctx.action == "closed":
        return str(mapping["merged"] if ctx.merged else mapping["closed"])
    if ctx.action == "converted_to_draft" or ctx.draft:
        return str(mapping["draft"])
    return str(mapping["review"])


def issue_label_names(item: dict[str, Any]) -> set[str]:
    return {
        str(label["name"])
        for label in item.get("labels", [])
        if isinstance(label, dict) and label.get("name")
    }


def issue_assignee_logins(item: dict[str, Any]) -> list[str]:
    return [
        str(assignee["login"])
        for assignee in item.get("assignees", [])
        if isinstance(assignee, dict) and assignee.get("login")
    ]


def issue_milestone_number(item: dict[str, Any]) -> int | None:
    milestone = item.get("milestone")
    if isinstance(milestone, dict) and milestone.get("number") is not None:
        return int(milestone["number"])
    return None


def add_labels(client: GitHubClient, repo: str, issue_number: int, labels: list[str]) -> None:
    client.request_json(
        "POST",
        f"{API_BASE}/repos/{repo}/issues/{issue_number}/labels",
        {"labels": labels},
    )


def add_assignees(client: GitHubClient, repo: str, issue_number: int, assignees: list[str]) -> None:
    client.request_json(
        "POST",
        f"{API_BASE}/repos/{repo}/issues/{issue_number}/assignees",
        {"assignees": assignees},
    )


def upsert_sync_comment(
    client: GitHubClient,
    repo: str,
    pr_number: int,
    body: str,
    *,
    dry_run: bool = False,
) -> None:
    existing = next(
        (
            comment
            for comment in client.list_issue_comments(repo, pr_number)
            if SYNC_MARKER in (comment.get("body") or "")
        ),
        None,
    )
    if dry_run:
        verb = "update" if existing else "create"
        print(f"[DRY-RUN] Would {verb} PR Sync comment on PR #{pr_number}")
        print(body)
        return
    if existing:
        client.update_issue_comment(repo, int(existing["id"]), body)
    else:
        client.create_issue_comment(repo, pr_number, body)


def render_failure_comment(message: str) -> str:
    return "\n".join(
        [
            SYNC_MARKER,
            "## PR Sync needs attention",
            "",
            message,
            "",
            "Use `Closes #123`, `Fixes #123`, or `Resolves #123` to identify the implementation task.",
        ]
    )


def render_success_comment(
    ctx: PullRequestContext,
    task_number: int,
    status: str,
    project_note: str,
    parent_note: str,
) -> str:
    return "\n".join(
        [
            SYNC_MARKER,
            "## PR Sync",
            "",
            f"- Linked task: #{task_number}",
            f"- PR lifecycle target: `{status}`",
            f"- Project v2: {project_note}",
            f"- Parent/sub-issue: {parent_note}",
            f"- PR: #{ctx.number}",
        ]
    )


def is_permission_error(exc: BaseException) -> bool:
    if isinstance(exc, GitHubRequestError):
        return exc.status in {401, 403}
    text = str(exc).casefold()
    return any(
        marker in text
        for marker in (
            "forbidden",
            "resource not accessible",
            "insufficient",
            "permission",
            "scope",
        )
    )


def sync_pr_metadata(
    client: GitHubClient,
    repo: str,
    ctx: PullRequestContext,
    task: dict[str, Any],
    pr_issue: dict[str, Any],
    config: dict[str, Any],
    *,
    dry_run: bool = False,
) -> None:
    if config.get("syncLabels", True):
        prefixes = tuple(str(value) for value in config.get("labelPrefixes", []))
        task_labels = sorted(name for name in issue_label_names(task) if name.startswith(prefixes))
        existing = issue_label_names(pr_issue)
        missing = [name for name in task_labels if name not in existing]
        if missing:
            if dry_run:
                print(f"[DRY-RUN] Would add labels to PR #{ctx.number}: {', '.join(missing)}")
            else:
                add_labels(client, repo, ctx.number, missing)

    if config.get("syncMilestone", True):
        task_milestone = issue_milestone_number(task)
        pr_milestone = issue_milestone_number(pr_issue)
        if task_milestone is not None and task_milestone != pr_milestone:
            if dry_run:
                print(f"[DRY-RUN] Would set PR #{ctx.number} milestone to #{task_milestone}")
            else:
                client.update_issue(repo, ctx.number, {"milestone": task_milestone})

    if config.get("syncAssignees", True):
        task_assignees = issue_assignee_logins(task)
        if not task_assignees and config.get("assignAuthorWhenTaskUnassigned", True) and ctx.author:
            task_assignees = [ctx.author]
            if dry_run:
                print(f"[DRY-RUN] Would assign task #{task['number']} to {ctx.author}")
            else:
                add_assignees(client, repo, int(task["number"]), [ctx.author])

        existing_pr_assignees = set(issue_assignee_logins(pr_issue))
        missing_assignees = [login for login in task_assignees if login not in existing_pr_assignees]
        if missing_assignees:
            if dry_run:
                print(f"[DRY-RUN] Would assign PR #{ctx.number} to {', '.join(missing_assignees)}")
            else:
                add_assignees(client, repo, ctx.number, missing_assignees)


def sync_parent_relationship(
    client: GitHubClient,
    repo: str,
    task: dict[str, Any],
    config: dict[str, Any],
    *,
    dry_run: bool = False,
) -> str:
    if not config.get("linkSubissues", True):
        return "disabled by configuration."
    parent_number = parent_issue_number(task.get("body") or "")
    if parent_number is None:
        return "no parent reference found."
    if dry_run:
        print(f"[DRY-RUN] Would link task #{task['number']} as sub-issue of #{parent_number}")
        return f"would ensure #{task['number']} is a sub-issue of #{parent_number}."
    try:
        add_sub_issue(client, repo, parent_number, int(task["number"]))
        return f"linked #{task['number']} under #{parent_number}."
    except Exception as exc:
        text = str(exc).casefold()
        if any(
            marker in text
            for marker in ("already", "exists", "duplicate sub-issues", "may only have one parent")
        ):
            return f"already linked under a parent (requested #{parent_number})."
        if is_permission_error(exc):
            return f"not synchronized: token lacks permission ({exc})."
        raise


def normalized_option(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def status_option_id(field: dict[str, Any], desired: str) -> str | None:
    desired_normalized = normalized_option(desired)
    for option in field.get("options", []):
        if normalized_option(str(option.get("name", ""))) == desired_normalized:
            return str(option["id"])
    return option_id(field, desired)


def sync_project_status(
    project_client: GitHubClient,
    repo: str,
    task: dict[str, Any],
    project_number: int,
    desired_status: str,
    config: dict[str, Any],
    *,
    owner: str | None = None,
    dry_run: bool = False,
) -> str:
    if not config.get("syncProject", True):
        return "disabled by configuration."

    project_owner = owner or split_repo(repo)[0]
    project = find_project(project_client, project_owner, project_number)
    fields = {
        str(field["name"]): field
        for field in list_project_fields(project_client, str(project["id"]))
        if field and field.get("name")
    }
    field_name = str(config.get("projectStatusField") or "Status")
    status_field = fields.get(field_name)
    if not status_field:
        raise RuntimeError(f"Project field `{field_name}` was not found")

    selected = status_option_id(status_field, desired_status)
    if not selected:
        available = ", ".join(str(item.get("name")) for item in status_field.get("options", []))
        raise RuntimeError(
            f"Project status option `{desired_status}` was not found in `{field_name}`. "
            f"Available options: {available or '(none)'}"
        )

    task_node = task.get("node_id") or issue_node_id(project_client, repo, int(task["number"]))
    project_items = list_project_items(project_client, str(project["id"]))
    item_id = project_items.get(str(task_node))
    if not item_id:
        if dry_run:
            print(f"[DRY-RUN] Would add task #{task['number']} to Project v2 #{project_number}")
            item_id = f"dry-run-{task['number']}"
        else:
            item_id = add_issue_to_project(project_client, str(project["id"]), str(task_node))

    if dry_run:
        print(
            f"[DRY-RUN] Would set task #{task['number']} `{field_name}` "
            f"to `{desired_status}` in Project v2 #{project_number}"
        )
    else:
        update_single_select(
            project_client,
            str(project["id"]),
            str(item_id),
            str(status_field["id"]),
            selected,
        )
    return f"synced to `{desired_status}` in Project v2 #{project_number}."


def project_number_from_value(value: int | None) -> int | None:
    if value is not None:
        return value
    raw = os.getenv("PROJECT_SETUP_PROJECT_NUMBER")
    if raw is None or not raw.strip():
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError("PROJECT_SETUP_PROJECT_NUMBER must be an integer") from exc


def apply_pr_sync(
    client: GitHubClient,
    repo: str,
    event: dict[str, Any],
    config: dict[str, Any],
    *,
    project_client: GitHubClient | None = None,
    project_number: int | None = None,
    owner: str | None = None,
    dry_run: bool = False,
) -> int:
    ctx = context_from_event(event, client=client, repo=repo)

    if not config.get("enabled", True):
        print("PR Sync is disabled by project_setup.json.")
        return 0
    if not is_same_repository(ctx, repo):
        print("Skipping PR Sync for a fork pull request.")
        return 0
    if is_promotion_pull_request(ctx, config):
        print(f"Skipping PR Sync for promotion PR {ctx.head_ref} -> {ctx.base_ref}.")
        return 0

    task_number = linked_task_number(ctx.body)
    if task_number is None:
        message = "No linked implementation task was found in the pull request body."
        upsert_sync_comment(client, repo, ctx.number, render_failure_comment(message), dry_run=dry_run)
        return 1

    task = client.get_issue(repo, task_number)
    if "pull_request" in task:
        message = f"Linked item #{task_number} is a pull request, not an implementation issue/task."
        upsert_sync_comment(client, repo, ctx.number, render_failure_comment(message), dry_run=dry_run)
        return 1

    pr_issue = client.get_issue(repo, ctx.number)
    sync_pr_metadata(client, repo, ctx, task, pr_issue, config, dry_run=dry_run)
    parent_note = sync_parent_relationship(client, repo, task, config, dry_run=dry_run)

    desired_status = project_status_for_context(ctx, config)
    if not config.get("syncProject", True):
        project_note = "disabled by configuration."
    elif project_number is None:
        project_note = "skipped because `PROJECT_SETUP_PROJECT_NUMBER` is not configured."
    elif project_client is None:
        project_note = "skipped because `PROJECT_SETUP_PAT` is not configured."
    else:
        try:
            project_note = sync_project_status(
                project_client,
                repo,
                task,
                project_number,
                desired_status,
                config,
                owner=owner,
                dry_run=dry_run,
            )
        except Exception as exc:
            if not is_permission_error(exc):
                raise
            project_note = f"not synchronized: Project token lacks permission ({exc})."

    upsert_sync_comment(
        client,
        repo,
        ctx.number,
        render_success_comment(ctx, task_number, desired_status, project_note, parent_note),
        dry_run=dry_run,
    )
    return 0


def apply_pr_sync_from_path(
    client: GitHubClient,
    repo: str,
    event_path: str | os.PathLike[str],
    config_path: str | os.PathLike[str] = "project_setup.json",
    *,
    project_client: GitHubClient | None = None,
    project_number: int | None = None,
    owner: str | None = None,
    dry_run: bool = False,
) -> int:
    return apply_pr_sync(
        client,
        repo,
        load_event(event_path),
        load_sync_config(config_path),
        project_client=project_client,
        project_number=project_number,
        owner=owner,
        dry_run=dry_run,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Synchronize a pull request with its linked implementation task")
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
    return apply_pr_sync_from_path(
        client,
        args.repo,
        args.event_path,
        args.config,
        project_client=project_client,
        project_number=project_number_from_value(args.project_number),
        owner=args.owner,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
