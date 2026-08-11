from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from project_setup.github import GitHubClient
from project_setup.pr_sync import PullRequestContext
from project_setup.pr_sync_router import apply_routed_pr_sync
from project_setup.related_prs import (
    DEFAULT_BRANCH_PATTERNS,
    branch_matches,
    detect_related_prs,
    load_related_prs_config,
    pr_numbers_from_body_sections,
    rewrite_promotion_body,
)


ROOT = Path(__file__).resolve().parents[1]


class RelatedPrDetectionTests(unittest.TestCase):
    def config_file(self, related: dict | None = None) -> str:
        data = {
            "prAutomation": {
                "relatedPrs": related or {},
                "sync": {
                    "promotionPaths": [
                        {"head": "develop", "base": "Q.A"},
                        {"head": "Q.A", "base": "main"},
                    ]
                },
            }
        }
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
        json.dump(data, handle)
        handle.close()
        return handle.name

    def promotion_context(self, **overrides) -> PullRequestContext:
        values = {
            "number": 100,
            "action": "opened",
            "body": "## Related PRs\n- #99\n",
            "base_ref": "Q.A",
            "head_ref": "develop",
            "head_repo": "owner/repo",
            "author": "alice",
            "draft": False,
            "merged": False,
        }
        values.update(overrides)
        return PullRequestContext(**values)

    def test_default_patterns_are_broad_examples(self):
        for branch in (
            "feat/example",
            "fix/example",
            "docs/example",
            "refactor/example",
            "test/example",
            "hotfix/example",
            "phase/example",
            "task/example",
            "chore/example",
            "ci/example",
            "release/example",
        ):
            with self.subTest(branch=branch):
                self.assertTrue(branch_matches(branch, DEFAULT_BRANCH_PATTERNS))
        self.assertFalse(branch_matches("integration/example", DEFAULT_BRANCH_PATTERNS))

    def test_branch_patterns_are_replaceable_by_configuration(self):
        path = self.config_file({"branchPatterns": [r"^work/", r"^bug/"]})
        config = load_related_prs_config(path)
        self.assertEqual(config["branchPatterns"], [r"^work/", r"^bug/"])
        self.assertTrue(branch_matches("work/123", config["branchPatterns"]))
        self.assertFalse(branch_matches("feat/123", config["branchPatterns"]))

    def test_body_references_are_independent_of_branch_patterns(self):
        body = """## Related PRs
- #31
- https://github.com/owner/repo/pull/32
- <optional related pull request numbers; example #999>

## Summary
- Keep me
"""
        self.assertEqual(pr_numbers_from_body_sections(body, ["Related PRs"]), [31, 32])

    def test_detection_unions_explicit_branch_and_inherited_references(self):
        path = self.config_file({"fallbackDays": 0})
        client = Mock(spec=GitHubClient)

        previous_promotions = [
            {
                "number": 80,
                "merged_at": "2026-08-01T00:00:00Z",
                "head": {"ref": "develop"},
                "base": {"ref": "Q.A"},
            }
        ]
        source_prs = [
            {
                "number": 70,
                "merged_at": "2026-07-30T00:00:00Z",
                "head": {"ref": "feat/old"},
                "base": {"ref": "develop"},
                "body": "",
            },
            {
                "number": 90,
                "merged_at": "2026-08-05T00:00:00Z",
                "head": {"ref": "fix/current"},
                "base": {"ref": "develop"},
                "body": "",
            },
            {
                "number": 91,
                "merged_at": "2026-08-06T00:00:00Z",
                "head": {"ref": "integration/current"},
                "base": {"ref": "develop"},
                "body": "## Related PRs\n- #88\n",
            },
        ]
        client.paginated.side_effect = [previous_promotions, source_prs]

        result = detect_related_prs(
            client,
            "owner/repo",
            self.promotion_context(),
            config_path=path,
        )

        self.assertEqual(result.explicit_numbers, [99])
        self.assertEqual(result.branch_match_numbers, [90])
        self.assertEqual(result.inherited_numbers, [88])
        self.assertEqual(result.related_numbers, [99, 90, 88])
        self.assertEqual(result.cutoff, "2026-08-01T00:00:00Z")
        self.assertEqual(result.cutoff_source, "previous promotion")

    def test_promotion_body_aggregates_related_prs_issues_and_milestones(self):
        body = """## Linked Issue
- Closes #<issue-number>

## Milestone
- <milestone>

## Related PRs
- <optional related pull request numbers>

## Summary
- <what changed and why>

## Known risks
- None
"""
        pulls = [
            {
                "number": 41,
                "title": "feat: one",
                "body": "Closes #10",
                "milestone": {"title": "M1"},
            },
            {
                "number": 42,
                "title": "fix: two",
                "body": "Fixes #11\nResolves #10",
                "milestone": {"title": "M2"},
            },
        ]

        updated, changed = rewrite_promotion_body(body, pulls)

        self.assertTrue(changed)
        self.assertIn("- Closes #10", updated)
        self.assertIn("- Closes #11", updated)
        self.assertEqual(updated.count("Closes #10"), 1)
        self.assertIn("## Milestone\n- M1\n- M2", updated)
        self.assertIn("## Related PRs\n- #41 — feat: one\n- #42 — fix: two", updated)
        self.assertIn("Promotes 2 related PR(s)", updated)
        self.assertIn("## Known risks\n- None", updated)

    def test_human_summary_is_preserved(self):
        body = "## Summary\n- Human-authored release rationale\n"
        updated, _ = rewrite_promotion_body(
            body,
            [{"number": 41, "title": "feat: one", "body": "Closes #10", "milestone": None}],
        )
        self.assertIn("## Summary\n- Human-authored release rationale", updated)


