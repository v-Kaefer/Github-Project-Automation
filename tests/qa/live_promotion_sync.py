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

from project_setup.github import API_BASE, GitHubClient, GitHubRequestError, split_repo
from project_setup.pr_sync import DEFAULT_SYNC_CONFIG, apply_pr_sync
from project_setup.pr_sync_router import apply_routed_pr_sync
from project_setup.project import create_project, ensure_fields, resolve_owner_type


QA_LABEL_MARKER = ":qa-promotion-"
QA_MILESTONE_PREFIX = "QA-PROMOTION-"
QA_PROJECT_PREFIX = "QA Promotion Sync validation "
QA_ISSUE_PREFIX = "QA Promotion Sync task "
QA_IMPL_PR_PREFIX = "QA Promotion implementation "
QA_PROMOTION_PR_PREFIX = "QA Promotion aggregate "
QA_BRANCH_PREFIX = "qa/promotion-sync/"
PROJECT_READBACK_TIMEOUT_SECONDS = 20.0
PROJECT_READBACK_INTERVAL_SECONDS = 1.0


def require_sandbox(repo: str) -> None:
    current_repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    if not repo:
        raise SystemExit("QA_REPOSITORY is missing. Configure it in the `qa` Environment.")
    if "/" not in repo:
        raise SystemExit("QA_REPOSITORY must use owner/repository format.")
    if current_repo and repo.casefold() == current_repo.casefold():
        raise SystemExit("Refusing live Promotion Sync validation against the GPA source repository.")
    if not os.getenv("PROJECT_SETUP_PAT", "").strip():
        raise SystemExit("QA_PROJECT_SETUP_PAT is required for live Promotion Sync validation.")


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


def create_marker_commit(client: GitHubClient, repo: str, branch: str, path: str, content: str, message: str) -> None:
    client.request_json(
        "PUT",
        f"{API_BASE}/repos/{repo}/contents/{urllib.parse.quote(path, safe='')}",
        {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "branch": branch,
        },
    )


