from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.parse

from project_setup.github import API_BASE, GitHubClient
from project_setup.issues import generate_issues
from project_setup.labels import sync_labels


REQUIRED_LABELS = {
    "type:task": {"name": "type:task", "color": "5319e7", "description": "Task"},
    "status:backlog": {"name": "status:backlog", "color": "c5def5", "description": "Backlog"},
}


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


def label_by_name(client: GitHubClient, repo: str, name: str) -> dict | None:
    labels = client.paginated(f"{API_BASE}/repos/{repo}/labels")
    return next((label for label in labels if label.get("name") == name), None)


def restore_label(client: GitHubClient, repo: str, name: str, original: dict | None) -> None:
    encoded = urllib.parse.quote(name, safe="")
    current = label_by_name(client, repo, name)
    if original is None:
        if current:
            client.request_json("DELETE", f"{API_BASE}/repos/{repo}/labels/{encoded}")
        return
    payload = {
        "name": original["name"],
        "color": original["color"],
        "description": original.get("description") or "",
    }
    if current:
        client.request_json("PATCH", f"{API_BASE}/repos/{repo}/labels/{encoded}", payload)
    else:
        client.request_json("POST", f"{API_BASE}/repos/{repo}/labels", payload)


def close_if_present(client: GitHubClient, repo: str, title: str) -> dict | None:
    issue = issue_by_title(client, repo, title)
    if not issue:
        return None
    if issue.get("state") != "closed":
        client.update_issue(
            repo,
            int(issue["number"]),
            {"state": "closed", "state_reason": "not_planned"},
        )
    return client.get_issue(repo, int(issue["number"]))


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
    original_labels = {name: label_by_name(client, args.repo, name) for name in REQUIRED_LABELS}
    primary_error: Exception | None = None
    story: dict | None = None
    task: dict | None = None

    try:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            labels_file = root / "labels.json"
            manifest_file = root / "backlog.json"
            labels_file.write_text(json.dumps(list(REQUIRED_LABELS.values())), encoding="utf-8")
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
    except Exception as exc:
        primary_error = exc

    cleanup_errors: list[str] = []
    try:
        task = close_if_present(client, args.repo, task_title) or task
        story = close_if_present(client, args.repo, story_title) or story
    except Exception as exc:
        cleanup_errors.append(f"issues: {exc}")

    for name, original in original_labels.items():
        try:
            restore_label(client, args.repo, name, original)
        except Exception as exc:
            cleanup_errors.append(f"label {name}: {exc}")

    if primary_error:
        if cleanup_errors:
            print("warning: cleanup also failed: " + "; ".join(cleanup_errors))
        raise primary_error
    if cleanup_errors:
        raise RuntimeError("Q.A cleanup failed: " + "; ".join(cleanup_errors))
    if not story or not task or story.get("state") != "closed" or task.get("state") != "closed":
        raise RuntimeError("Generated Q.A issues were not verified as closed")

    print(f"generated_story=#{story['number']}")
    print(f"generated_task=#{task['number']}")
    print("qa_issue_generation=passed")
    print("qa_label_restore=passed")
    print("note=closed Q.A issues remain visible in the dedicated sandbox history")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
