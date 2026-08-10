from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
from typing import Any

from .github import API_BASE, GitHubClient, require_client
from .issues import load_backlog, task_title
from .pr_sync import (
    context_from_event,
    is_promotion_pull_request,
    is_same_repository,
    linked_task_number,
    load_sync_config,
)
from .project import list_repo_issues


SECTION_HEADING_PATTERN = re.compile(r"^##\s+(.+?)\s*$")
BRANCH_STORY_PATTERN = re.compile(r"(?i)(?:^|[^A-Z0-9])US-(\d+)(?=$|[^A-Z0-9])")
BRANCH_TASK_PATTERN = re.compile(r"(?i)(?:^|[^A-Z0-9])T-(\d+(?:\.\d+)?)(?=$|[^A-Z0-9])")
BRANCH_ISSUE_PATTERN = re.compile(r"(?i)(?:^|[/_.-])(?:issue|task)[-_]?(\d+)(?=$|[/_.-])")
TARGET_SECTIONS = ("Linked Issue", "Milestone")


def normalize_text(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def split_body(body: str) -> tuple[list[str], list[tuple[str, list[str]]]]:
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
            continue
        if current_name is None:
            preamble.append(line)
        else:
            current_lines.append(line)

    if current_name is not None:
        sections.append((current_name, current_lines))
    return preamble, sections


def render_body(preamble: list[str], sections: list[tuple[str, list[str]]]) -> str:
    parts: list[str] = []
    if preamble:
        text = "\n".join(preamble).rstrip()
        if text:
            parts.append(text)
    for name, lines in sections:
        text = f"## {name}"
        content = "\n".join(lines).rstrip()
        if content:
            text += f"\n{content}"
        parts.append(text)
    return ("\n\n".join(parts).rstrip() + "\n") if parts else ""


def rewrite_pr_body(body: str, issue_number: int, milestone: str | None) -> tuple[str, bool]:
    preamble, sections = split_body(body)
    replacements: dict[str, tuple[str, list[str]]] = {
        normalize_text("Linked Issue"): ("Linked Issue", [f"- Closes #{issue_number}"]),
    }
    if milestone:
        replacements[normalize_text("Milestone")] = ("Milestone", [f"- {milestone}"])

    rewritten: list[tuple[str, list[str]]] = []
    seen: set[str] = set()
    for name, lines in sections:
        key = normalize_text(name)
        if key in replacements:
            rewritten.append(replacements[key])
            seen.add(key)
        else:
            rewritten.append((name, lines))

    for target in TARGET_SECTIONS:
        key = normalize_text(target)
        if key in replacements and key not in seen:
            rewritten.insert(0 if target == "Linked Issue" else min(1, len(rewritten)), replacements[key])

    rendered = render_body(preamble, rewritten)
    return rendered, rendered != (body or "")


def _story_number(story_id: str | None) -> int | None:
    if not story_id:
        return None
    match = re.search(r"\d+", story_id)
    return int(match.group(0)) if match else None


def _task_key(value: str) -> str | None:
    match = re.match(r"(?i)^T-(\d+(?:\.\d+)?)\b", value.strip())
    return match.group(1) if match else None


def find_manifest_candidate(backlog: dict[str, Any], branch: str) -> tuple[str, str | None] | None:
    story_match = BRANCH_STORY_PATTERN.search(branch or "")
    task_match = BRANCH_TASK_PATTERN.search(branch or "")
    wanted_story = int(story_match.group(1)) if story_match else None
    wanted_task = task_match.group(1) if task_match else None

    for phase in backlog.get("phases", []):
        milestone = phase.get("milestone")
        for story in phase.get("stories", []):
            if wanted_story is not None and _story_number(story.get("storyId")) == wanted_story:
                return str(story["title"]), str(milestone) if milestone else None
            if wanted_task is not None:
                for task in story.get("tasks", []):
                    title = task_title(task)
                    if _task_key(title) == wanted_task:
                        return title, str(milestone) if milestone else None
    return None


def find_issue_by_exact_title(issues: list[dict[str, Any]], title: str) -> dict[str, Any] | None:
    matches = [issue for issue in issues if normalize_text(str(issue.get("title") or "")) == normalize_text(title)]
    open_matches = [issue for issue in matches if issue.get("state") == "open"]
    if len(open_matches) == 1:
        return open_matches[0]
    if len(open_matches) > 1:
        return None
    return matches[0] if len(matches) == 1 else None


def resolve_from_branch(
    client: GitHubClient,
    repo: str,
    branch: str,
    backlog_file: str,
) -> tuple[dict[str, Any] | None, str | None, str]:
    explicit = BRANCH_ISSUE_PATTERN.search(branch or "")
    if explicit:
        number = int(explicit.group(1))
        issue = client.get_issue(repo, number)
        if "pull_request" in issue:
            return None, None, f"branch references #{number}, but that item is a pull request"
        milestone = (issue.get("milestone") or {}).get("title")
        return issue, str(milestone) if milestone else None, f"resolved issue #{number} from branch token"

    backlog = load_backlog(backlog_file)
    candidate = find_manifest_candidate(backlog, branch)
    if not candidate:
        return None, None, "no deterministic issue/story/task token was found in the branch name"

    title, fallback_milestone = candidate
    issue = find_issue_by_exact_title(list_repo_issues(client, repo, state="all"), title)
    if not issue:
        return None, None, f"manifest item `{title}` did not resolve to one unambiguous repository issue"
    milestone = (issue.get("milestone") or {}).get("title") or fallback_milestone
    return issue, str(milestone) if milestone else None, f"resolved `{title}` from branch/backlog context"


def apply_pr_autofill(
    client: GitHubClient,
    repo: str,
    event: dict[str, Any],
    *,
    backlog_file: str = "config/stories/backlog-manifest.json",
    config_file: str = "project_setup.json",
    event_path: str | os.PathLike[str] | None = None,
    dry_run: bool = False,
) -> int:
    config = load_sync_config(config_file)
    ctx = context_from_event(event, client=client, repo=repo)

    if not is_same_repository(ctx, repo):
        print("Skipping PR Sync autofill for a fork pull request.")
        return 0
    if is_promotion_pull_request(ctx, config):
        print(f"Skipping PR Sync autofill for promotion PR {ctx.head_ref} -> {ctx.base_ref}.")
        return 0
    if linked_task_number(ctx.body) is not None:
        print("PR Sync autofill: explicit Linked Issue already present; preserving it as authoritative.")
        return 0

    issue, milestone, note = resolve_from_branch(client, repo, ctx.head_ref, backlog_file)
    if not issue:
        print(f"PR Sync autofill: {note}. No metadata was invented.")
        return 0

    issue_number = int(issue["number"])
    updated_body, changed = rewrite_pr_body(ctx.body, issue_number, milestone)
    if not changed:
        print(f"PR Sync autofill: PR body already matches resolved issue #{issue_number}.")
        return 0

    if dry_run:
        print(f"[DRY-RUN] Would autofill PR #{ctx.number} from issue #{issue_number}: {note}")
        return 0

    client.request_json(
        "PATCH",
        f"{API_BASE}/repos/{repo}/pulls/{ctx.number}",
        {"body": updated_body},
    )
    if event.get("pull_request") is not None:
        event["pull_request"]["body"] = updated_body
    if event_path:
        Path(event_path).write_text(json.dumps(event), encoding="utf-8")
    print(f"PR Sync autofill: updated PR #{ctx.number} from issue #{issue_number}; {note}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Autofill recoverable PR metadata before PR Sync")
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    parser.add_argument("--event-path", default=os.getenv("GITHUB_EVENT_PATH"))
    parser.add_argument("--backlog-file", default="config/stories/backlog-manifest.json")
    parser.add_argument("--config", default=os.getenv("PROJECT_SETUP_CONFIG", "project_setup.json"))
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.repo:
        raise SystemExit("Missing --repo or GITHUB_REPOSITORY")
    if not args.event_path:
        raise SystemExit("Missing --event-path or GITHUB_EVENT_PATH")
    event = json.loads(Path(args.event_path).read_text(encoding="utf-8"))
    return apply_pr_autofill(
        require_client(),
        args.repo,
        event,
        backlog_file=args.backlog_file,
        config_file=args.config,
        event_path=args.event_path,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
