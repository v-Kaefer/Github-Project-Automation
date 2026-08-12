from __future__ import annotations

from typing import Any

from .github import GitHubClient, split_repo
from .pr_sync import PullRequestContext, status_option_id
from .project import add_issue_to_project, find_project, list_project_fields, update_single_select


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


def sync_pull_request_project_status(
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
        raise RuntimeError(f"PR #{ctx.number} has no GraphQL node id")

    current_items = list_project_content_items(project_client, str(project["id"]))
    item_id = current_items.get(pr_node)
    if not item_id:
        if dry_run:
            print(f"[DRY-RUN] Would add PR #{ctx.number} to Project v2 #{project_number}")
            item_id = f"dry-run-pr-{ctx.number}"
        else:
            item_id = add_issue_to_project(project_client, str(project["id"]), pr_node)

    if dry_run:
        print(
            f"[DRY-RUN] Would set PR #{ctx.number} `{field_name}` "
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
    return f"PR #{ctx.number} synced to `{desired_status}` in Project v2 #{project_number}."
