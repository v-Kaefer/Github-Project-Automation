from __future__ import annotations

import json
import re

from .github import API_BASE, GitHubRequestError, GitHubClient


LABEL_PREFIXES = ("type:", "priority:", "test:")


def load_event(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_allowed_labels(path: str) -> set[str]:
    with open(path, "r", encoding="utf-8") as f:
        return {item["name"] for item in json.load(f)}


def label_names(item: dict) -> set[str]:
    return {label["name"] for label in item.get("labels", [])}


def find_test_label(text: str) -> str | None:
    patterns = [
        r"Test strategy\s*\n+\s*(automated|smoke|manual)\b",
        r"Expected test type\s*\n+\s*(automated|smoke|manual)\b",
        r"Test type:\s*(automated|smoke|manual)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return f"test:{match.group(1).lower()}"
    return None


def find_priority_label(text: str) -> str | None:
    match = re.search(r"Severity\s*\n+\s*(critical|high|medium|low)\b", text, re.IGNORECASE)
    return f"priority:{match.group(1).lower()}" if match else None


def title_type_label(title: str) -> str | None:
    if re.match(r"^US-\d+", title, re.IGNORECASE):
        return "type:user-story"
    if re.match(r"^T-\d+", title, re.IGNORECASE):
        return "type:task"
    if re.match(r"^BUG\b", title, re.IGNORECASE):
        return "type:bug"
    return None


def linked_issue_number(text: str) -> int | None:
    match = re.search(r"\b(?:closes|fixes|resolves)\s+#(\d+)\b", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def labels_from_linked_issue(client: GitHubClient, repo: str, number: int) -> set[str]:
    issue = client.request_json("GET", f"{API_BASE}/repos/{repo}/issues/{number}")
    return {name for name in label_names(issue) if name.startswith(LABEL_PREFIXES)}


def branch_type_label(branch: str) -> str | None:
    prefix = branch.split("/", 1)[0].lower()
    if prefix in {"fix", "hotfix"}:
        return "type:bug"
    if prefix in {"docs", "refactor", "test"}:
        return "type:repo"
    return None


def infer_issue_labels(issue: dict) -> set[str]:
    current = label_names(issue)
    body = issue.get("body") or ""
    labels = set()

    type_label = next((label for label in current if label.startswith("type:")), None)
    labels.add(type_label or title_type_label(issue.get("title", "")) or "")

    priority_label = find_priority_label(body)
    if priority_label:
        labels.add(priority_label)

    test_label = find_test_label(body)
    if test_label:
        labels.add(test_label)

    if not any(label.startswith("status:") for label in current):
        labels.add("status:backlog")

    return {label for label in labels if label}


def infer_pr_labels(repo: str, pr: dict, client: GitHubClient | None) -> set[str]:
    body = pr.get("body") or ""
    labels = set()

    number = linked_issue_number(body)
    if number and client:
        try:
            labels.update(labels_from_linked_issue(client, repo, number))
        except GitHubRequestError as exc:
            print(f"warning: could not read linked issue #{number}: {exc}")

    test_label = find_test_label(body)
    if test_label:
        labels.add(test_label)

    if not any(label.startswith("type:") for label in labels):
        type_label = branch_type_label(pr.get("head", {}).get("ref", ""))
        if type_label:
            labels.add(type_label)

    return labels


def event_target(event: dict) -> tuple[str, dict, int]:
    if "issue" in event and "pull_request" not in event["issue"]:
        return "issue", event["issue"], event["issue"]["number"]
    if "pull_request" in event:
        return "pull_request", event["pull_request"], event["pull_request"]["number"]
    raise RuntimeError("Unsupported event payload: expected issue or pull_request")


def apply_auto_labels(repo: str, event_path: str, labels_file: str, client: GitHubClient | None, dry_run: bool = False) -> int:
    event = load_event(event_path)
    allowed = load_allowed_labels(labels_file)
    target_type, item, number = event_target(event)
    current = label_names(item)

    inferred = infer_issue_labels(item) if target_type == "issue" else infer_pr_labels(repo, item, client)
    labels = sorted(label for label in inferred if label in allowed and label not in current)
    if not labels:
        print(f"No labels to add for {target_type} #{number}")
        return 0

    print(f"Labels to add to {target_type} #{number}: {', '.join(labels)}")
    if dry_run:
        return 0
    if not client:
        print("Missing GITHUB_TOKEN or GH_TOKEN")
        return 1

    try:
        client.request_json("POST", f"{API_BASE}/repos/{repo}/issues/{number}/labels", {"labels": labels})
    except GitHubRequestError as exc:
        if exc.status == 403:
            print(f"warning: token cannot add labels to {target_type} #{number}; skipping")
            return 0
        raise
    return 0