class PrSyncRouterTests(unittest.TestCase):
    def test_promotion_routes_to_aggregate_sync_not_implementation_sync(self):
        event = {
            "action": "opened",
            "pull_request": {
                "number": 54,
                "body": "## Related PRs\n- #53\n",
                "base": {"ref": "Q.A"},
                "head": {"ref": "develop", "repo": {"full_name": "owner/repo"}},
                "user": {"login": "alice"},
                "draft": False,
                "merged": False,
            },
        }
        client = Mock(spec=GitHubClient)

        with (
            patch("project_setup.pr_sync_router.apply_promotion_sync", return_value=0) as promotion_sync,
            patch("project_setup.pr_sync_router.apply_pr_sync", return_value=0) as implementation_sync,
        ):
            result = apply_routed_pr_sync(
                client,
                "owner/repo",
                event,
                config_path=str(ROOT / "project_setup.json"),
            )

        self.assertEqual(result, 0)
        promotion_sync.assert_called_once()
        implementation_sync.assert_not_called()

    def test_workflows_use_related_pr_guardrails_and_sync_router(self):
        guardrails = (ROOT / ".github/workflows/pr-metadata.yml").read_text(encoding="utf-8")
        sync = (ROOT / ".github/workflows/pr-sync.yml").read_text(encoding="utf-8")
        self.assertIn("python -m project_setup.related_prs autofill", guardrails)
        self.assertIn("python -m project_setup.related_prs validate", guardrails)
        self.assertLess(
            guardrails.index("python -m project_setup.related_prs autofill"),
            guardrails.index("python scripts/validation/validate_pr_body.py"),
        )
        self.assertIn("python -m project_setup.pr_sync_router", sync)

    def test_committed_config_has_no_promotion_skip_switch(self):
        data = json.loads((ROOT / "project_setup.json").read_text(encoding="utf-8"))
        self.assertNotIn("skipPromotionPullRequests", data["prAutomation"]["sync"])
        patterns = data["prAutomation"]["relatedPrs"]["branchPatterns"]
        self.assertIn("^feat/", patterns)
        self.assertIn("^fix/", patterns)
        self.assertIn("^ci/", patterns)


if __name__ == "__main__":
    unittest.main()
