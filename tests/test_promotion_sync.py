from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from project_setup.github import GitHubClient
from project_setup.pr_sync import PullRequestContext
from project_setup.promotion_sync import (
    PromotionMetadata,
    aggregate_promotion_metadata,
    sync_promotion_native_metadata,
    sync_promotion_project_status,
)


ROOT = Path(__file__).resolve().parents[1]


class PromotionMetadataAggregationTests(unittest.TestCase):
    def item(self, *, labels=None, assignees=None, milestone=None):
        return {
            "labels": [{"name": name} for name in (labels or [])],
            "assignees": [{"login": login} for login in (assignees or [])],
            "milestone": milestone,
        }

    def test_consensus_labels_milestone_and_assignee_union(self):
        items = [
            self.item(
                labels=["type:task", "priority:high", "test:manual", "status:backlog"],
                assignees=["alice"],
                milestone={"number": 3, "title": "M3"},
            ),
            self.item(
                labels=["type:task", "priority:high", "test:manual"],
                assignees=["bob", "alice"],
                milestone={"number": 3, "title": "M3"},
            ),
        ]

        result = aggregate_promotion_metadata(items, ["type:", "priority:", "test:"])

        self.assertEqual(result.labels, ["type:task", "priority:high", "test:manual"])
        self.assertEqual(result.label_conflicts, [])
        self.assertEqual(result.assignees, ["alice", "bob"])
        self.assertEqual(result.milestone_number, 3)
        self.assertEqual(result.milestone_title, "M3")
        self.assertIsNone(result.milestone_conflict)

    def test_conflicting_single_value_metadata_is_not_invented(self):
        items = [
            self.item(
                labels=["type:task", "priority:high"],
                milestone={"number": 3, "title": "M3"},
            ),
            self.item(
                labels=["type:task", "priority:medium"],
                milestone={"number": 4, "title": "M4"},
            ),
        ]

        result = aggregate_promotion_metadata(items, ["type:", "priority:", "test:"])

        self.assertEqual(result.labels, ["type:task"])
        self.assertTrue(any(conflict.startswith("priority:") for conflict in result.label_conflicts))
        self.assertIsNone(result.milestone_number)
        self.assertIsNotNone(result.milestone_conflict)


