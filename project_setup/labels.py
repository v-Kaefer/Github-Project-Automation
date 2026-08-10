from __future__ import annotations

import json
import urllib.parse

from .github import API_BASE, GitHubClient, GitHubRequestError, split_repo


def load_labels(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as file:
        labels = json.load(file)
    if not isinstance(labels, list):
        raise ValueError("labels manifest must be a JSON list")
    for label in labels:
        if not label.get("name") or not label.get("color"):
            raise ValueError("each label must define name and color")
    return labels


def sync_labels(client: GitHubClient, repo: str, labels_file: str, dry_run: bool = False) -> None:
    owner, name = split_repo(repo)
    labels = load_labels(labels_file)
    endpoint = f"{API_BASE}/repos/{owner}/{name}/labels"

    if dry_run:
        print(f"[DRY-RUN] Would sync {len(labels)} labels to {repo}")
        for label in labels:
            print(f"- {label['name']}")
        return

    for label in labels:
        try:
            client.request_json("POST", endpoint, label)
            print(f"created: {label['name']}")
        except GitHubRequestError as exc:
            if exc.status != 422:
                raise
            encoded_name = urllib.parse.quote(label["name"], safe="")
            client.request_json("PATCH", f"{endpoint}/{encoded_name}", label)
            print(f"updated: {label['name']}")
