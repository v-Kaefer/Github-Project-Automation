from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request


API_BASE = "https://api.github.com"
GRAPHQL_URL = f"{API_BASE}/graphql"
API_VERSION = "2022-11-28"
RETRYABLE_HTTP_STATUS = {429, 502, 503, 504}


class GitHubRequestError(RuntimeError):
    def __init__(self, method: str, url: str, status: int, details: str):
        super().__init__(f"GitHub API request failed ({method} {url}) status={status}: {details}")
        self.method = method
        self.url = url
        self.status = status
        self.details = details


def get_token() -> str | None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("PROJECT_SETUP_PAT")
    if token:
        return token.strip()
    gh = shutil.which("gh")
    if not gh:
        return None
    try:
        result = subprocess.run([gh, "auth", "token"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def split_repo(repo: str) -> tuple[str, str]:
    if "/" not in repo:
        raise ValueError("repository must use owner/name format")
    owner, name = repo.split("/", 1)
    if not owner or not name:
        raise ValueError("repository must use owner/name format")
    return owner, name


class GitHubClient:
    def __init__(self, token: str):
        self.token = token.strip()

    def _headers(self, accept: str = "application/vnd.github+json") -> dict[str, str]:
        headers = {
            "Accept": accept,
            "X-GitHub-Api-Version": API_VERSION,
            "Content-Type": "application/json",
            "User-Agent": "github-project-setup",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def request_json(self, method: str, url: str, payload: Any = None, accept: str = "application/vnd.github+json") -> Any:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        for attempt in range(1, 6):
            request = urllib.request.Request(url, data=data, headers=self._headers(accept), method=method)
            try:
                with urllib.request.urlopen(request) as response:
                    body = response.read().decode("utf-8")
                    return json.loads(body) if body else {}
            except urllib.error.HTTPError as exc:
                details = exc.read().decode("utf-8", errors="replace")
                if exc.code in RETRYABLE_HTTP_STATUS and attempt < 5:
                    retry_after = exc.headers.get("Retry-After")
                    wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else attempt * 2
                    print(f"warning: GitHub returned HTTP {exc.code}; retrying in {wait_seconds}s")
                    time.sleep(wait_seconds)
                    continue
                raise GitHubRequestError(method, url, exc.code, details) from exc
            except urllib.error.URLError as exc:
                if attempt < 5:
                    wait_seconds = attempt * 2
                    print(f"warning: GitHub request failed; retrying in {wait_seconds}s: {exc.reason}")
                    time.sleep(wait_seconds)
                    continue
                raise
        raise RuntimeError("GitHub request exhausted retries")

    def paginated(self, url: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            separator = "&" if "?" in url else "?"
            batch = self.request_json("GET", f"{url}{separator}per_page=100&page={page}")
            if not isinstance(batch, list):
                raise RuntimeError(f"Expected a list from paginated GitHub endpoint: {url}")
            items.extend(batch)
            if len(batch) < 100:
                return items
            page += 1

    def graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.request_json("POST", GRAPHQL_URL, {"query": query, "variables": variables or {}})
        if response.get("errors"):
            raise RuntimeError(f"GraphQL error: {json.dumps(response['errors'], ensure_ascii=False)}")
        return response["data"]

    def get_issue(self, repo: str, number: int) -> dict[str, Any]:
        return self.request_json("GET", f"{API_BASE}/repos/{repo}/issues/{number}")

    def create_issue(self, repo: str, title: str, body: str, labels: list[str]) -> dict[str, Any]:
        return self.request_json(
            "POST",
            f"{API_BASE}/repos/{repo}/issues",
            {"title": title, "body": body, "labels": labels},
        )

    def update_issue(self, repo: str, number: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request_json("PATCH", f"{API_BASE}/repos/{repo}/issues/{number}", payload)

    def list_issue_comments(self, repo: str, number: int) -> list[dict[str, Any]]:
        return self.paginated(f"{API_BASE}/repos/{repo}/issues/{number}/comments")

    def create_issue_comment(self, repo: str, number: int, body: str) -> dict[str, Any]:
        return self.request_json("POST", f"{API_BASE}/repos/{repo}/issues/{number}/comments", {"body": body})

    def update_issue_comment(self, repo: str, comment_id: int, body: str) -> dict[str, Any]:
        return self.request_json("PATCH", f"{API_BASE}/repos/{repo}/issues/comments/{comment_id}", {"body": body})

    def delete_issue_comment(self, repo: str, comment_id: int) -> dict[str, Any]:
        return self.request_json("DELETE", f"{API_BASE}/repos/{repo}/issues/comments/{comment_id}")


def require_client() -> GitHubClient:
    token = get_token()
    if not token:
        raise SystemExit("Missing GITHUB_TOKEN, GH_TOKEN, PROJECT_SETUP_PAT, or authenticated gh CLI")
    return GitHubClient(token)