class PromotionNativeSyncTests(unittest.TestCase):
    def context(self) -> PullRequestContext:
        return PullRequestContext(
            number=65,
            action="synchronize",
            body="## Related PRs\n- #63\n- #67\n",
            base_ref="main",
            head_ref="Q.A",
            head_repo="owner/repo",
            author="alice",
            draft=False,
            merged=False,
        )

    def config(self) -> dict:
        return {
            "syncLabels": True,
            "labelPrefixes": ["type:", "priority:", "test:"],
            "syncMilestone": True,
            "syncAssignees": True,
            "syncProject": True,
            "projectStatusField": "Status",
        }

    def test_native_sync_replaces_managed_labels_and_sets_milestone_and_assignees(self):
        client = Mock(spec=GitHubClient)
        pr_issue = {
            "number": 65,
            "labels": [{"name": "priority:old"}, {"name": "keep-me"}],
            "assignees": [],
            "milestone": None,
        }
        metadata = PromotionMetadata(
            labels=["type:task", "priority:high", "test:manual"],
            label_conflicts=[],
            assignees=["alice", "bob"],
            milestone_number=3,
            milestone_title="M3",
            milestone_conflict=None,
        )

        sync_promotion_native_metadata(
            client,
            "owner/repo",
            self.context(),
            pr_issue,
            metadata,
            self.config(),
        )

        client.request_json.assert_any_call(
            "PUT",
            "https://api.github.com/repos/owner/repo/issues/65/labels",
            {"labels": ["keep-me", "priority:high", "test:manual", "type:task"]},
        )
        client.update_issue.assert_called_once_with("owner/repo", 65, {"milestone": 3})
        client.request_json.assert_any_call(
            "POST",
            "https://api.github.com/repos/owner/repo/issues/65/assignees",
            {"assignees": ["alice", "bob"]},
        )

    def test_conflict_clears_managed_labels_and_milestone(self):
        client = Mock(spec=GitHubClient)
        pr_issue = {
            "number": 65,
            "labels": [{"name": "priority:old"}, {"name": "keep-me"}],
            "assignees": [],
            "milestone": {"number": 3},
        }
        metadata = PromotionMetadata(
            labels=[],
            label_conflicts=["priority: [priority:high, priority:medium]"],
            assignees=[],
            milestone_number=None,
            milestone_title=None,
            milestone_conflict="related PR milestones disagree [3, 4]",
        )

        sync_promotion_native_metadata(
            client,
            "owner/repo",
            self.context(),
            pr_issue,
            metadata,
            self.config(),
        )

        client.request_json.assert_called_once_with(
            "PUT",
            "https://api.github.com/repos/owner/repo/issues/65/labels",
            {"labels": ["keep-me"]},
        )
        client.update_issue.assert_called_once_with("owner/repo", 65, {"milestone": None})

    def test_promotion_pr_itself_is_added_to_project_and_statused(self):
        client = Mock(spec=GitHubClient)
        pr_issue = {"number": 65, "node_id": "PR_node_65"}
        status_field = {
            "id": "FIELD_STATUS",
            "name": "Status",
            "options": [{"id": "OPT_REVIEW", "name": "In review"}],
        }

        with (
            patch("project_setup.promotion_sync.find_project", return_value={"id": "PROJECT"}),
            patch("project_setup.promotion_sync.list_project_fields", return_value=[status_field]),
            patch("project_setup.promotion_sync.list_project_content_items", return_value={}),
            patch("project_setup.promotion_sync.add_issue_to_project", return_value="ITEM") as add_item,
            patch("project_setup.promotion_sync.update_single_select") as update_status,
        ):
            note = sync_promotion_project_status(
                client,
                "owner/repo",
                self.context(),
                pr_issue,
                42,
                "In review",
                self.config(),
                owner="owner",
            )

        add_item.assert_called_once_with(client, "PROJECT", "PR_node_65")
        update_status.assert_called_once_with(client, "PROJECT", "ITEM", "FIELD_STATUS", "OPT_REVIEW")
        self.assertIn("promotion PR synced", note)


class PromotionWorkflowContractTests(unittest.TestCase):
    def test_live_qa_runs_promotion_native_metadata_smoke(self):
        workflow = (ROOT / ".github/workflows/qa-live.yml").read_text(encoding="utf-8")
        self.assertIn("python tests/qa/live_promotion_sync.py", workflow)

    def test_router_forwards_project_context_to_promotion_sync(self):
        from project_setup.pr_sync_router import apply_routed_pr_sync

        event = {
            "action": "opened",
            "pull_request": {
                "number": 65,
                "body": "## Related PRs\n- #63\n",
                "base": {"ref": "main"},
                "head": {"ref": "Q.A", "repo": {"full_name": "owner/repo"}},
                "user": {"login": "alice"},
                "draft": False,
                "merged": False,
            },
        }
        client = Mock(spec=GitHubClient)
        project_client = Mock(spec=GitHubClient)

        with patch("project_setup.pr_sync_router.is_promotion_context", return_value=True), patch(
            "project_setup.pr_sync_router.apply_promotion_sync", return_value=0
        ) as promotion_sync:
            result = apply_routed_pr_sync(
                client,
                "owner/repo",
                event,
                config_path="project_setup.json",
                project_client=project_client,
                project_number=42,
                owner="owner",
            )

        self.assertEqual(result, 0)
        promotion_sync.assert_called_once_with(
            client,
            "owner/repo",
            event,
            config_path="project_setup.json",
            project_client=project_client,
            project_number=42,
            owner="owner",
            dry_run=False,
        )


if __name__ == "__main__":
    unittest.main()
