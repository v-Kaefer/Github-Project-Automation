from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import re
import tempfile
import time
import urllib.parse

from project_setup.github import API_BASE, GitHubClient, split_repo
from project_setup.pr_sync import DEFAULT_SYNC_CONFIG, apply_pr_sync
from project_setup.project import create_project, ensure_fields, issue_node_id, list_project_items, resolve_owner_type


QA_SYNC_LABEL_MARKER = ":qa-sync-"
QA_SYNC_MILESTONE_PREFIX = "QA-SYNC-"
QA_SYNC_PROJECT_PREFIX = "QA PR Sync validation "
QA_SYNC_ISSUE_PREFIX = "QA PR Sync task "
QA_SYNC_PR_PREFIX = "QA PR Sync validation "
QA_SYNC_BRANCH_PREFIX = "qa/pr-sync/"
PROJECT_READBACK_TIMEOUT_SECONDS = 20.0
PROJECT_READBACK_INTERVAL_SECONDS = 1.0


def require_sandbox(repo: str) -> None:
    current_repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    if not repo:
        raise SystemExit("QA_REPOSITORY is missing. Configure it in the `qa` Environment.")
    if "/" not in repo:
        raise SystemExit("QA_REPOSITORY must use owner/repository format.")
    if current_repo and repo.casefold() == current_repo.casefold():
        raise SystemExit("Refusing live PR Sync validation against the GPA source repository.")
    if not os.getenv("PROJECT_SETUP_PAT", "").strip():
        raise SystemExit("QA_PROJECT_SETUP_PAT is required for live PR Sync validation.")


def list_projects(client: GitHubClient, owner: str, owner_type: str) -> list[dict]:
    query = f"""
    query($login:String!, $cursor:String) {{
      {owner_type}(login:$login) {{
        projectsV2(first:100, after:$cursor) {{
          pageInfo {{ hasNextPage endCursor }}
          nodes {{ id number title url }}
        }}
      }}
    }}
    """
    projects: list[dict] = []
    cursor = None
    while True:
        data = client.graphql(query, {"login": owner, "cursor": cursor})
        node = data.get(owner_type)
        if not node:
            return projects
        page = node["projectsV2"]
        projects.extend(project for project in page["nodes"] if project)
        if not page["pageInfo"]["hasNextPage"]:
            return projects
        cursor = page["pageInfo"]["endCursor"]


def project_by_title(client: GitHubClient, owner: str, owner_type: str, title: str) -> dict | None:
    return next((project for project in list_projects(client, owner, owner_type) if project.get("title") == title), None)


def delete_project(client: GitHubClient, project_id: str) -> None:
    mutation = """
    mutation($project:ID!) {
      deleteProjectV2(input:{projectId:$project}) { projectV2 { id } }
    }
    """
    client.graphql(mutation, {"project": project_id})


def encoded_ref(branch: str) -> str:
    return urllib.parse.quote(f"heads/{branch}", safe="/")


def branch_sha(client: GitHubClient, repo: str, branch: str) -> str:
    ref = client.request_json("GET", f"{API_BASE}/repos/{repo}/git/ref/{encoded_ref(branch)}")
    return str((ref.get("object") or {})["sha"])


def create_branch(client: GitHubClient, repo: str, branch: str, sha: str) -> None:
    client.request_json(
        "POST",
        f"{API_BASE}/repos/{repo}/git/refs",
        {"ref": f"refs/heads/{branch}", "sha": sha},
    )


def delete_branch(client: GitHubClient, repo: str, branch: str) -> None:
    client.request_json("DELETE", f"{API_BASE}/repos/{repo}/git/refs/{encoded_ref(branch)}")


