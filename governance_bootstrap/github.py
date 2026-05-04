from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request


API_BASE = "https://api.github.com"
GRAPHQL_URL = f"{API_BASE}/graphql"
API_VERSION = "2022-11-28"
RETRYABLE_HTTP_STATUS = {502, 503, 504}


class GitHubRequestError(RuntimeError):
    def __init__(self, method: str, url: str, status: int, details: str):
        super().__init__(f"GitHub API request failed ({method} {url}) status={status}: {details}")
        self.method = method
        self.url = url
        self.status = status
        self.details = details


def get_token() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def split_repo(repo: str) -> tuple[str, str]:
    if "/" not in repo:
        raise ValueError("repository must use owner/name format")
    return repo.split("/", 1)


class GitHubClient:
    def __init__(self, token: str):
        self.token = token

    def request_json(self, method: str, url: str, payload=None, accept: str = "application/vnd.github+json"):
        headers = {
            "Accept": accept,
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": API_VERSION,
            "Content-Type": "application/json",
        }
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        for attempt in range(1, 6):
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req) as res:
                    body = res.read().decode("utf-8")
                    return json.loads(body) if body else {}
            except urllib.error.HTTPError as exc:
                details = exc.read().decode("utf-8", errors="replace")
                if exc.code in RETRYABLE_HTTP_STATUS and attempt < 5:
                    wait_seconds = attempt * 2
                    print(f"warning: HTTP {exc.code} from GitHub; retrying in {wait_seconds}s")
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

    def paginated(self, url: str):
        items = []
        page = 1
        while True:
            sep = "&" if "?" in url else "?"
            batch = self.request_json("GET", f"{url}{sep}per_page=100&page={page}")
            items.extend(batch)
            if len(batch) < 100:
                return items
            page += 1

    def graphql(self, query: str, variables: dict | None = None):
        data = self.request_json("POST", GRAPHQL_URL, {"query": query, "variables": variables or {}})
        if data.get("errors"):
            raise RuntimeError(f"GraphQL error: {json.dumps(data['errors'], ensure_ascii=False)}")
        return data["data"]


def require_client() -> GitHubClient:
    token = get_token()
    if not token:
        raise SystemExit("Missing GITHUB_TOKEN or GH_TOKEN")
    return GitHubClient(token)
