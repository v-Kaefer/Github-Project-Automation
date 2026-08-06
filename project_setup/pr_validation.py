from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from .github import GitHubClient


VALIDATION_MARKER = "<!-- project-setup-pr-validation -->"
BRANCH_PATTERN = re.compile(r"^(feat|fix|docs|refactor|test|hotfix|phase|task|chore|ci|release)/[a-z0-9._/-]+$")
REQUIRED_SECTIONS = (
    ("linked issue", "Linked Issue"),
    ("milestone", "Milestone"),
    ("summary", "Summary"),
    ("how to test", "How to test"),
    ("known risks", "Known risks"),
    ("dod checklist", "DoD checklist"),
)
PLACEHOLDER = re.compile(r"(<[^>]+>|\b(todo|tbd|placeholder|describe|fill in|replace)\b)", re.IGNORECASE)


@dataclass(frozen=True)
class ValidationFinding:
    section: str
    problem: str
    fix: str


def normalize_header(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(character for character in normalized if not unicodedata.combining(character))
    return " ".join(normalized.strip().lower().split())


def sections_from_body(body: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in (body or "").splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            current = normalize_header(match.group(1))
            sections.setdefault(current, [])
        elif current:
            sections[current].append(line)
    return sections


def meaningful(lines: list[str]) -> bool:
    for line in lines:
        stripped = line.strip().lstrip("-* ").strip()
        if stripped and not PLACEHOLDER.search(stripped):
            return True
    return False


def validate_branch(branch: str | None, base_branch: str | None = None) -> list[ValidationFinding]:
    normalized = (branch or "").strip()
    if normalized == "develop" and (base_branch or "").strip() == "main":
        return []
    if BRANCH_PATTERN.fullmatch(normalized.casefold()):
        return []
    return [
        ValidationFinding(
            "Branch name",
            f"Invalid branch name: `{normalized or '(missing)'}`.",
            "Use a supported prefix such as `feat/`, `fix/`, `docs/`, `task/`, `chore/`, `hotfix/`, or `release/`.",
        )
    ]


def validate_body(body: str | None) -> list[ValidationFinding]:
    if not (body or "").strip():
        return [ValidationFinding("PR body", "The pull request body is empty.", "Fill the repository pull request template.")]
    sections = sections_from_body(body or "")
    findings: list[ValidationFinding] = []
    for key, label in REQUIRED_SECTIONS:
        lines = sections.get(key)
        if lines is None:
            findings.append(ValidationFinding(label, "Required section is missing.", f"Add `## {label}`."))
        elif not meaningful(lines):
            findings.append(ValidationFinding(label, "Section is empty or contains only placeholders.", "Replace placeholders with concrete information."))
    linked = "\n".join(sections.get("linked issue", []))
    if linked and not re.search(r"\b(closes|fixes|resolves)\s+#\d+\b", linked, re.IGNORECASE):
        findings.append(ValidationFinding("Linked Issue", "No closing issue reference was found.", "Use `Closes #123`, `Fixes #123`, or `Resolves #123`."))
    return findings


def validate_pull_request(branch: str | None, body: str | None, base_branch: str | None = None) -> list[ValidationFinding]:
    return [*validate_branch(branch, base_branch), *validate_body(body)]


def render_comment(findings: list[ValidationFinding]) -> str:
    lines = [VALIDATION_MARKER, "## Project setup PR validation", ""]
    if not findings:
        lines.append("All configured pull request checks passed.")
        return "\n".join(lines)
    lines.append("The pull request still needs attention:")
    for finding in findings:
        lines.extend(["", f"### {finding.section}", f"- Problem: {finding.problem}", f"- Fix: {finding.fix}"])
    return "\n".join(lines)


def upsert_validation_comment(client: GitHubClient, repo: str, pr_number: int, findings: list[ValidationFinding]) -> str | None:
    existing = next(
        (comment for comment in client.list_issue_comments(repo, pr_number) if VALIDATION_MARKER in (comment.get("body") or "")),
        None,
    )
    if not findings:
        if existing:
            client.delete_issue_comment(repo, int(existing["id"]))
            return "deleted"
        return None
    body = render_comment(findings)
    if existing:
        client.update_issue_comment(repo, int(existing["id"]), body)
        return "updated"
    client.create_issue_comment(repo, pr_number, body)
    return "created"
