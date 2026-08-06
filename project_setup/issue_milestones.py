from __future__ import annotations

import re

from .github import API_BASE, GitHubClient, split_repo


def milestone_from_body(body: str) -> str | None:
    match = re.search(r"-\s*Milestone:\s*([A-Za-z0-9_.-]+)", body or "")
    return match.group(1) if match else None


def parent_issue_number_from_body(body: str) -> int | None:
    match = re.search(r"Parent story:.*\(#(\d+)\)", body or "")
    return int(match.group(1)) if match else None


def sync_issue_milestones(
    client: GitHubClient,
    repo: str,
    clear_not_planned: bool = False,
    dry_run: bool = False,
) -> None:
    owner, name = split_repo(repo)
    base = f"{API_BASE}/repos/{owner}/{name}"
    milestones = client.paginated(f"{base}/milestones?state=all")
    milestones_by_title = {item["title"]: item for item in milestones}
    issues = [
        item
        for item in client.paginated(f"{base}/issues?state=all&sort=created&direction=asc")
        if "pull_request" not in item
    ]
    explicit = {
        issue["number"]: title
        for issue in issues
        if (title := milestone_from_body(issue.get("body") or ""))
    }
    updated = cleared = unchanged = 0
    unmapped: list[tuple[int, str]] = []

    for issue in issues:
        number = int(issue["number"])
        current = issue.get("milestone")
        current_title = current["title"] if current else None
        if clear_not_planned and issue.get("state") == "closed" and issue.get("state_reason") == "not_planned":
            if current_title:
                if dry_run:
                    print(f"[DRY-RUN] Would clear milestone from issue #{number}")
                else:
                    client.update_issue(repo, number, {"milestone": None})
                cleared += 1
            else:
                unchanged += 1
            continue

        target = explicit.get(number)
        if not target and (parent := parent_issue_number_from_body(issue.get("body") or "")):
            target = explicit.get(parent)
        if not target:
            unmapped.append((number, issue["title"]))
            continue
        milestone = milestones_by_title.get(target)
        if not milestone:
            raise RuntimeError(f"Milestone '{target}' referenced by issue #{number} does not exist")
        if current_title == target:
            unchanged += 1
            continue
        if dry_run:
            print(f"[DRY-RUN] Would set issue #{number}: {current_title or 'none'} -> {target}")
        else:
            client.update_issue(repo, number, {"milestone": milestone["number"]})
        updated += 1

    print(f"issues_checked={len(issues)}")
    print(f"updated={updated}")
    print(f"cleared_not_planned={cleared}")
    print(f"already_correct={unchanged}")
    print(f"unmapped={len(unmapped)}")
    for number, title in unmapped:
        print(f"unmapped #{number}: {title}")
