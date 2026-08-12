from __future__ import annotations

import argparse
import os
import urllib.parse
from typing import Any

from .github import API_BASE, GitHubClient, require_client, split_repo


def _branch_oid(client: GitHubClient, repo: str, base_ref: str) -> str:
    encoded = urllib.parse.quote(base_ref, safe="")
    branch = client.request_json("GET", f"{API_BASE}/repos/{repo}/branches/{encoded}")
    oid = str((branch.get("commit") or {}).get("sha") or "")
    if not oid:
        raise RuntimeError(f"Could not resolve base branch `{base_ref}` in {repo}")
    return oid


def create_linked_branch(
    client: GitHubClient,
    repo: str,
    issue_number: int,
    branch_name: str,
    *,
    base_ref: str = "develop",
    dry_run: bool = False,
) -> dict[str, Any]:
    branch_name = branch_name.strip()
    base_ref = base_ref.strip()
    if not branch_name:
        raise ValueError("Linked branch name cannot be empty")
    if not base_ref:
        raise ValueError("Linked branch base cannot be empty")
    if dry_run:
        print(
            f"[DRY-RUN] Would create linked branch `{branch_name}` for issue #{issue_number} "
            f"from `{base_ref}` in {repo}"
        )
        return {"issue": {"number": issue_number}, "linkedBranch": {"ref": {"name": branch_name}}}

    issue = client.get_issue(repo, issue_number)
    if "pull_request" in issue:
        raise ValueError(f"#{issue_number} is a pull request, not an issue")
    issue_id = str(issue.get("node_id") or "")
    if not issue_id:
        raise RuntimeError(f"Issue #{issue_number} has no GraphQL node id")

    repository = client.request_json("GET", f"{API_BASE}/repos/{repo}")
    repository_id = str(repository.get("node_id") or "")
    if not repository_id:
        raise RuntimeError(f"Repository {repo} has no GraphQL node id")
    oid = _branch_oid(client, repo, base_ref)

    mutation = """
    mutation($issue:ID!, $repository:ID!, $name:String!, $oid:GitObjectID!) {
      createLinkedBranch(
        input:{issueId:$issue,repositoryId:$repository,name:$name,oid:$oid}
      ) {
        issue { id number }
        linkedBranch { id ref { name } }
      }
    }
    """
    payload = client.graphql(
        mutation,
        {
            "issue": issue_id,
            "repository": repository_id,
            "name": branch_name,
            "oid": oid,
        },
    )["createLinkedBranch"]
    linked_name = str((((payload.get("linkedBranch") or {}).get("ref") or {}).get("name")) or branch_name)
    print(f"Created linked branch `{linked_name}` for issue #{issue_number} from `{base_ref}`.")
    return payload


def manually_linked_pr_numbers(client: GitHubClient, repo: str, issue_number: int) -> list[int]:
    owner, name = split_repo(repo)
    query = """
    query($owner:String!, $repo:String!, $number:Int!) {
      repository(owner:$owner,name:$repo) {
        issue(number:$number) {
          closedByPullRequestsReferences(first:50,userLinkedOnly:true,includeClosedPrs:true) {
            nodes { number }
          }
        }
      }
    }
    """
    issue = client.graphql(
        query,
        {"owner": owner, "repo": name, "number": issue_number},
    )["repository"]["issue"]
    if not issue:
        raise RuntimeError(f"Issue #{issue_number} not found in {repo}")
    connection = issue.get("closedByPullRequestsReferences") or {}
    return [int(pr["number"]) for pr in connection.get("nodes", []) if pr and pr.get("number") is not None]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a GitHub Linked Branch so a later PR can appear in the issue Development sidebar"
    )
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--base", default="develop")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", dest="dry_run", action="store_true")
    mode.add_argument("--live", dest="dry_run", action="store_false")
    parser.set_defaults(dry_run=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.repo:
        raise SystemExit("Missing --repo or GITHUB_REPOSITORY")
    client = GitHubClient("") if args.dry_run else require_client()
    create_linked_branch(
        client,
        args.repo,
        args.issue,
        args.branch,
        base_ref=args.base,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
