from __future__ import annotations

import argparse
import base64
import os
import re
import time
import urllib.parse

from project_setup.github import API_BASE, GitHubClient
from project_setup.linked_branch import create_linked_branch, manually_linked_pr_numbers


BRANCH_PREFIX = "qa/development/"
ISSUE_PREFIX = "QA Development linkage "
PR_PREFIX = "QA Development linked PR "
TIMEOUT_SECONDS = 20.0


def _ref_path(branch: str) -> str:
    return urllib.parse.quote(f"heads/{branch}", safe="/")


def _branch_sha(client: GitHubClient, repo: str, branch: str) -> str:
    ref = client.request_json("GET", f"{API_BASE}/repos/{repo}/git/ref/{_ref_path(branch)}")
    return str((ref.get("object") or {})["sha"])


def _create_plain_branch(client: GitHubClient, repo: str, branch: str, sha: str) -> None:
    client.request_json(
        "POST",
        f"{API_BASE}/repos/{repo}/git/refs",
        {"ref": f"refs/heads/{branch}", "sha": sha},
    )


def _delete_branch(client: GitHubClient, repo: str, branch: str) -> None:
    client.request_json("DELETE", f"{API_BASE}/repos/{repo}/git/refs/{_ref_path(branch)}")


def _wait_for_development_link(
    client: GitHubClient,
    repo: str,
    issue_number: int,
    pr_number: int,
) -> bool:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while True:
        if pr_number in manually_linked_pr_numbers(client, repo, issue_number):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(1.0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Live GitHub Development linkage validation")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    source_repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    if args.repo.casefold() == source_repo.casefold():
        raise SystemExit("Refusing Development linkage live test against the GPA source repository")
    token = os.getenv("PROJECT_SETUP_PAT", "").strip()
    if not token:
        raise SystemExit("PROJECT_SETUP_PAT is required for linked-branch live validation")

    client = GitHubClient(token)
    suffix = re.sub(r"[^A-Za-z0-9_.-]+", "-", args.run_id).strip("-")[:36] or "manual"
    issue_number: int | None = None
    pr_number: int | None = None
    created_branches: list[str] = []
    primary_error: Exception | None = None
    cleanup_errors: list[str] = []

    try:
        repository = client.request_json("GET", f"{API_BASE}/repos/{args.repo}")
        default_branch = str(repository["default_branch"])
        root_sha = _branch_sha(client, args.repo, default_branch)
        base_branch = f"{BRANCH_PREFIX}base-{suffix}"
        head_branch = f"{BRANCH_PREFIX}head-{suffix}"

        _create_plain_branch(client, args.repo, base_branch, root_sha)
        created_branches.append(base_branch)

        issue = client.request_json(
            "POST",
            f"{API_BASE}/repos/{args.repo}/issues",
            {"title": f"{ISSUE_PREFIX}{suffix}", "body": "Disposable native Development linkage validation."},
        )
        issue_number = int(issue["number"])

        create_linked_branch(
            client,
            args.repo,
            issue_number,
            head_branch,
            base_ref=base_branch,
        )
        created_branches.append(head_branch)

        marker_path = f"qa-development-{suffix}.txt"
        client.request_json(
            "PUT",
            f"{API_BASE}/repos/{args.repo}/contents/{urllib.parse.quote(marker_path, safe='')}",
            {
                "message": f"test: native Development link {suffix}",
                "content": base64.b64encode(f"development-link {suffix}\n".encode()).decode(),
                "branch": head_branch,
            },
        )

        pr = client.request_json(
            "POST",
            f"{API_BASE}/repos/{args.repo}/pulls",
            {
                "title": f"{PR_PREFIX}{suffix}",
                "head": head_branch,
                "base": base_branch,
                "body": "Native Development linkage must come from the Linked Branch, not a default-branch closing keyword.",
            },
        )
        pr_number = int(pr["number"])
        if base_branch == default_branch:
            raise RuntimeError("Development linkage smoke must target a non-default base branch")
        if not _wait_for_development_link(client, args.repo, issue_number, pr_number):
            raise RuntimeError(
                f"PR #{pr_number} did not appear as a manually linked Development PR for issue #{issue_number}"
            )
        print("development_linked_branch=passed")
        print("development_non_default_pr=passed")

    except Exception as exc:
        primary_error = exc

    if pr_number is not None:
        try:
            client.request_json("PATCH", f"{API_BASE}/repos/{args.repo}/pulls/{pr_number}", {"state": "closed"})
        except Exception as exc:
            cleanup_errors.append(f"pull request: {exc}")
    if issue_number is not None:
        try:
            client.update_issue(args.repo, issue_number, {"state": "closed"})
        except Exception as exc:
            cleanup_errors.append(f"issue: {exc}")
    for branch in reversed(created_branches):
        try:
            _delete_branch(client, args.repo, branch)
        except Exception as exc:
            cleanup_errors.append(f"branch `{branch}`: {exc}")

    if primary_error:
        if cleanup_errors:
            print("warning: cleanup also failed: " + "; ".join(cleanup_errors))
        raise primary_error
    if cleanup_errors:
        raise RuntimeError("Development linkage cleanup failed: " + "; ".join(cleanup_errors))
    print("development_link_cleanup=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
