from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from project_setup.github import GitHubClient
from project_setup.pr_sync import (
    DEFAULT_SYNC_CONFIG,
    PullRequestContext,
    SYNC_MARKER,
    apply_pr_sync,
    linked_task_number,
    load_sync_config,
    parent_issue_number,
    project_status_for_context,
    sync_parent_relationship,
    sync_pr_metadata,
    upsert_sync_comment,
)
from project_setup.pr_validation import validate_pull_request


ROOT = Path(__file__).resolve().parents[1]


class PrSyncTests(unittest.TestCase):
    def context(self, **overrides) -> PullRequestContext:
        values = {
            "number": 33,
            "action": "opened",
            "body": "Closes #12",
            "base_ref": "develop",
            "head_ref": "feat/example",
            "head_repo": "owner/repo",
            "author": "alice",
            "draft": False,
            "merged": False,
        }
        values.update(overrides)
        return PullRequestContext(**values)

    def event(self, **overrides) -> dict:
        pull_request = {
            "number": 33,
            "body": "Closes #12",
            "base": {"ref": "develop"},
            "head": {"ref": "feat/example", "repo": {"full_name": "owner/repo"}},
            "user": {"login": "alice"},
            "draft": False,
            "merged": False,
        }
        pull_request.update(overrides.pop("pull_request", {}))
        event = {"action": "opened", "pull_request": pull_request}
        event.update(overrides)
        return event

    def test_linked_task_parser_accepts_closing_keywords(self):
        for body in ("Closes #12", "fixes: #12", "Resolves #12"):
            with self.subTest(body=body):
                self.assertEqual(linked_task_number(body), 12)

    def test_parent_parser_accepts_generated_task_body(self):
        self.assertEqual(parent_issue_number("Parent story: US-12 (#8)"), 8)
        self.assertEqual(parent_issue_number("Parent issue: #9"), 9)

    def test_default_lifecycle_mapping(self):
        self.assertEqual(
            project_status_for_context(self.context(draft=True), DEFAULT_SYNC_CONFIG),
            "In progress",
        )
        self.assertEqual(
            project_status_for_context(self.context(action="ready_for_review"), DEFAULT_SYNC_CONFIG),
            "In review",
        )
        self.assertEqual(
            project_status_for_context(self.context(action="closed", merged=False), DEFAULT_SYNC_CONFIG),
            "In progress",
        )
        self.assertEqual(
            project_status_for_context(self.context(action="closed", merged=True), DEFAULT_SYNC_CONFIG),
            "Done",
        )

    def test_config_merges_custom_status_with_defaults(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            json.dump(
                {
                    "prAutomation": {
                        "sync": {
                            "syncAssignees": False,
                            "projectStatus": {"review": "Review"},
                        }
                    }
                },
                handle,
            )
            path = handle.name

        config = load_sync_config(path)

        self.assertFalse(config["syncAssignees"])
        self.assertEqual(config["projectStatus"]["review"], "Review")
        self.assertEqual(config["projectStatus"]["merged"], "Done")

    def test_metadata_sync_adds_only_configured_labels_and_missing_assignees(self):
        client = Mock(spec=GitHubClient)
        task = {
            "number": 12,
            "labels": [
                {"name": "type:task"},
                {"name": "priority:high"},
                {"name": "status:backlog"},
            ],
            "milestone": {"number": 4},
            "assignees": [{"login": "alice"}],
        }
        pr_issue = {
            "labels": [{"name": "type:task"}],
            "milestone": None,
            "assignees": [],
        }

        sync_pr_metadata(
            client,
            "owner/repo",
            self.context(),
            task,
            pr_issue,
            DEFAULT_SYNC_CONFIG,
        )

        client.request_json.assert_any_call(
            "POST",
            "https://api.github.com/repos/owner/repo/issues/33/labels",
            {"labels": ["priority:high"]},
        )
        client.request_json.assert_any_call(
            "POST",
            "https://api.github.com/repos/owner/repo/issues/33/assignees",
            {"assignees": ["alice"]},
        )
        client.update_issue.assert_called_once_with("owner/repo", 33, {"milestone": 4})

    def test_metadata_sync_can_assign_author_when_task_is_unassigned(self):
        client = Mock(spec=GitHubClient)
        task = {"number": 12, "labels": [], "milestone": None, "assignees": []}
        pr_issue = {"labels": [], "milestone": None, "assignees": []}

        sync_pr_metadata(
            client,
            "owner/repo",
            self.context(author="alice"),
            task,
            pr_issue,
            DEFAULT_SYNC_CONFIG,
        )

        client.request_json.assert_any_call(
            "POST",
            "https://api.github.com/repos/owner/repo/issues/12/assignees",
            {"assignees": ["alice"]},
        )
        client.request_json.assert_any_call(
            "POST",
            "https://api.github.com/repos/owner/repo/issues/33/assignees",
            {"assignees": ["alice"]},
        )

    def test_parent_sync_treats_existing_relationship_as_idempotent(self):
        client = Mock(spec=GitHubClient)
        task = {"number": 12, "body": "Parent story: US-1 (#8)"}

        with patch(
            "project_setup.pr_sync.add_sub_issue",
            side_effect=RuntimeError("duplicate sub-issues"),
        ):
            note = sync_parent_relationship(
                client,
                "owner/repo",
                task,
                DEFAULT_SYNC_CONFIG,
            )

        self.assertIn("already", note)

    def test_fork_pull_request_is_skipped_before_reads(self):
        client = Mock(spec=GitHubClient)
        event = self.event(
            pull_request={
                "head": {
                    "ref": "feat/example",
                    "repo": {"full_name": "fork-owner/repo"},
                }
            }
        )

        result = apply_pr_sync(client, "owner/repo", event, DEFAULT_SYNC_CONFIG)

        self.assertEqual(result, 0)
        client.get_issue.assert_not_called()

    def test_promotion_pull_request_is_skipped(self):
        client = Mock(spec=GitHubClient)
        event = self.event(
            pull_request={
                "base": {"ref": "Q.A"},
                "head": {"ref": "develop", "repo": {"full_name": "owner/repo"}},
            }
        )

        result = apply_pr_sync(client, "owner/repo", event, DEFAULT_SYNC_CONFIG)

        self.assertEqual(result, 0)
        client.get_issue.assert_not_called()

    def test_promotion_pull_request_skips_implementation_metadata_body(self):
        placeholder_body = "## Linked Issue\n- Closes #<issue-number>\n\n## Summary\n- <what changed and why>"
        self.assertEqual(validate_pull_request("develop", placeholder_body, "Q.A"), [])
        self.assertEqual(validate_pull_request("Q.A", placeholder_body, "main"), [])

    def test_missing_linked_task_sets_sticky_failure_comment(self):
        client = Mock(spec=GitHubClient)
        client.list_issue_comments.return_value = []
        event = self.event(pull_request={"body": ""})

        result = apply_pr_sync(client, "owner/repo", event, DEFAULT_SYNC_CONFIG)

        self.assertEqual(result, 1)
        body = client.create_issue_comment.call_args.args[2]
        self.assertIn(SYNC_MARKER, body)
        self.assertIn("No linked implementation task", body)

    def test_linked_pull_request_is_rejected_as_task(self):
        client = Mock(spec=GitHubClient)
        client.get_issue.return_value = {
            "number": 12,
            "pull_request": {"url": "https://api.github.com/repos/owner/repo/pulls/12"},
        }
        client.list_issue_comments.return_value = []

        result = apply_pr_sync(client, "owner/repo", self.event(), DEFAULT_SYNC_CONFIG)

        self.assertEqual(result, 1)
        self.assertIn(
            "not an implementation issue/task",
            client.create_issue_comment.call_args.args[2],
        )

    def test_success_comment_is_updated_instead_of_duplicated(self):
        client = Mock(spec=GitHubClient)
        client.list_issue_comments.return_value = [{"id": 99, "body": f"{SYNC_MARKER}\nold"}]

        upsert_sync_comment(
            client,
            "owner/repo",
            33,
            f"{SYNC_MARKER}\nnew",
        )

        client.update_issue_comment.assert_called_once_with(
            "owner/repo",
            99,
            f"{SYNC_MARKER}\nnew",
        )
        client.create_issue_comment.assert_not_called()


class PrSyncWorkflowContractTests(unittest.TestCase):
    def test_pr_sync_runs_directly_for_relevant_pr_lifecycle_events(self):
        text = (ROOT / ".github/workflows/pr-sync.yml").read_text(encoding="utf-8")

        for expected in (
            "name: PR Sync",
            "pull_request_target:",
            "- opened",
            "- synchronize",
            "- reopened",
            "- edited",
            "- ready_for_review",
            "- converted_to_draft",
            "- closed",
            "github.event.pull_request.head.repo.full_name == github.repository",
            "ref: ${{ github.event.pull_request.base.sha }}",
            "persist-credentials: false",
            "PROJECT_SETUP_PAT: ${{ secrets.PROJECT_SETUP_PAT }}",
            "PROJECT_SETUP_PROJECT_NUMBER: ${{ vars.PROJECT_SETUP_PROJECT_NUMBER }}",
            "python -m project_setup.pr_sync",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

        self.assertNotIn("workflow_run:", text)
        self.assertNotIn('workflows: ["PR metadata validation", "PR guardrails"]', text)
        self.assertNotIn("github.event.pull_request.head.sha", text)
        self.assertNotIn("refs/heads/${{ github.event.pull_request.head.ref }}", text)

    def test_metadata_validation_depends_on_successful_pr_sync(self):
        text = (ROOT / ".github/workflows/pr-metadata.yml").read_text(encoding="utf-8")

        for expected in (
            "name: PR metadata validation",
            "workflow_run:",
            'workflows: ["PR Sync"]',
            "github.event.workflow_run.conclusion == 'success'",
            "github.event.workflow_run.event == 'pull_request_target'",
            "github.event.workflow_run.pull_requests[0].number != null",
            "pull-requests: read",
            "ref: ${{ github.event.repository.default_branch }}",
            "--skip-draft-or-closed",
            "--pr-number \"$PR_NUMBER\"",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

        self.assertNotIn("pull_request_target:", text)
        self.assertNotIn("PR_BODY:", text)

    def test_installer_distributes_pr_sync_workflow(self):
        text = (ROOT / "project_setup/installer.py").read_text(encoding="utf-8")
        self.assertIn('".github/workflows/pr-sync.yml"', text)


if __name__ == "__main__":
    unittest.main()
