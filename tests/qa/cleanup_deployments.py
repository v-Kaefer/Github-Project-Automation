from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import urllib.parse


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from project_setup.github import API_BASE, GitHubClient


def cleanup_deployments(client: GitHubClient, repo: str, environment: str) -> tuple[int, list[str]]:
    """Mark and delete historical deployments for one explicitly named Q.A environment."""
    encoded_environment = urllib.parse.quote(environment, safe="")
    deployments = client.paginated(
        f"{API_BASE}/repos/{repo}/deployments?environment={encoded_environment}"
    )
    deleted = 0
    errors: list[str] = []

    for deployment in deployments:
        deployment_id = deployment.get("id")
        if deployment_id is None:
            continue
        try:
            client.request_json(
                "POST",
                f"{API_BASE}/repos/{repo}/deployments/{int(deployment_id)}/statuses",
                {
                    "state": "inactive",
                    "environment": environment,
                    "description": "Superseded GPA Q.A validation deployment",
                },
            )
            client.request_json(
                "DELETE",
                f"{API_BASE}/repos/{repo}/deployments/{int(deployment_id)}",
            )
            deleted += 1
        except Exception as exc:
            errors.append(f"deployment {deployment_id}: {exc}")

    return deleted, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean historical GitHub deployments created by GPA Q.A validation")
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"), required=False)
    parser.add_argument("--environment", default="qa")
    args = parser.parse_args()

    if not args.repo:
        raise SystemExit("Missing --repo or GITHUB_REPOSITORY")
    if args.environment != "qa":
        raise SystemExit("Refusing to clean a non-Q.A GitHub Environment; --environment must be exactly 'qa'.")

    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        raise SystemExit("GITHUB_TOKEN is required to clean Q.A deployment history.")

    deleted, errors = cleanup_deployments(GitHubClient(token), args.repo, args.environment)
    print(f"qa_deployments_deleted={deleted}")
    if errors:
        raise RuntimeError("Q.A deployment cleanup failed: " + "; ".join(errors))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
