from __future__ import annotations

import json

from .github import API_BASE, GitHubClient, split_repo


MILESTONE_LOOKUP_LIMIT = 100


def load_milestones(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as file:
        milestones = json.load(file)
    if not isinstance(milestones, list):
        raise ValueError("milestones manifest must be a JSON list")
    for milestone in milestones:
        if not isinstance(milestone, dict):
            raise ValueError("each milestone must be a JSON object")
        if not milestone.get("title"):
            raise ValueError("each milestone must define a title")
    return milestones


def sync_milestones(client: GitHubClient, repo: str, milestones_file: str, dry_run: bool = False) -> None:
    owner, name = split_repo(repo)
    milestones = load_milestones(milestones_file)
    endpoint = f"{API_BASE}/repos/{owner}/{name}/milestones"

    if dry_run:
        print(f"[DRY-RUN] Would sync {len(milestones)} milestones to {repo}")
        for milestone in milestones:
            print(f"- {milestone['title']} ({milestone.get('due_on', 'no due date')})")
        return

    existing = client.request_json("GET", f"{endpoint}?state=all&per_page={MILESTONE_LOOKUP_LIMIT}")
    existing_by_title = {item["title"]: item for item in existing}
    for milestone in milestones:
        payload = {
            "title": milestone["title"],
            "description": milestone.get("description", ""),
        }
        if milestone.get("due_on"):
            payload["due_on"] = milestone["due_on"]
        current = existing_by_title.get(milestone["title"])
        if current:
            client.request_json("PATCH", f"{endpoint}/{current['number']}", payload)
            print(f"updated: {milestone['title']}")
        else:
            client.request_json("POST", endpoint, payload)
            print(f"created: {milestone['title']}")
