#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from project_setup.github import get_token, require_client
from project_setup.pr_validation import upsert_validation_comment, validate_pull_request


def read_body(args: argparse.Namespace) -> str:
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
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
    args = parser.parse_args()

    findings = validate_pull_request(args.branch, read_body(args), args.base_branch)
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
