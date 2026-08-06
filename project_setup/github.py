from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
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
IDEMPOTENT_METHODS = {"GET", "HEAD"}
HTTP_TIMEOUT_SECONDS = 30
ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class GitHubRequestError(RuntimeError):
    def __init__(self, method: str, url: str, status: int, details: str):
        super().__init__(f"GitHub API request failed ({method} {url}) status={status}: {details}")
        self.method = method
        self.url = url
        self.status = status
        self.details = details


@dataclass(frozen=True)
class GhAuthStatus:
    installed: bool
    authenticated: bool
    detail: str


def load_env_file(path: str | os.PathLike[str] | None = None) -> Path | None:
    """Load a simple dotenv file without overriding existing environment variables."""
    configured_path = path or os.getenv("PROJECT_SETUP_ENV_FILE", ".env")
    candidate = Path(configured_path).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    if not candidate.is_file():
        return None

    for line_number, raw_line in enumerate(candidate.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(
                f"Invalid environment entry in {candidate} at line {line_number}: expected NAME=value"
            )
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not ENV_KEY.fullmatch(key):
            raise ValueError(
                f"Invalid environment variable name '{key}' in {candidate} at line {line_number}"
            )
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)
    return candidate.resolve()


def _compact_detail(text: str, fallback: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[0] if lines else fallback


def get_gh_auth_status() -> GhAuthStatus:
    gh = shutil.which("gh")
    if not gh:
        return GhAuthStatus(False, False, "GitHub CLI is not installed or is not available on PATH")
    try:
        result = subprocess.run(
            [gh, "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return GhAuthStatus(True, False, "`gh auth status` timed out after 10 seconds")
    except OSError as exc:
        return GhAuthStatus(True, False, f"Could not execute `gh auth status`: {exc}")
    detail = _compact_detail(
        result.stdout if result.returncode == 0 else result.stderr,
        "GitHub CLI authentication is valid" if result.returncode == 0 else "GitHub CLI authentication is invalid",
    )
    return GhAuthStatus(True, result.returncode == 0, detail)


def get_token_source() -> tuple[str | None, str]:
    load_env_file()
    for variable in ("GITHUB_TOKEN", "GH_TOKEN", "PROJECT_SETUP_PAT"):
        token = os.environ.get(variable)
        if token and token.strip():
            return token.strip(), variable
    gh = shutil.which("gh")
    if not gh:
        return None, "missing"
    try:
        result = subprocess.run([gh, "auth", "token"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None, "gh-invalid"
    token = result.stdout.strip() if result.returncode == 0 else ""
    return (token, "gh") if token else (None, "gh-invalid")


def get_token() -> str | None:
    return get_token_source()[0]


def get_project_pat() -> str | None:
    load_env_file()
    token = os.environ.get("PROJECT_SETUP_PAT")
    return token.strip() if token and token.strip() else None


def split_repo(repo: str) -> tuple[str, str]:
    if "/" not in repo:
        raise ValueError("repository must use owner/name format")
    owner, name = repo.split("/", 1)
    if not owner or not name:
        raise ValueError("repository must use owner/name format")
    return owner, name


def _validate_github_api_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "api.github.com":
        raise ValueError(f"Unsupported GitHub API URL: {url}")


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
        normalized_method = method.upper()
        _validate_github_api_url(url)
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        retry_allowed = normalized_method in IDEMPOTENT_METHODS
        for attempt in range(1, 6):
            request = urllib.request.Request(
                url,
                data=data,
                headers=self._headers(accept),
                method=normalized_method,
            )
            try:
                with urllib.request.urlopen(  # noqa: S310 - URL is restricted to https://api.github.com above.
                    request,
                    timeout=HTTP_TIMEOUT_SECONDS,
                ) as response:
                    body = response.read().decode("utf-8")
                    return json.loads(body) if body else {}
            except urllib.error.HTTPError as exc:
                details = exc.read().decode("utf-8", errors="replace")
                if retry_allowed and exc.code in RETRYABLE_HTTP_STATUS and attempt < 5:
                    retry_after = exc.headers.get("Retry-After")
                    wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else attempt * 2
                    print(f"warning: GitHub returned HTTP {exc.code}; retrying read in {wait_seconds}s")
                    time.sleep(wait_seconds)
                    continue
                raise GitHubRequestError(normalized_method, url, exc.code, details) from exc
            except urllib.error.URLError as exc:
                if retry_allowed and attempt < 5:
                    wait_seconds = attempt * 2
                    print(f"warning: GitHub read failed; retrying in {wait_seconds}s: {exc.reason}")
                    time.sleep(wait_seconds)
                    continue
                raise GitHubRequestError(normalized_method, url, 0, str(exc.reason)) from exc
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
    token, source = get_token_source()
    if not token:
        gh = get_gh_auth_status()
        gh_guidance = (
            f"GitHub CLI status: {gh.detail}.\n" if gh.installed else "GitHub CLI is not installed.\n"
        )
        raise SystemExit(
            "No GitHub token is available.\n"
            f"{gh_guidance}"
            "Fix: copy .env.example to .env and set PROJECT_SETUP_PAT, set GITHUB_TOKEN/GH_TOKEN, "
            "or repair the CLI session with `gh auth login`."
        )
    if source == "gh-invalid":
        raise SystemExit("GitHub CLI authentication is invalid. Fix: run `gh auth login` and retry.")
    return GitHubClient(token)


def require_project_client() -> GitHubClient:
    token = get_project_pat()
    if not token:
        raise SystemExit(
            "GitHub Projects v2 requires PROJECT_SETUP_PAT.\n"
            "Fix:\n"
            "  1. GitHub profile picture > Settings > Developer settings.\n"
            "  2. Personal access tokens > Tokens (classic) > Generate new token (classic).\n"
            "  3. Select the `repo` and `project` scopes.\n"
            "  4. Copy .env.example to .env and set PROJECT_SETUP_PAT=<token>.\n"
            "  5. Run `make doctor` before retrying.\n"
            "The repository-scoped github.token cannot create or synchronize Projects v2."
        )
    return GitHubClient(token)
