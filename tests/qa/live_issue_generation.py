from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import tempfile

from project_setup.github import API_BASE, GitHubClient
from project_setup.issues import generate_issues
from project_setup.labels import sync_labels


def require_sandbox(repo: str) -> None:
    current_repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    if not repo or "/" not in repo:
        raise SystemExit("QA_REPOSITORY must be configured as owner/repository in GitHub Environment `qa`.")
    if current_repo and repo.casefold() == current_repo.casefold():
        raise SystemExit("Refusing issue-generation Q.A test against the source repository.")
    if not os.getenv("PROJECT_SETUP_PAT", "").strip():
        raise SystemExit("QA_PROJECT_SETUP_PAT is required for the manual live issue-generation test.")


def issue_by_title(client: GitHubClient, repo: str, title: str) -> dict | None:
    issues = client.paginated(f"{API_BASE}/repos/{repo}/issues?state=all&sort=created&direction=desc")
    return next((issue for issue in issues if "pull_request" not in issue and issue.get("title") == title), None)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the non-idempotent issue-generation Q.A test in a sandbox")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    require_sandbox(args.repo)

    suffix = re.sub(r"[^A-Za-z0-9_.-]+", "-", args.run_id).strip("-")[:40] or "manual"
    story_title = f"QA issue generator {suffix}"
    task_title = f"QA generated task {suffix}"
    client = GitHubClient(os.environ["PROJECT_SETUP_PAT"].strip())

    with tempfile.TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        labels_file = root / "labels.json"
        manifest_file = root / "backlog.json"
        labels_file.write_text(
            json.dumps(
                [
                    {"name": "type:task", "color": "5319e7", "description": "Task"},
                    {"name": "status:backlog", "color": "c5def5", "description": "Backlog"},
                ]
            ),
            encoding="utf-8",
        )
        sync_labels(client, args.repo, str(labels_file), dry_run=False)
        manifest_file.write_text(
            json.dumps(
                {
                    "phases": [
                        {
                            "milestone": "QA",
                            "stories": [
                                {
                                    "storyId": f"QA-{suffix}",
                                    "title": story_title,
                                    "body": "## Context\n- Manual Q.A validation of issue generation.",
                                    "acceptanceCriteria": "- Story and task are created and then closed by the test.",
                                    "testStrategy": "- Manual workflow in dedicated sandbox.",
                                    "dod": "- Generated resources verified and closed.",
                                    "tasks": [{"title": task_title}],
                                }
                            ],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        generate_issues(client, args.repo, str(manifest_file), dry_run=False, link_subissues=False)

    story = issue_by_title(client, args.repo, story_title)
    task = issue_by_title(client, args.repo, task_title)
    if not story or not task:
        raise RuntimeError("Issue-generation verification failed: expected story/task were not found")
    if f"(#{story['number']})" not in (task.get("body") or ""):
        raise RuntimeError("Generated task does not reference the generated parent story")

    for issue in (task, story):
        client.update_issue(
            args.repo,
            int(issue["number"]),
            {"state": "closed", "state_reason": "not_planned"},
        )
        verified = client.get_issue(args.repo, int(issue["number"]))
        if verified.get("state") != "closed":
            raise RuntimeError(f"Could not close generated Q.A issue #{issue['number']}")

    print(f"generated_story=#{story['number']}")
    print(f"generated_task=#{task['number']}")
    print("qa_issue_generation=passed")
    print("note=closed Q.A issues remain visible in the dedicated sandbox history")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
