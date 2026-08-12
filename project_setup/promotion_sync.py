from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

from .github import API_BASE, GitHubClient, split_repo
from .pr_sync import (
    PullRequestContext,
    add_assignees,
    context_from_event,
    is_permission_error,
    issue_assignee_logins,
    issue_label_names,
    issue_milestone_number,
    load_sync_config,
    project_status_for_context,
    status_option_id,
)
from .project import add_issue_to_project, find_project, list_project_fields, update_single_select
from .related_prs import (
    RELATED_PRS_MARKER,
    _promotion_link_marker,
    _render_promotion_link,
    _upsert_comment,
    is_promotion_context,
    load_related_prs_config,
    pr_numbers_from_body_sections,
)


@dataclass(frozen=True)
class PromotionMetadata:
    labels: list[str]
    label_conflicts: list[str]
    assignees: list[str]
    milestone_number: int | None
    milestone_title: str | None
    milestone_conflict: str | None


def _label_values(item: dict[str, Any], prefix: str) -> list[str]:
    return sorted(name for name in issue_label_names(item) if name.startswith(prefix))


def aggregate_promotion_metadata(
    related_items: list[dict[str, Any]],
    label_prefixes: list[str],
) -> PromotionMetadata:
    labels: list[str] = []
    label_conflicts: list[str] = []

    for prefix in label_prefixes:
        per_item = [_label_values(item, prefix) for item in related_items]
        if per_item and all(not values for values in per_item):
            continue
        if per_item and all(len(values) == 1 for values in per_item):
            values = {values[0] for values in per_item}
            if len(values) == 1:
                labels.append(next(iter(values)))
                continue
        if per_item:
            rendered = ", ".join("/".join(values) if values else "missing" for values in per_item)
            label_conflicts.append(f"{prefix} [{rendered}]")

    assignees: list[str] = []
    seen_assignees: set[str] = set()
    for item in related_items:
        for login in issue_assignee_logins(item):
            if login not in seen_assignees:
                seen_assignees.add(login)
                assignees.append(login)

    milestone_numbers = [issue_milestone_number(item) for item in related_items]
    milestone_number: int | None = None
    milestone_title: str | None = None
    milestone_conflict: str | None = None
    if milestone_numbers and all(number is None for number in milestone_numbers):
        pass
    elif milestone_numbers and milestone_numbers[0] is not None and all(
        number == milestone_numbers[0] for number in milestone_numbers
    ):
        milestone_number = milestone_numbers[0]
        milestone = related_items[0].get("milestone") or {}
        milestone_title = str(milestone.get("title") or "") or None
    elif milestone_numbers:
        rendered = ", ".join(str(number) if number is not None else "missing" for number in milestone_numbers)
        milestone_conflict = f"related PR milestones disagree [{rendered}]"

    return PromotionMetadata(
        labels=labels,
        label_conflicts=label_conflicts,
        assignees=assignees,
        milestone_number=milestone_number,
        milestone_title=milestone_title,
        milestone_conflict=milestone_conflict,
    )


def sync_promotion_native_metadata(
    client: GitHubClient,
    repo: str,
    ctx: PullRequestContext,
    pr_issue: dict[str, Any],
    metadata: PromotionMetadata,
    config: dict[str, Any],
    *,
    dry_run: bool = False,
) -> list[str]:
    notes: list[str] = []

    if config.get("syncLabels", True):
        prefixes = tuple(str(value) for value in config.get("labelPrefixes", []))
        existing = issue_label_names(pr_issue)
        unmanaged = sorted(name for name in existing if not name.startswith(prefixes))
        target = sorted(set(unmanaged + metadata.labels))
        if set(target) != existing:
            if dry_run:
                print(f"[DRY-RUN] Would set promotion PR #{ctx.number} labels: {', '.join(target) or '(none)'}")
            else:
                client.request_json(
                    "PUT",
                    f"{API_BASE}/repos/{repo}/issues/{ctx.number}/labels",
                    {"labels": target},
                )
        if metadata.labels:
            notes.append("labels=" + ", ".join(f"`{name}`" for name in metadata.labels))
        elif metadata.label_conflicts:
            notes.append("labels=not synchronized (no consensus)")
        else:
            notes.append("labels=none")

    if config.get("syncMilestone", True):
        current = issue_milestone_number(pr_issue)
        desired = metadata.milestone_number
        if desired != current:
            if dry_run:
                print(f"[DRY-RUN] Would set promotion PR #{ctx.number} milestone to {desired or 'none'}")
            else:
                client.update_issue(repo, ctx.number, {"milestone": desired})
        if desired is not None:
            notes.append(f"milestone=`{metadata.milestone_title or f'#{desired}'}`")
        elif metadata.milestone_conflict:
            notes.append("milestone=cleared (no consensus)")
        else:
            notes.append("milestone=none")

    if config.get("syncAssignees", True):
        current_assignees = set(issue_assignee_logins(pr_issue))
        missing = [login for login in metadata.assignees if login not in current_assignees]
        if missing:
            if dry_run:
                print(f"[DRY-RUN] Would assign promotion PR #{ctx.number} to {', '.join(missing)}")
            else:
                add_assignees(client, repo, ctx.number, missing)
        notes.append(
            "assignees=" + (", ".join(f"`{login}`" for login in metadata.assignees) if metadata.assignees else "none")
        )

    return notes


