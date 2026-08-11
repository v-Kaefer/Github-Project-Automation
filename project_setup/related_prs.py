from __future__ import annotations

import argparse
from dataclasses import dataclass
import datetime
import json
import os
from pathlib import Path
import re
from typing import Any
import urllib.parse

from .github import API_BASE, GitHubClient, require_client
from .pr_sync import PullRequestContext, context_from_event, load_sync_config


RELATED_PRS_MARKER = "<!-- project-setup-related-prs -->"
PROMOTION_LINK_MARKER_PREFIX = "<!-- project-setup-promotion-link-"
SECTION_HEADING_PATTERN = re.compile(r"^##\s+(.+?)\s*$")
PR_REFERENCE_PATTERN = re.compile(r"(?:#|/pull/)(\d+)\b", re.IGNORECASE)
CLOSING_ISSUE_PATTERN = re.compile(
    r"\b(?:closes|fixes|resolves)\s*:?\s*#(\d+)\b",
    re.IGNORECASE,
)
PLACEHOLDER_PATTERN = re.compile(
    r"(?:<[^<>]+>|\b(?:todo|tbd|placeholder|replace|fill in|optional|example)\b)",
    re.IGNORECASE,
)

DEFAULT_BRANCH_PATTERNS = [
    r"^feat/",
    r"^fix/",
    r"^docs/",
    r"^refactor/",
    r"^test/",
    r"^hotfix/",
    r"^phase/",
    r"^task/",
    r"^chore/",
    r"^ci/",
    r"^release/",
]

DEFAULT_RELATED_PRS_CONFIG: dict[str, Any] = {
    "enabled": True,
    "branchPatterns": DEFAULT_BRANCH_PATTERNS,
    "bodySections": ["Related PRs", "Related Pull Requests"],
    "includeBranchMatches": True,
    "includeBodyReferences": True,
    "inheritBodyReferences": True,
    "fallbackDays": 7,
}


@dataclass(frozen=True)
class RelatedPrDetection:
    related_numbers: list[int]
    explicit_numbers: list[int]
    branch_match_numbers: list[int]
    inherited_numbers: list[int]
    source_promotion_numbers: list[int]
    cutoff: str | None
    cutoff_source: str


def load_project_config(path: str | os.PathLike[str] = "project_setup.json") -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_related_prs_config(path: str | os.PathLike[str] = "project_setup.json") -> dict[str, Any]:
    data = load_project_config(path)
    configured = data.get("prAutomation", {}).get("relatedPrs", {})
    if configured is None:
        configured = {}
    if not isinstance(configured, dict):
        raise ValueError("project_setup.json prAutomation.relatedPrs must be an object")

    result = dict(DEFAULT_RELATED_PRS_CONFIG)
    result.update(configured)

    patterns = result.get("branchPatterns", [])
    if not isinstance(patterns, list) or not all(isinstance(item, str) and item for item in patterns):
        raise ValueError("prAutomation.relatedPrs.branchPatterns must be a list of non-empty regex strings")
    for pattern in patterns:
        re.compile(pattern)

    sections = result.get("bodySections", [])
    if not isinstance(sections, list) or not all(isinstance(item, str) and item.strip() for item in sections):
        raise ValueError("prAutomation.relatedPrs.bodySections must be a list of non-empty section names")

    fallback_days = result.get("fallbackDays", 7)
    if not isinstance(fallback_days, int) or fallback_days < 0:
        raise ValueError("prAutomation.relatedPrs.fallbackDays must be a non-negative integer")
    return result


def normalize_header(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def sections_from_body(body: str | None) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in (body or "").splitlines():
        heading = SECTION_HEADING_PATTERN.match(line)
        if heading:
            current = normalize_header(heading.group(1))
            sections.setdefault(current, [])
        elif current:
            sections[current].append(line)
    return sections


def pr_numbers_from_body_sections(body: str | None, section_names: list[str]) -> list[int]:
    sections = sections_from_body(body)
    wanted = {normalize_header(name) for name in section_names}
    numbers: list[int] = []
    seen: set[int] = set()
    for name, lines in sections.items():
        if name not in wanted:
            continue
        for line in lines:
            if PLACEHOLDER_PATTERN.search(line):
                continue
            for match in PR_REFERENCE_PATTERN.finditer(line):
                number = int(match.group(1))
                if number not in seen:
                    seen.add(number)
                    numbers.append(number)
    return numbers


def closing_issue_numbers(body: str | None) -> list[int]:
    numbers: list[int] = []
    seen: set[int] = set()
    for match in CLOSING_ISSUE_PATTERN.finditer(body or ""):
        number = int(match.group(1))
        if number not in seen:
            seen.add(number)
            numbers.append(number)
    return numbers


def branch_matches(branch: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, branch or "", re.IGNORECASE) for pattern in patterns)


