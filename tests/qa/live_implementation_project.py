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
from project_setup.pr_sync_router import apply_routed_pr_sync
from project_setup.project import create_project, ensure_fields, resolve_owner_type


PREFIX = "QA Implementation Project "
BRANCH_PREFIX = "qa/implementation-project/"
TIMEOUT_SECONDS = 20.0


def list_projects(client: GitHubClient, owner: str, owner_type: str) -> list[dict]:
    query = f"""
    query($login:String!, $cursor:String) {{
      {owner_type}(login:$login) {{
        projectsV2(first:100, after:$cursor) {{
          pageInfo {{ hasNextPage endCursor }}
          nodes {{ id number title }}
        }}
      }}
    }}
    """
    result: list[dict] = []
    cursor = None
    while True:
        page = client.graphql(query, {"login": owner, "cursor": cursor})[owner_type]["projectsV2"]
        result.extend(item for item in page["nodes"] if item)
        if not page["pageInfo"]["hasNextPage"]:
            return result
        cursor = page["pageInfo"]["endCursor"]


def delete_project(client: GitHubClient, project_id: str) -> None:
    client.graphql(
        "mutation($project:ID!){deleteProjectV2(input:{projectId:$project}){projectV2{id}}}",
        {"project": project_id},
    )


def project_statuses(client: GitHubClient, project_id: str, repo: str) -> dict[tuple[str, int], str | None]:
    query = """
    query($project:ID!, $cursor:String) {
      node(id:$project) {
        ... on ProjectV2 {
          items(first:100,after:$cursor) {
            pageInfo { hasNextPage endCursor }
            nodes {
              content {
                __typename
                ... on Issue { number repository { nameWithOwner } }
                ... on PullRequest { number repository { nameWithOwner } }
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
    result: dict[tuple[str, int], str | None] = {}
    cursor = None
    while True:
        page = client.graphql(query, {"project": project_id, "cursor": cursor})["node"]["items"]
        for item in page["nodes"]:
            content = item.get("content") or {}
            repository = content.get("repository") or {}
            if str(repository.get("nameWithOwner") or "").casefold() != repo.casefold():
                continue
            kind = str(content.get("__typename") or "")
            number = int(content.get("number") or 0)
            if kind not in {"Issue", "PullRequest"} or not number:
                continue
            status = None
            for value in (item.get("fieldValues") or {}).get("nodes", []):
                if value and ((value.get("field") or {}).get("name") == "Status"):
                    status = str(value.get("name") or "") or None
                    break
            result[(kind, number)] = status
        if not page["pageInfo"]["hasNextPage"]:
            return result
        cursor = page["pageInfo"]["endCursor"]


def wait_for_items(client: GitHubClient, project_id: str, repo: str, issue_number: int, pr_number: int) -> bool:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while True:
        statuses = project_statuses(client, project_id, repo)
        if statuses.get(("Issue", issue_number)) == "In review" and statuses.get(("PullRequest", pr_number)) == "In review":
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(1.0)


def ref_path(branch: str) -> str:
    return urllib.parse.quote(f"heads/{branch}", safe="/")


def create_branch(client: GitHubClient, repo: str, branch: str, sha: str) -> None:
    client.request_json("POST", f"{API_BASE}/repos/{repo}/git/refs", {"ref": f"refs/heads/{branch}", "sha": sha})


def delete_branch(client: GitHubClient, repo: str, branch: str) -> None:
    client.request_json("DELETE", f"{API_BASE}/repos/{repo}/git/refs/{ref_path(branch)}")


def branch_sha(client: GitHubClient, repo: str, branch: str) -> str:
    return str(client.request_json("GET", f"{API_BASE}/repos/{repo}/git/ref/{ref_path(branch)}")["object"]["sha"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Live implementation PR Project v2 membership validation")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if args.repo.casefold() == os.getenv("GITHUB_REPOSITORY", "").casefold():
        raise SystemExit("Refusing implementation Project live test against GPA source repository")
    token = os.getenv("PROJECT_SETUP_PAT", "").strip()
    if not token:
        raise SystemExit("PROJECT_SETUP_PAT is required")

    client = GitHubClient(token)
    owner, _ = split_repo(args.repo)
    owner_type = resolve_owner_type(client, owner)
    suffix = re.sub(r"[^A-Za-z0-9_.-]+", "-", args.run_id).strip("-")[:32] or "manual"
    project_title = f"{PREFIX}{suffix}"
    issue_number: int | None = None
    pr_number: int | None = None
    project_id: str | None = None
    branches: list[str] = []
    primary_error: Exception | None = None
    cleanup_errors: list[str] = []

    try:
        with tempfile.TemporaryDirectory() as tempdir:
            definition = Path(tempdir) / "project.json"
            definition.write_text(
                json.dumps({"name": project_title, "fields": [{"name": "Status", "type": "single_select", "options": ["In progress", "In review", "Done"]}]}),
                encoding="utf-8",
            )
            create_project(client, args.repo, str(definition), owner_type=owner_type)
        project = next(item for item in list_projects(client, owner, owner_type) if item.get("title") == project_title)
        project_id = str(project["id"])
        project_number = int(project["number"])
        ensure_fields(client, project_id, {"fields": [{"name": "Status", "type": "single_select", "options": ["In progress", "In review", "Done"]}]})

        issue = client.request_json("POST", f"{API_BASE}/repos/{args.repo}/issues", {"title": f"{PREFIX}task {suffix}", "body": "Disposable implementation Project item test."})
        issue_number = int(issue["number"])
        repository = client.request_json("GET", f"{API_BASE}/repos/{args.repo}")
        default_branch = str(repository["default_branch"])
        root = branch_sha(client, args.repo, default_branch)
        base = f"{BRANCH_PREFIX}base-{suffix}"
        head = f"{BRANCH_PREFIX}head-{suffix}"
        create_branch(client, args.repo, base, root)
        branches.append(base)
        create_branch(client, args.repo, head, root)
        branches.append(head)
        marker = f"qa-implementation-project-{suffix}.txt"
        client.request_json(
            "PUT",
            f"{API_BASE}/repos/{args.repo}/contents/{urllib.parse.quote(marker, safe='')}",
            {"message": f"test: implementation Project {suffix}", "content": base64.b64encode(b"implementation-project\n").decode(), "branch": head},
        )
        pr = client.request_json(
            "POST",
            f"{API_BASE}/repos/{args.repo}/pulls",
            {"title": f"{PREFIX}PR {suffix}", "head": head, "base": base, "body": f"## Linked Issue\n- Closes #{issue_number}\n\n## Milestone\n- None\n"},
        )
        pr_number = int(pr["number"])

        with tempfile.TemporaryDirectory() as tempdir:
            config = Path(tempdir) / "project_setup.json"
            config.write_text(
                json.dumps({"prAutomation": {"sync": {"enabled": True, "syncLabels": False, "syncMilestone": False, "syncAssignees": False, "linkSubissues": False, "syncProject": True, "promotionPaths": [{"head": "develop", "base": "Q.A"}, {"head": "Q.A", "base": "main"}], "projectStatusField": "Status", "projectStatus": {"draft": "In progress", "review": "In review", "closed": "In progress", "merged": "Done"}}}}),
                encoding="utf-8",
            )
            result = apply_routed_pr_sync(
                client,
                args.repo,
                {"action": "opened", "pull_request": pr},
                config_path=str(config),
                project_client=client,
                project_number=project_number,
                owner=owner,
            )
        if result != 0:
            raise RuntimeError(f"Routed implementation PR Sync returned {result}")
        if not wait_for_items(client, project_id, args.repo, issue_number, pr_number):
            raise RuntimeError("Issue and implementation PR did not both converge to In review in Project v2")
        print("implementation_task_project_status=passed")
        print("implementation_pr_project_status=passed")
        print("implementation_pr_projects_sidebar_contract=passed")

    except Exception as exc:
        primary_error = exc

    if pr_number is not None:
        try:
            client.request_json("PATCH", f"{API_BASE}/repos/{args.repo}/pulls/{pr_number}", {"state": "closed"})
        except Exception as exc:
            cleanup_errors.append(f"PR: {exc}")
    if issue_number is not None:
        try:
            client.update_issue(args.repo, issue_number, {"state": "closed"})
        except Exception as exc:
            cleanup_errors.append(f"issue: {exc}")
    for branch in reversed(branches):
        try:
            delete_branch(client, args.repo, branch)
        except Exception as exc:
            cleanup_errors.append(f"branch {branch}: {exc}")
    if project_id is not None:
        try:
            delete_project(client, project_id)
        except Exception as exc:
            cleanup_errors.append(f"project: {exc}")

    if primary_error:
        if cleanup_errors:
            print("warning: cleanup also failed: " + "; ".join(cleanup_errors))
        raise primary_error
    if cleanup_errors:
        raise RuntimeError("Implementation Project cleanup failed: " + "; ".join(cleanup_errors))
    print("implementation_project_cleanup=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