def list_project_content_items(client: GitHubClient, project_id: str) -> dict[str, str]:
    query = """
    query($project:ID!, $cursor:String) {
      node(id:$project) {
        ... on ProjectV2 {
          items(first:100,after:$cursor) {
            pageInfo { hasNextPage endCursor }
            nodes {
              id
              content {
                __typename
                ... on Issue { id }
                ... on PullRequest { id }
              }
            }
          }
        }
      }
    }
    """
    result: dict[str, str] = {}
    cursor = None
    while True:
        page = client.graphql(query, {"project": project_id, "cursor": cursor})["node"]["items"]
        for item in page["nodes"]:
            content = item.get("content") or {}
            if content.get("__typename") in {"Issue", "PullRequest"} and content.get("id"):
                result[str(content["id"])] = str(item["id"])
        if not page["pageInfo"]["hasNextPage"]:
            return result
        cursor = page["pageInfo"]["endCursor"]


def sync_promotion_project_status(
    project_client: GitHubClient,
    repo: str,
    ctx: PullRequestContext,
    pr_issue: dict[str, Any],
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

    pr_node = str(pr_issue.get("node_id") or "")
    if not pr_node:
        raise RuntimeError(f"Promotion PR #{ctx.number} has no GraphQL node id")
    current_items = list_project_content_items(project_client, str(project["id"]))
    item_id = current_items.get(pr_node)
    if not item_id:
        if dry_run:
            print(f"[DRY-RUN] Would add promotion PR #{ctx.number} to Project v2 #{project_number}")
            item_id = f"dry-run-pr-{ctx.number}"
        else:
            item_id = add_issue_to_project(project_client, str(project["id"]), pr_node)

    if dry_run:
        print(
            f"[DRY-RUN] Would set promotion PR #{ctx.number} `{field_name}` "
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
    return f"promotion PR synced to `{desired_status}` in Project v2 #{project_number}."


def _render_summary(
    ctx: PullRequestContext,
    state: str,
    related_numbers: list[int],
    metadata: PromotionMetadata,
    metadata_notes: list[str],
    project_note: str,
) -> str:
    lines = [
        RELATED_PRS_MARKER,
        "## Promotion Sync",
        "",
        f"- Promotion: `{ctx.head_ref} -> {ctx.base_ref}`",
        f"- State: `{state}`",
        "- Related PRs:",
        *[f"  - #{number}" for number in related_numbers],
        "- Native metadata:",
        *[f"  - {note}" for note in metadata_notes],
    ]
    for conflict in metadata.label_conflicts:
        lines.append(f"  - label conflict: `{conflict}`")
    if metadata.milestone_conflict:
        lines.append(f"  - milestone conflict: `{metadata.milestone_conflict}`")
    lines.append(f"- Project v2: {project_note}")
    return "\n".join(lines)


def apply_promotion_sync(
    client: GitHubClient,
    repo: str,
    event: dict[str, Any],
    *,
    config_path: str | os.PathLike[str] = "project_setup.json",
    project_client: GitHubClient | None = None,
    project_number: int | None = None,
    owner: str | None = None,
    dry_run: bool = False,
) -> int:
    ctx = context_from_event(event, client=client, repo=repo)
    if not is_promotion_context(ctx, config_path):
        return 0

    related_config = load_related_prs_config(config_path)
    related_numbers = pr_numbers_from_body_sections(
        ctx.body,
        [str(item) for item in related_config.get("bodySections", [])],
    )
    if not related_numbers:
        print(f"Promotion Sync: PR #{ctx.number} has no Related PRs context.")
        return 1

    sync_config = load_sync_config(config_path)
    related_items = [client.get_issue(repo, number) for number in related_numbers]
    metadata = aggregate_promotion_metadata(
        related_items,
        [str(value) for value in sync_config.get("labelPrefixes", [])],
    )
    pr_issue = client.get_issue(repo, ctx.number)
    metadata_notes = sync_promotion_native_metadata(
        client,
        repo,
        ctx,
        pr_issue,
        metadata,
        sync_config,
        dry_run=dry_run,
    )

    desired_status = project_status_for_context(ctx, sync_config)
    if not sync_config.get("syncProject", True):
        project_note = "disabled by configuration."
    elif project_number is None:
        project_note = "skipped because `PROJECT_SETUP_PROJECT_NUMBER` is not configured."
    elif project_client is None:
        project_note = "skipped because `PROJECT_SETUP_PAT` is not configured."
    else:
        try:
            project_note = sync_promotion_project_status(
                project_client,
                repo,
                ctx,
                pr_issue,
                project_number,
                desired_status,
                sync_config,
                owner=owner,
                dry_run=dry_run,
            )
        except Exception as exc:
            if not is_permission_error(exc):
                raise
            project_note = f"not synchronized: Project token lacks permission ({exc})."

    state = "merged" if ctx.action == "closed" and ctx.merged else "planned"
    marker = _promotion_link_marker(ctx.base_ref)
    backlink = _render_promotion_link(ctx, state)
    for number in related_numbers:
        _upsert_comment(client, repo, number, marker, backlink, dry_run=dry_run)

    _upsert_comment(
        client,
        repo,
        ctx.number,
        RELATED_PRS_MARKER,
        _render_summary(ctx, state, related_numbers, metadata, metadata_notes, project_note),
        dry_run=dry_run,
    )
    return 0