def promotion_paths(config_path: str | os.PathLike[str] = "project_setup.json") -> list[dict[str, Any]]:
    return list(load_sync_config(config_path).get("promotionPaths", []))


def promotion_path_for(
    head_ref: str,
    base_ref: str,
    config_path: str | os.PathLike[str] = "project_setup.json",
) -> dict[str, Any] | None:
    for path in promotion_paths(config_path):
        if str(path.get("head")) == head_ref and str(path.get("base")) == base_ref:
            return path
    return None


def is_promotion_context(
    ctx: PullRequestContext,
    config_path: str | os.PathLike[str] = "project_setup.json",
) -> bool:
    return promotion_path_for(ctx.head_ref, ctx.base_ref, config_path) is not None


def _list_pulls(client: GitHubClient, repo: str, *, state: str, base: str) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {"state": state, "base": base, "sort": "updated", "direction": "desc"}
    )
    return client.paginated(f"{API_BASE}/repos/{repo}/pulls?{query}")


def _head_ref(pr: dict[str, Any]) -> str:
    return str((pr.get("head") or {}).get("ref") or "")


def _base_ref(pr: dict[str, Any]) -> str:
    return str((pr.get("base") or {}).get("ref") or "")


def _previous_same_promotion(
    client: GitHubClient,
    repo: str,
    ctx: PullRequestContext,
) -> dict[str, Any] | None:
    merged = [
        pr
        for pr in _list_pulls(client, repo, state="closed", base=ctx.base_ref)
        if int(pr.get("number") or 0) != ctx.number
        and pr.get("merged_at")
        and _head_ref(pr) == ctx.head_ref
    ]
    merged.sort(key=lambda item: str(item.get("merged_at") or ""), reverse=True)
    return merged[0] if merged else None


def _detection_cutoff(
    previous: dict[str, Any] | None,
    fallback_days: int,
) -> tuple[str | None, str]:
    if previous and previous.get("merged_at"):
        return str(previous["merged_at"]), "previous promotion"
    if fallback_days <= 0:
        return None, "repository history"
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=fallback_days)
    return cutoff.strftime("%Y-%m-%dT%H:%M:%SZ"), f"fallback {fallback_days} days"


