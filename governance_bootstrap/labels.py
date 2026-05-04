from __future__ import annotations

import json
import urllib.parse

from .github import API_BASE, GitHubRequestError, GitHubClient, split_repo


def load_labels(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        labels = json.load(f)
    if not isinstance(labels, list):
        raise ValueError("labels manifest must be a JSON list")
    for label in labels:
        for key in ("name", "color"):
            if key not in label:
                raise ValueError(f"label is missing required key: {key}")
    return labels


def sync_labels(client: GitHubClient, repo: str, labels_file: str, dry_run: bool = False) -> None:
    owner, name = split_repo(repo)
    labels = load_labels(labels_file)
    base = f"{API_BASE}/repos/{owner}/{name}/labels"

    if dry_run:
        print(f"[DRY-RUN] Would sync {len(labels)} labels to {repo}")
        for label in labels:
            print(f"- {label['name']}")
        return

    for label in labels:
        try:
            client.request_json("POST", base, label)
            print(f"created: {label['name']}")
        except GitHubRequestError as exc:
            if exc.status != 422:
                raise
            patch_url = f"{base}/{urllib.parse.quote(label['name'])}"
            client.request_json("PATCH", patch_url, label)
            print(f"updated: {label['name']}")
