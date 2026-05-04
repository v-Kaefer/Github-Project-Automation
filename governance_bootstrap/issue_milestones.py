from __future__ import annotations

import re

from .github import API_BASE, GitHubClient, split_repo


def milestone_from_body(body: str) -> str | None:
    match = re.search(r"-\s*Milestone:\s*([A-Za-z0-9_.-]+)", body or "")
    return match.group(1) if match else None


def parent_issue_number_from_body(body: str) -> int | None:
    match = re.search(r"Parent story:.*\(#(\d+)\)", body or "")
    return int(match.group(1)) if match else None


def sync_issue_milestones(client: GitHubClient, repo: str, clear_not_planned: bool = False, dry_run: bool = False) -> None:
    owner, name = split_repo(repo)
    repo_base = f"{API_BASE}/repos/{owner}/{name}"

    milestones = client.paginated(f"{repo_base}/milestones?state=all")
    milestone_by_title = {milestone["title"]: milestone for milestone in milestones}
    issues = [
        issue
        for issue in client.paginated(f"{repo_base}/issues?state=all&sort=created&direction=asc")
        if "pull_request" not in issue
    ]

    explicit_milestone_by_issue = {}
    for issue in issues:
        milestone = milestone_from_body(issue.get("body") or "")
        if milestone:
            explicit_milestone_by_issue[issue["number"]] = milestone

    updated = 0
    cleared = 0
    already_correct = 0
    unmapped = []

    for issue in issues:
        issue_number = issue["number"]
        current = issue.get("milestone")
        current_title = current["title"] if current else None

        if clear_not_planned and issue.get("state") == "closed" and issue.get("state_reason") == "not_planned":
            if current_title:
                if dry_run:
                    print(f"[DRY-RUN] Would clear milestone from not-planned issue #{issue_number}: {current_title}")
                else:
                    client.request_json("PATCH", f"{repo_base}/issues/{issue_number}", {"milestone": None})
                    print(f"cleared #{issue_number}: {current_title}")
                cleared += 1
            else:
                already_correct += 1
            continue

        target = explicit_milestone_by_issue.get(issue_number)
        if not target:
            parent_number = parent_issue_number_from_body(issue.get("body") or "")
            if parent_number:
                target = explicit_milestone_by_issue.get(parent_number)

        if not target:
            unmapped.append((issue_number, issue["title"]))
            continue

        milestone = milestone_by_title.get(target)
        if not milestone:
            raise RuntimeError(f"Milestone '{target}' referenced by issue #{issue_number} does not exist")

        if current_title == target:
            already_correct += 1
            continue

        if dry_run:
            print(f"[DRY-RUN] Would set issue #{issue_number}: {current_title or 'none'} -> {target}")
        else:
            client.request_json("PATCH", f"{repo_base}/issues/{issue_number}", {"milestone": milestone["number"]})
            print(f"updated #{issue_number}: {current_title or 'none'} -> {target}")
        updated += 1

    print(f"issues_checked={len(issues)}")
    print(f"updated={updated}")
    print(f"cleared_not_planned={cleared}")
    print(f"already_correct={already_correct}")
    print(f"unmapped={len(unmapped)}")
    for issue_number, title in unmapped:
        print(f"unmapped #{issue_number}: {title}")