def project_item_status(
    client: GitHubClient,
    project_id: str,
    repo: str,
    issue_number: int,
    field_name: str = "Status",
) -> str | None:
    query = """
    query($project:ID!, $cursor:String) {
      node(id:$project) {
        ... on ProjectV2 {
          items(first:100, after:$cursor) {
            pageInfo { hasNextPage endCursor }
            nodes {
              content {
                __typename
                ... on Issue { number repository { nameWithOwner } }
              }
              fieldValues(first:50) {
                nodes {
                  ... on ProjectV2ItemFieldSingleSelectValue {
                    name
                    field { ... on ProjectV2SingleSelectField { name } }
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    cursor = None
    while True:
        page = client.graphql(query, {"project": project_id, "cursor": cursor})["node"]["items"]
        for item in page["nodes"]:
            content = item.get("content") or {}
            repository = content.get("repository") or {}
            if (
                content.get("__typename") == "Issue"
                and int(content.get("number") or 0) == issue_number
                and str(repository.get("nameWithOwner") or "").casefold() == repo.casefold()
            ):
                for value in (item.get("fieldValues") or {}).get("nodes", []):
                    if not value:
                        continue
                    field = value.get("field") or {}
                    if field.get("name") == field_name:
                        return str(value.get("name") or "") or None
                return None
        if not page["pageInfo"]["hasNextPage"]:
            return None
        cursor = page["pageInfo"]["endCursor"]


def wait_for_project_task_status(
    client: GitHubClient,
    project_id: str,
    repo: str,
    issue_number: int,
    expected_status: str,
    *,
    timeout_seconds: float = PROJECT_READBACK_TIMEOUT_SECONDS,
    interval_seconds: float = PROJECT_READBACK_INTERVAL_SECONDS,
) -> tuple[bool, str | None]:
    task_node = issue_node_id(client, repo, issue_number)
    deadline = time.monotonic() + timeout_seconds
    last_status: str | None = None
    while True:
        project_items = list_project_items(client, project_id)
        if task_node in project_items:
            last_status = project_item_status(client, project_id, repo, issue_number)
            if last_status == expected_status:
                return True, last_status
        if time.monotonic() >= deadline:
            return False, last_status
        time.sleep(interval_seconds)


def cleanup_stale_resources(client: GitHubClient, repo: str, owner: str, owner_type: str) -> None:
    for pr in client.paginated(f"{API_BASE}/repos/{repo}/pulls?state=open"):
        if str(pr.get("title") or "").startswith(QA_SYNC_PR_PREFIX):
            client.request_json("PATCH", f"{API_BASE}/repos/{repo}/pulls/{pr['number']}", {"state": "closed"})

    for issue in client.paginated(f"{API_BASE}/repos/{repo}/issues?state=open"):
        if "pull_request" in issue:
            continue
        if str(issue.get("title") or "").startswith(QA_SYNC_ISSUE_PREFIX):
            client.update_issue(repo, int(issue["number"]), {"state": "closed"})

    for project in list_projects(client, owner, owner_type):
        if str(project.get("title") or "").startswith(QA_SYNC_PROJECT_PREFIX):
            delete_project(client, str(project["id"]))

    for milestone in client.paginated(f"{API_BASE}/repos/{repo}/milestones?state=all"):
        if str(milestone.get("title") or "").startswith(QA_SYNC_MILESTONE_PREFIX):
            client.request_json("DELETE", f"{API_BASE}/repos/{repo}/milestones/{milestone['number']}")

    for label in client.paginated(f"{API_BASE}/repos/{repo}/labels"):
        name = str(label.get("name") or "")
        if QA_SYNC_LABEL_MARKER in name:
            encoded = urllib.parse.quote(name, safe="")
            client.request_json("DELETE", f"{API_BASE}/repos/{repo}/labels/{encoded}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Live, self-cleaning PR Sync structured metadata validation")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    require_sandbox(args.repo)
    token = os.environ["PROJECT_SETUP_PAT"].strip()
    client = GitHubClient(token)
    owner, _ = split_repo(args.repo)
    owner_type = resolve_owner_type(client, owner)
    suffix = re.sub(r"[^A-Za-z0-9_.-]+", "-", args.run_id).strip("-")[:36] or "manual"

    labels = [
        f"type:qa-sync-{suffix}",
        f"priority:qa-sync-{suffix}",
        f"test:qa-sync-{suffix}",
    ]
    milestone_title = f"{QA_SYNC_MILESTONE_PREFIX}{suffix}"
    project_title = f"{QA_SYNC_PROJECT_PREFIX}{suffix}"
    issue_title = f"{QA_SYNC_ISSUE_PREFIX}{suffix}"
    pr_title = f"{QA_SYNC_PR_PREFIX}{suffix}"
    base_branch = f"{QA_SYNC_BRANCH_PREFIX}base-{suffix}"
    head_branch = f"{QA_SYNC_BRANCH_PREFIX}head-{suffix}"
    marker_path = f"qa-pr-sync-{suffix}.txt"

    created_project_id: str | None = None
    created_project_number: int | None = None
    created_milestone_number: int | None = None
    created_issue_number: int | None = None
    created_pr_number: int | None = None
    created_branches: list[str] = []
    primary_error: Exception | None = None
    cleanup_errors: list[str] = []

    cleanup_stale_resources(client, args.repo, owner, owner_type)

    try:
        for index, label_name in enumerate(labels):
            client.request_json(
                "POST",
                f"{API_BASE}/repos/{args.repo}/labels",
                {
                    "name": label_name,
                    "color": ("1D76DB", "B60205", "0366D6")[index],
                    "description": "Disposable GPA PR Sync Q.A label",
                },
            )

        milestone = client.request_json(
            "POST",
            f"{API_BASE}/repos/{args.repo}/milestones",
            {"title": milestone_title, "description": "Disposable GPA PR Sync Q.A milestone"},
        )
        created_milestone_number = int(milestone["number"])

        with tempfile.TemporaryDirectory() as temporary_directory:
            project_file = Path(temporary_directory) / "project.json"
            project_file.write_text(
                json.dumps(
                    {
                        "name": project_title,
                        "fields": [
                            {
                                "name": "Status",
                                "type": "single_select",
                                "options": ["In progress", "In review", "Done"],
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            create_project(client, args.repo, str(project_file), dry_run=False, owner_type=owner_type)

        project = project_by_title(client, owner, owner_type, project_title)
        if not project:
            raise RuntimeError("PR Sync Q.A Project v2 creation verification failed")
        created_project_id = str(project["id"])
        created_project_number = int(project["number"])
        ensure_fields(
            client,
            created_project_id,
            {
                "fields": [
                    {
                        "name": "Status",
                        "type": "single_select",
                        "options": ["In progress", "In review", "Done"],
                    }
                ]
            },
            dry_run=False,
        )

        issue = client.request_json(
            "POST",
            f"{API_BASE}/repos/{args.repo}/issues",
            {
                "title": issue_title,
                "body": "Disposable implementation task for GPA PR Sync live validation.",
                "labels": labels,
                "milestone": created_milestone_number,
            },
        )
        created_issue_number = int(issue["number"])

        repository = client.request_json("GET", f"{API_BASE}/repos/{args.repo}")
        default_branch = str(repository["default_branch"])
        root_sha = branch_sha(client, args.repo, default_branch)

        create_branch(client, args.repo, base_branch, root_sha)
        created_branches.append(base_branch)
        create_branch(client, args.repo, head_branch, root_sha)
        created_branches.append(head_branch)

        client.request_json(
            "PUT",
            f"{API_BASE}/repos/{args.repo}/contents/{urllib.parse.quote(marker_path, safe='')}",
            {
                "message": f"test: PR Sync structured metadata {suffix}",
                "content": base64.b64encode(f"GPA PR Sync live validation {suffix}\n".encode()).decode(),
                "branch": head_branch,
            },
        )

        pr = client.request_json(
            "POST",
            f"{API_BASE}/repos/{args.repo}/pulls",
            {
                "title": pr_title,
                "head": head_branch,
                "base": base_branch,
                "body": (
                    f"## Linked Issue\n- Closes #{created_issue_number}\n\n"
                    f"## Milestone\n- {milestone_title}\n\n"
                    "## Summary\n- Disposable non-default-branch PR Sync validation.\n"
                ),
            },
        )
        created_pr_number = int(pr["number"])
        if str((pr.get("base") or {}).get("ref") or "") == default_branch:
            raise RuntimeError("Live PR Sync test must target a non-default branch")

        config = dict(DEFAULT_SYNC_CONFIG)
        config["labelPrefixes"] = ["type:", "priority:", "test:"]
        config["syncProject"] = True
        result = apply_pr_sync(
            client,
            args.repo,
            {"action": "opened", "pull_request": pr},
            config,
            project_client=client,
            project_number=created_project_number,
            owner=owner,
            dry_run=False,
        )
        if result != 0:
            raise RuntimeError(f"PR Sync returned {result} during live structured metadata validation")

        pr_issue = client.get_issue(args.repo, created_pr_number)
        pr_labels = {str(label.get("name") or "") for label in pr_issue.get("labels", [])}
        missing_labels = [label for label in labels if label not in pr_labels]
        if missing_labels:
            raise RuntimeError(f"PR labels were not synchronized: {', '.join(missing_labels)}")
        print("pr_labels=passed")

        pr_milestone = pr_issue.get("milestone") or {}
        if int(pr_milestone.get("number") or 0) != created_milestone_number:
            raise RuntimeError("PR milestone was not synchronized")
        print("pr_milestone=passed")

        pr_author = str((pr.get("user") or {}).get("login") or "")
        pr_assignees = {str(item.get("login") or "") for item in pr_issue.get("assignees", [])}
        task = client.get_issue(args.repo, created_issue_number)
        task_assignees = {str(item.get("login") or "") for item in task.get("assignees", [])}
        if not pr_author or pr_author not in pr_assignees or pr_author not in task_assignees:
            raise RuntimeError("PR/task assignee fallback was not synchronized")
        print("pr_assignees=passed")

        project_converged, visible_status = wait_for_project_task_status(
            client,
            created_project_id,
            args.repo,
            created_issue_number,
            "In review",
        )
        if not project_converged:
            raise RuntimeError(
                "Project v2 task/status did not converge after synchronization; "
                f"last visible status: {visible_status or '(task not visible)'}"
            )
        print("project_v2_task_status=passed")
        print("non_default_base_branch=passed")
        print("pr_sync_structured_metadata=passed")

    except Exception as exc:
        primary_error = exc

    if created_pr_number is not None:
        try:
            client.request_json("PATCH", f"{API_BASE}/repos/{args.repo}/pulls/{created_pr_number}", {"state": "closed"})
        except Exception as exc:
            cleanup_errors.append(f"pull request: {exc}")

    if created_issue_number is not None:
        try:
            client.update_issue(args.repo, created_issue_number, {"state": "closed"})
        except Exception as exc:
            cleanup_errors.append(f"issue: {exc}")

    for branch in reversed(created_branches):
        try:
            delete_branch(client, args.repo, branch)
        except Exception as exc:
            cleanup_errors.append(f"branch `{branch}`: {exc}")

    if created_project_id is not None:
        try:
            delete_project(client, created_project_id)
        except Exception as exc:
            cleanup_errors.append(f"project: {exc}")

    if created_milestone_number is not None:
        try:
            client.request_json("DELETE", f"{API_BASE}/repos/{args.repo}/milestones/{created_milestone_number}")
        except Exception as exc:
            cleanup_errors.append(f"milestone: {exc}")

    for label_name in labels:
        try:
            encoded = urllib.parse.quote(label_name, safe="")
            client.request_json("DELETE", f"{API_BASE}/repos/{args.repo}/labels/{encoded}")
        except Exception as exc:
            cleanup_errors.append(f"label `{label_name}`: {exc}")

    if primary_error:
        if cleanup_errors:
            print("warning: cleanup also failed: " + "; ".join(cleanup_errors))
        raise primary_error
    if cleanup_errors:
        raise RuntimeError("PR Sync Q.A cleanup failed: " + "; ".join(cleanup_errors))

    print("pr_sync_cleanup=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())