def _candidate_source_pulls(
    client: GitHubClient,
    repo: str,
    ctx: PullRequestContext,
    cutoff: str | None,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for pr in _list_pulls(client, repo, state="closed", base=ctx.head_ref):
        merged_at = pr.get("merged_at")
        if not merged_at:
            continue
        if cutoff and str(merged_at) <= cutoff:
            continue
        result.append(pr)
    result.sort(key=lambda item: str(item.get("merged_at") or ""))
    return result


def _is_configured_promotion_pr(pr: dict[str, Any], config_path: str | os.PathLike[str]) -> bool:
    return promotion_path_for(_head_ref(pr), _base_ref(pr), config_path) is not None


def detect_related_prs(
    client: GitHubClient,
    repo: str,
    ctx: PullRequestContext,
    *,
    config_path: str | os.PathLike[str] = "project_setup.json",
) -> RelatedPrDetection:
    config = load_related_prs_config(config_path)
    empty = RelatedPrDetection([], [], [], [], [], None, "not applicable")
    if not config.get("enabled", True) or not is_promotion_context(ctx, config_path):
        return empty

    section_names = [str(item) for item in config.get("bodySections", [])]
    explicit = (
        pr_numbers_from_body_sections(ctx.body, section_names)
        if config.get("includeBodyReferences", True)
        else []
    )

    previous = _previous_same_promotion(client, repo, ctx)
    cutoff, cutoff_source = _detection_cutoff(previous, int(config.get("fallbackDays", 7)))
    candidates = _candidate_source_pulls(client, repo, ctx, cutoff)
    patterns = [str(item) for item in config.get("branchPatterns", [])]

    branch_matches_found: list[int] = []
    inherited: list[int] = []
    source_promotions: list[int] = []
    for candidate in candidates:
        number = int(candidate["number"])
        if _is_configured_promotion_pr(candidate, config_path):
            source_promotions.append(number)
        if config.get("includeBranchMatches", True) and branch_matches(_head_ref(candidate), patterns):
            branch_matches_found.append(number)
        if config.get("inheritBodyReferences", True):
            inherited.extend(pr_numbers_from_body_sections(candidate.get("body") or "", section_names))

    ordered: list[int] = []
    seen: set[int] = {ctx.number}
    for source in (explicit, branch_matches_found, inherited):
        for number in source:
            if number not in seen:
                seen.add(number)
                ordered.append(number)

    return RelatedPrDetection(
        related_numbers=ordered,
        explicit_numbers=list(dict.fromkeys(explicit)),
        branch_match_numbers=list(dict.fromkeys(branch_matches_found)),
        inherited_numbers=list(dict.fromkeys(inherited)),
        source_promotion_numbers=list(dict.fromkeys(source_promotions)),
        cutoff=cutoff,
        cutoff_source=cutoff_source,
    )


def _fetch_pull(client: GitHubClient, repo: str, number: int) -> dict[str, Any]:
    return client.request_json("GET", f"{API_BASE}/repos/{repo}/pulls/{number}")


def _split_body(body: str) -> tuple[list[str], list[tuple[str, list[str]]]]:
    preamble: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    current_name: str | None = None
    current_lines: list[str] = []
    for line in (body or "").splitlines():
        heading = SECTION_HEADING_PATTERN.match(line)
        if heading:
            if current_name is not None:
                sections.append((current_name, current_lines))
            current_name = heading.group(1)
            current_lines = []
        elif current_name is None:
            preamble.append(line)
        else:
            current_lines.append(line)
    if current_name is not None:
        sections.append((current_name, current_lines))
    return preamble, sections


def _render_body(preamble: list[str], sections: list[tuple[str, list[str]]]) -> str:
    parts: list[str] = []
    preamble_text = "\n".join(preamble).rstrip()
    if preamble_text:
        parts.append(preamble_text)
    for name, lines in sections:
        content = "\n".join(lines).rstrip()
        parts.append(f"## {name}" + (f"\n{content}" if content else ""))
    return ("\n\n".join(parts).rstrip() + "\n") if parts else ""


def _section_is_placeholder(lines: list[str]) -> bool:
    meaningful = [line.strip().lstrip("-* ").strip() for line in lines if line.strip()]
    return not meaningful or all(PLACEHOLDER_PATTERN.search(line) for line in meaningful)


def rewrite_promotion_body(body: str, related_pulls: list[dict[str, Any]]) -> tuple[str, bool]:
    issue_numbers: list[int] = []
    milestone_titles: list[str] = []
    seen_issues: set[int] = set()
    seen_milestones: set[str] = set()
    for pr in related_pulls:
        for number in closing_issue_numbers(pr.get("body") or ""):
            if number not in seen_issues:
                seen_issues.add(number)
                issue_numbers.append(number)
        milestone = pr.get("milestone") or {}
        title = str(milestone.get("title") or "").strip()
        if title and title not in seen_milestones:
            seen_milestones.add(title)
            milestone_titles.append(title)

    replacements: dict[str, list[str]] = {
        normalize_header("Related PRs"): [
            f"- #{int(pr['number'])} — {str(pr.get('title') or '').strip()}" for pr in related_pulls
        ]
    }
    if issue_numbers:
        replacements[normalize_header("Linked Issue")] = [f"- Closes #{number}" for number in issue_numbers]
    if milestone_titles:
        replacements[normalize_header("Milestone")] = [f"- {title}" for title in milestone_titles]

    preamble, sections = _split_body(body)
    rewritten: list[tuple[str, list[str]]] = []
    seen_sections: set[str] = set()
    has_summary = False
    for name, lines in sections:
        key = normalize_header(name)
        if key in replacements:
            rewritten.append((name, replacements[key]))
            seen_sections.add(key)
        elif key == normalize_header("Summary"):
            has_summary = True
            if _section_is_placeholder(lines):
                rewritten.append(
                    (
                        name,
                        [f"- Promotes {len(related_pulls)} related PR(s)."]
                        + [f"- #{int(pr['number'])}: {str(pr.get('title') or '').strip()}" for pr in related_pulls],
                    )
                )
            else:
                rewritten.append((name, lines))
        else:
            rewritten.append((name, lines))

    for target in reversed(("Linked Issue", "Milestone", "Related PRs")):
        key = normalize_header(target)
        if key in replacements and key not in seen_sections:
            rewritten.insert(0, (target, replacements[key]))
    if not has_summary:
        rewritten.append(
            (
                "Summary",
                [f"- Promotes {len(related_pulls)} related PR(s)."]
                + [f"- #{int(pr['number'])}: {str(pr.get('title') or '').strip()}" for pr in related_pulls],
            )
        )

    rendered = _render_body(preamble, rewritten)
    return rendered, rendered != (body or "")


def _upsert_comment(
    client: GitHubClient,
    repo: str,
    number: int,
    marker: str,
    body: str,
    *,
    dry_run: bool = False,
) -> None:
    existing = next(
        (comment for comment in client.list_issue_comments(repo, number) if marker in (comment.get("body") or "")),
        None,
    )
    if dry_run:
        print(body)
    elif existing:
        client.update_issue_comment(repo, int(existing["id"]), body)
    else:
        client.create_issue_comment(repo, number, body)


def render_detection_comment(ctx: PullRequestContext, detection: RelatedPrDetection) -> str:
    lines = [
        RELATED_PRS_MARKER,
        "## Related PR detection",
        "",
        f"- Promotion: `{ctx.head_ref} -> {ctx.base_ref}`",
        f"- Detection cutoff: `{detection.cutoff or 'none'}` ({detection.cutoff_source})",
        f"- Explicit body references: {', '.join(f'#{n}' for n in detection.explicit_numbers) or 'none'}",
        f"- Branch-pattern matches: {', '.join(f'#{n}' for n in detection.branch_match_numbers) or 'none'}",
        f"- Inherited promotion references: {', '.join(f'#{n}' for n in detection.inherited_numbers) or 'none'}",
        f"- Source promotion PRs: {', '.join(f'#{n}' for n in detection.source_promotion_numbers) or 'none'}",
        "- Related PRs:",
    ]
    lines.extend(f"  - #{number}" for number in detection.related_numbers)
    if not detection.related_numbers:
        lines.append("  - none")
    return "\n".join(lines)


def apply_promotion_autofill(
    client: GitHubClient,
    repo: str,
    event: dict[str, Any],
    *,
    config_path: str | os.PathLike[str] = "project_setup.json",
    dry_run: bool = False,
) -> int:
    ctx = context_from_event(event, client=client, repo=repo)
    if not is_promotion_context(ctx, config_path):
        return 0

    detection = detect_related_prs(client, repo, ctx, config_path=config_path)
    related_pulls = [_fetch_pull(client, repo, number) for number in detection.related_numbers]
    related_pulls = [pr for pr in related_pulls if pr.get("merged_at")]
    _upsert_comment(
        client,
        repo,
        ctx.number,
        RELATED_PRS_MARKER,
        render_detection_comment(ctx, detection),
        dry_run=dry_run,
    )
    if not related_pulls:
        print(f"Related PR detection found no merged PRs for promotion {ctx.head_ref} -> {ctx.base_ref}.")
        return 0

    updated_body, changed = rewrite_promotion_body(ctx.body, related_pulls)
    if not changed:
        print(f"Promotion PR #{ctx.number} already contains the detected related PR context.")
        return 0
    if dry_run:
        print(f"[DRY-RUN] Would update promotion PR #{ctx.number} with {len(related_pulls)} related PR(s).")
        return 0
    client.request_json("PATCH", f"{API_BASE}/repos/{repo}/pulls/{ctx.number}", {"body": updated_body})
    print(f"Updated promotion PR #{ctx.number} with {len(related_pulls)} related PR(s).")
    return 0


def validate_promotion_context(
    client: GitHubClient,
    repo: str,
    pr_number: int,
    *,
    config_path: str | os.PathLike[str] = "project_setup.json",
) -> list[str]:
    live_pr = _fetch_pull(client, repo, pr_number)
    ctx = context_from_event({"action": "synchronize", "pull_request": live_pr})
    if not is_promotion_context(ctx, config_path):
        return []

    config = load_related_prs_config(config_path)
    body_numbers = pr_numbers_from_body_sections(
        ctx.body,
        [str(item) for item in config.get("bodySections", [])],
    )
    if not body_numbers:
        return ["Promotion PR has no related PR references in a configured Related PRs section."]

    findings: list[str] = []
    for number in body_numbers:
        if not _fetch_pull(client, repo, number).get("merged_at"):
            findings.append(f"Related PR #{number} is not merged and cannot be promoted.")

    detection = detect_related_prs(client, repo, ctx, config_path=config_path)
    body_set = set(body_numbers)
    missing = [number for number in detection.related_numbers if number not in body_set]
    if missing:
        findings.append("Promotion PR is missing auto-detected related PRs: " + ", ".join(f"#{n}" for n in missing))
    return findings


def _promotion_link_marker(base_ref: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", base_ref).strip("-") or "target"
    return f"{PROMOTION_LINK_MARKER_PREFIX}{safe} -->"


def _render_promotion_link(ctx: PullRequestContext, state: str) -> str:
    return "\n".join(
        [
            _promotion_link_marker(ctx.base_ref),
            "## Promotion linkage",
            f"- State: `{state}`",
            f"- Stage: `{ctx.base_ref}`",
            f"- Promotion PR: #{ctx.number}",
        ]
    )


def apply_promotion_sync(
    client: GitHubClient,
    repo: str,
    event: dict[str, Any],
    *,
    config_path: str | os.PathLike[str] = "project_setup.json",
    dry_run: bool = False,
) -> int:
    ctx = context_from_event(event, client=client, repo=repo)
    if not is_promotion_context(ctx, config_path):
        return 0

    config = load_related_prs_config(config_path)
    related_numbers = pr_numbers_from_body_sections(
        ctx.body,
        [str(item) for item in config.get("bodySections", [])],
    )
    if not related_numbers:
        print(f"Promotion Sync: PR #{ctx.number} has no Related PRs context.")
        return 1

    state = "merged" if ctx.action == "closed" and ctx.merged else "planned"
    marker = _promotion_link_marker(ctx.base_ref)
    backlink = _render_promotion_link(ctx, state)
    for number in related_numbers:
        _upsert_comment(client, repo, number, marker, backlink, dry_run=dry_run)

    summary = "\n".join(
        [
            RELATED_PRS_MARKER,
            "## Promotion Sync",
            "",
            f"- Promotion: `{ctx.head_ref} -> {ctx.base_ref}`",
            f"- State: `{state}`",
            "- Related PRs:",
            *[f"  - #{number}" for number in related_numbers],
        ]
    )
    _upsert_comment(client, repo, ctx.number, RELATED_PRS_MARKER, summary, dry_run=dry_run)
    return 0


def _load_event(path: str | os.PathLike[str]) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Detect and synchronize related PR context for promotion pull requests")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("autofill", "sync"):
        command = sub.add_parser(name)
        command.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
        command.add_argument("--event-path", default=os.getenv("GITHUB_EVENT_PATH"))
        command.add_argument("--config", default=os.getenv("PROJECT_SETUP_CONFIG", "project_setup.json"))
        command.add_argument("--dry-run", action="store_true")
    validate = sub.add_parser("validate")
    validate.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    validate.add_argument("--pr-number", type=int, required=True)
    validate.add_argument("--config", default=os.getenv("PROJECT_SETUP_CONFIG", "project_setup.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.repo:
        raise SystemExit("Missing --repo or GITHUB_REPOSITORY")
    client = require_client()
    if args.command == "validate":
        findings = validate_promotion_context(client, args.repo, args.pr_number, config_path=args.config)
        for finding in findings:
            print(f"Promotion context: {finding}")
        return 1 if findings else 0
    if not args.event_path:
        raise SystemExit("Missing --event-path or GITHUB_EVENT_PATH")
    event = _load_event(args.event_path)
    if args.command == "autofill":
        return apply_promotion_autofill(client, args.repo, event, config_path=args.config, dry_run=args.dry_run)
    return apply_promotion_sync(client, args.repo, event, config_path=args.config, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