def project_pull_request_status(
    client: GitHubClient,
    project_id: str,
    repo: str,
    pr_number: int,
    field_name: str = "Status",
) -> tuple[bool, str | None]:
    query = """
    query($project:ID!, $cursor:String) {
      node(id:$project) {
        ... on ProjectV2 {
          items(first:100, after:$cursor) {
            pageInfo { hasNextPage endCursor }
            nodes {
              content {
                __typename
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
    cursor = None
    while True:
        page = client.graphql(query, {"project": project_id, "cursor": cursor})["node"]["items"]
        for item in page["nodes"]:
            content = item.get("content") or {}
            repository = content.get("repository") or {}
            if (
                content.get("__typename") == "PullRequest"
                and int(content.get("number") or 0) == pr_number
                and str(repository.get("nameWithOwner") or "").casefold() == repo.casefold()
            ):
                for value in (item.get("fieldValues") or {}).get("nodes", []):
                    if not value:
                        continue
                    field = value.get("field") or {}
                    if field.get("name") == field_name:
                        return True, str(value.get("name") or "") or None
                return True, None
        if not page["pageInfo"]["hasNextPage"]:
            return False, None
        cursor = page["pageInfo"]["endCursor"]


def wait_for_project_pr_status(
    client: GitHubClient,
    project_id: str,
    repo: str,
    pr_number: int,
    expected_status: str,
) -> tuple[bool, str | None]:
    deadline = time.monotonic() + PROJECT_READBACK_TIMEOUT_SECONDS
    last_status: str | None = None
    while True:
        found, last_status = project_pull_request_status(client, project_id, repo, pr_number)
        if found and last_status == expected_status:
            return True, last_status
        if time.monotonic() >= deadline:
            return False, last_status
        time.sleep(PROJECT_READBACK_INTERVAL_SECONDS)


def cleanup_stale_resources(client: GitHubClient, repo: str, owner: str, owner_type: str) -> None:
    for pr in client.paginated(f"{API_BASE}/repos/{repo}/pulls?state=open"):
        title = str(pr.get("title") or "")
        if title.startswith(QA_IMPL_PR_PREFIX) or title.startswith(QA_PROMOTION_PR_PREFIX):
            client.request_json("PATCH", f"{API_BASE}/repos/{repo}/pulls/{pr['number']}", {"state": "closed"})

    for issue in client.paginated(f"{API_BASE}/repos/{repo}/issues?state=open"):
        if "pull_request" in issue:
            continue
        if str(issue.get("title") or "").startswith(QA_ISSUE_PREFIX):
            client.update_issue(repo, int(issue["number"]), {"state": "closed"})

    for project in list_projects(client, owner, owner_type):
        if str(project.get("title") or "").startswith(QA_PROJECT_PREFIX):
            delete_project(client, str(project["id"]))

    for milestone in client.paginated(f"{API_BASE}/repos/{repo}/milestones?state=all"):
        if str(milestone.get("title") or "").startswith(QA_MILESTONE_PREFIX):
            client.request_json("DELETE", f"{API_BASE}/repos/{repo}/milestones/{milestone['number']}")

    for label in client.paginated(f"{API_BASE}/repos/{repo}/labels"):
        name = str(label.get("name") or "")
        if QA_LABEL_MARKER in name:
            client.request_json("DELETE", f"{API_BASE}/repos/{repo}/labels/{urllib.parse.quote(name, safe='')}")

    refs = client.request_json(
        "GET",
        f"{API_BASE}/repos/{repo}/git/matching-refs/{urllib.parse.quote('heads/' + QA_BRANCH_PREFIX, safe='/')}",
    )
    for ref in refs if isinstance(refs, list) else []:
        name = str(ref.get("ref") or "")
        if name.startswith("refs/heads/"):
            try:
                delete_branch(client, repo, name.removeprefix("refs/heads/"))
            except Exception:
                pass


def create_implementation(
    client: GitHubClient,
    repo: str,
    source_branch: str,
    branch: str,
    issue_number: int,
    milestone_title: str,
    marker_path: str,
    suffix: str,
    project_number: int,
    owner: str,
) -> int:
    create_branch(client, repo, branch, branch_sha(client, repo, source_branch))
    create_marker_commit(
        client,
        repo,
        branch,
        marker_path,
        f"Promotion Sync implementation marker {suffix}\n",
        f"test: promotion implementation {suffix}",
    )
    pr = client.request_json(
        "POST",
        f"{API_BASE}/repos/{repo}/pulls",
        {
            "title": f"{QA_IMPL_PR_PREFIX}{suffix}",
            "head": branch,
            "base": source_branch,
            "body": (
                f"## Linked Issue\n- Closes #{issue_number}\n\n"
                f"## Milestone\n- {milestone_title}\n\n"
                "## Summary\n- Disposable Promotion Sync constituent.\n"
            ),
        },
    )
    result = apply_pr_sync(
        client,
        repo,
        {"action": "opened", "pull_request": pr},
        dict(DEFAULT_SYNC_CONFIG),
        project_client=client,
        project_number=project_number,
        owner=owner,
        dry_run=False,
    )
    if result != 0:
        raise RuntimeError(f"Implementation PR Sync returned {result}")
    merge = client.request_json(
        "PUT",
        f"{API_BASE}/repos/{repo}/pulls/{pr['number']}/merge",
        {"merge_method": "merge"},
    )
    if not merge.get("merged"):
        raise RuntimeError(f"Failed to merge disposable implementation PR #{pr['number']}")
    return int(pr["number"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Live Promotion Sync native metadata and Project v2 validation")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    require_sandbox(args.repo)
    client = GitHubClient(os.environ["PROJECT_SETUP_PAT"].strip())
    owner, _ = split_repo(args.repo)
    owner_type = resolve_owner_type(client, owner)
    suffix = re.sub(r"[^A-Za-z0-9_.-]+", "-", args.run_id).strip("-")[:30] or "manual"

    labels = [
        f"type:qa-promotion-{suffix}",
        f"priority:qa-promotion-{suffix}",
        f"test:qa-promotion-{suffix}",
    ]
    milestone_title = f"{QA_MILESTONE_PREFIX}{suffix}"
    project_title = f"{QA_PROJECT_PREFIX}{suffix}"
    base_branch = f"{QA_BRANCH_PREFIX}base-{suffix}"
    source_branch = f"{QA_BRANCH_PREFIX}source-{suffix}"
    impl_branches = [
        f"{QA_BRANCH_PREFIX}feat-a-{suffix}",
        f"{QA_BRANCH_PREFIX}fix-b-{suffix}",
    ]

    created_project_id: str | None = None
    created_project_number: int | None = None
    created_milestone_number: int | None = None
    created_issue_numbers: list[int] = []
    created_pr_numbers: list[int] = []
    created_branches: list[str] = []
    primary_error: Exception | None = None
    cleanup_errors: list[str] = []

    cleanup_stale_resources(client, args.repo, owner, owner_type)

    try:
        for label_name in labels:
            client.request_json(
                "POST",
                f"{API_BASE}/repos/{args.repo}/labels",
                {"name": label_name, "color": "ededed", "description": "Disposable Promotion Sync Q.A label"},
            )

        milestone = client.request_json(
            "POST",
            f"{API_BASE}/repos/{args.repo}/milestones",
            {"title": milestone_title, "description": "Disposable Promotion Sync Q.A milestone"},
        )
        created_milestone_number = int(milestone["number"])

        with tempfile.TemporaryDirectory() as temporary_directory:
            project_definition = Path(temporary_directory) / "project.json"
            project_definition.write_text(
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
            create_project(client, args.repo, str(project_definition), dry_run=False, owner_type=owner_type)

        project = project_by_title(client, owner, owner_type, project_title)
        if not project:
            raise RuntimeError("Promotion Sync Q.A Project v2 creation verification failed")
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

        for index in range(2):
            issue = client.request_json(
                "POST",
                f"{API_BASE}/repos/{args.repo}/issues",
                {
                    "title": f"{QA_ISSUE_PREFIX}{suffix}-{index + 1}",
                    "body": "Disposable task for Promotion Sync native metadata validation.",
                    "labels": labels,
                    "milestone": created_milestone_number,
                },
            )
            created_issue_numbers.append(int(issue["number"]))

        repository = client.request_json("GET", f"{API_BASE}/repos/{args.repo}")
        default_branch = str(repository["default_branch"])
        root_sha = branch_sha(client, args.repo, default_branch)
        create_branch(client, args.repo, base_branch, root_sha)
        created_branches.append(base_branch)
        create_branch(client, args.repo, source_branch, root_sha)
        created_branches.append(source_branch)

        related_prs: list[int] = []
        for index, impl_branch in enumerate(impl_branches):
            pr_number = create_implementation(
                client,
                args.repo,
                source_branch,
                impl_branch,
                created_issue_numbers[index],
                milestone_title,
                f"promotion-impl-{suffix}-{index + 1}.txt",
                f"{suffix}-{index + 1}",
                created_project_number,
                owner,
            )
            related_prs.append(pr_number)
            created_pr_numbers.append(pr_number)
            created_branches.append(impl_branch)

        promotion_pr = client.request_json(
            "POST",
            f"{API_BASE}/repos/{args.repo}/pulls",
            {
                "title": f"{QA_PROMOTION_PR_PREFIX}{suffix}",
                "head": source_branch,
                "base": base_branch,
                "body": (
                    "## Related PRs\n"
                    + "\n".join(f"- #{number}" for number in related_prs)
                    + "\n\n## Linked Issue\n"
                    + "\n".join(f"- Closes #{number}" for number in created_issue_numbers)
                    + f"\n\n## Milestone\n- {milestone_title}\n\n"
                    + "## Summary\n- Disposable aggregate promotion metadata validation.\n"
                ),
            },
        )
        promotion_number = int(promotion_pr["number"])
        created_pr_numbers.append(promotion_number)

        with tempfile.TemporaryDirectory() as temporary_directory:
            config_path = Path(temporary_directory) / "project_setup.json"
            config_path.write_text(
                json.dumps(
                    {
                        "prAutomation": {
                            "relatedPrs": {
                                "enabled": True,
                                "bodySections": ["Related PRs"],
                                "includeBranchMatches": False,
                                "includeBodyReferences": True,
                                "inheritBodyReferences": True,
                                "fallbackDays": 0,
                            },
                            "sync": {
                                "enabled": True,
                                "syncLabels": True,
                                "labelPrefixes": ["type:", "priority:", "test:"],
                                "syncMilestone": True,
                                "syncAssignees": True,
                                "syncProject": True,
                                "promotionPaths": [{"head": source_branch, "base": base_branch}],
                                "projectStatusField": "Status",
                                "projectStatus": {
                                    "draft": "In progress",
                                    "review": "In review",
                                    "closed": "In progress",
                                    "merged": "Done",
                                },
                            },
                        }
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = apply_routed_pr_sync(
                client,
                args.repo,
                {"action": "opened", "pull_request": promotion_pr},
                config_path=str(config_path),
                project_client=client,
                project_number=created_project_number,
                owner=owner,
                dry_run=False,
            )
            if result != 0:
                raise RuntimeError(f"Promotion Sync returned {result}")

            pr_issue = client.get_issue(args.repo, promotion_number)
            actual_labels = {str(label.get("name") or "") for label in pr_issue.get("labels", [])}
            missing_labels = [label for label in labels if label not in actual_labels]
            if missing_labels:
                raise RuntimeError(f"Promotion PR labels were not synchronized: {', '.join(missing_labels)}")
            print("promotion_pr_labels=passed")

            pr_milestone = pr_issue.get("milestone") or {}
            if int(pr_milestone.get("number") or 0) != created_milestone_number:
                raise RuntimeError("Promotion PR milestone was not synchronized")
            print("promotion_pr_milestone=passed")

            author = str((promotion_pr.get("user") or {}).get("login") or "")
            assignees = {str(item.get("login") or "") for item in pr_issue.get("assignees", [])}
            if not author or author not in assignees:
                raise RuntimeError("Promotion PR assignee union was not synchronized")
            print("promotion_pr_assignees=passed")

            converged, visible_status = wait_for_project_pr_status(
                client,
                created_project_id,
                args.repo,
                promotion_number,
                "In review",
            )
            if not converged:
                raise RuntimeError(
                    "Promotion PR Project v2 membership/status did not converge; "
                    f"last visible status: {visible_status or '(PR not visible)'}"
                )
            print("promotion_pr_project_status_in_review=passed")

            merge = client.request_json(
                "PUT",
                f"{API_BASE}/repos/{args.repo}/pulls/{promotion_number}/merge",
                {"merge_method": "merge"},
            )
            if not merge.get("merged"):
                raise RuntimeError("Failed to merge disposable promotion PR")
            merged_pr = client.request_json("GET", f"{API_BASE}/repos/{args.repo}/pulls/{promotion_number}")
            result = apply_routed_pr_sync(
                client,
                args.repo,
                {"action": "closed", "pull_request": merged_pr},
                config_path=str(config_path),
                project_client=client,
                project_number=created_project_number,
                owner=owner,
                dry_run=False,
            )
            if result != 0:
                raise RuntimeError(f"Merged Promotion Sync returned {result}")

            converged, visible_status = wait_for_project_pr_status(
                client,
                created_project_id,
                args.repo,
                promotion_number,
                "Done",
            )
            if not converged:
                raise RuntimeError(
                    "Merged promotion PR Project v2 status did not converge to Done; "
                    f"last visible status: {visible_status or '(PR not visible)'}"
                )
            print("promotion_pr_project_status_done=passed")

            comments = client.list_issue_comments(args.repo, promotion_number)
            promotion_comment = next(
                (comment for comment in comments if "<!-- project-setup-related-prs -->" in (comment.get("body") or "")),
                None,
            )
            if not promotion_comment or "State: `merged`" not in (promotion_comment.get("body") or ""):
                raise RuntimeError("Promotion Sync sticky comment did not converge to merged state")
            print("promotion_sync_backlinks=passed")

        print("promotion_sync_structured_metadata=passed")

    except Exception as exc:
        primary_error = exc

    for pr_number in reversed(created_pr_numbers):
        try:
            pr = client.request_json("GET", f"{API_BASE}/repos/{args.repo}/pulls/{pr_number}")
            if str(pr.get("state") or "") == "open":
                client.request_json("PATCH", f"{API_BASE}/repos/{args.repo}/pulls/{pr_number}", {"state": "closed"})
        except Exception as exc:
            cleanup_errors.append(f"pull request #{pr_number}: {exc}")

    for issue_number in created_issue_numbers:
        try:
            client.update_issue(args.repo, issue_number, {"state": "closed"})
        except Exception as exc:
            cleanup_errors.append(f"issue #{issue_number}: {exc}")

    for branch in reversed(created_branches):
        try:
            delete_branch(client, args.repo, branch)
        except GitHubRequestError as exc:
            if exc.status not in {404, 422}:
                cleanup_errors.append(f"branch `{branch}`: {exc}")
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
            client.request_json("DELETE", f"{API_BASE}/repos/{args.repo}/labels/{urllib.parse.quote(label_name, safe='')}")
        except Exception as exc:
            cleanup_errors.append(f"label `{label_name}`: {exc}")

    if primary_error:
        if cleanup_errors:
            print("warning: cleanup also failed: " + "; ".join(cleanup_errors))
        raise primary_error
    if cleanup_errors:
        raise RuntimeError("Promotion Sync Q.A cleanup failed: " + "; ".join(cleanup_errors))

    print("promotion_sync_cleanup=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
