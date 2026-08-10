#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from project_setup.github import API_BASE, get_token, require_client
from project_setup.pr_validation import upsert_validation_comment, validate_pull_request


def read_pull_request(args: argparse.Namespace) -> dict | None:
    if not args.repo or not args.pr_number or not get_token():
        return None
    return require_client().request_json(
        "GET",
        f"{API_BASE}/repos/{args.repo}/pulls/{args.pr_number}",
    )


def read_body(args: argparse.Namespace, pull_request: dict | None = None) -> str:
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    if pull_request is not None:
        return pull_request.get("body") or ""
    if args.repo and args.pr_number and get_token():
        return require_client().get_issue(args.repo, args.pr_number).get("body") or ""
    if os.getenv("PR_BODY") is not None:
        return os.environ["PR_BODY"]
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate pull request branch naming and metadata")
    parser.add_argument("--file")
    parser.add_argument("--branch")
    parser.add_argument("--base-branch")
    parser.add_argument("--repo")
    parser.add_argument("--pr-number", type=int)
    parser.add_argument("--comment", action="store_true")
    parser.add_argument(
        "--skip-draft-or-closed",
        action="store_true",
        help="Skip active metadata validation when the resolved pull request is draft or closed.",
    )
    args = parser.parse_args()

    pull_request = read_pull_request(args)
    if args.skip_draft_or_closed and pull_request is not None:
        if pull_request.get("draft") or pull_request.get("state") != "open":
            print("Skipping metadata validation for draft or closed pull request.")
            return 0

    branch = args.branch
    base_branch = args.base_branch
    if pull_request is not None:
        branch = branch or (pull_request.get("head") or {}).get("ref")
        base_branch = base_branch or (pull_request.get("base") or {}).get("ref")

    findings = validate_pull_request(branch, read_body(args, pull_request), base_branch)
    for finding in findings:
        print(f"{finding.section}: {finding.problem}", file=sys.stderr)
        print(f"  Fix: {finding.fix}", file=sys.stderr)
    if args.comment:
        if not args.repo or not args.pr_number:
            print("--comment requires --repo and --pr-number", file=sys.stderr)
            return 2
        upsert_validation_comment(require_client(), args.repo, args.pr_number, findings)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
