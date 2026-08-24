from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from project_setup.github import GitHubClient
from project_setup.pr_project_sync import sync_pull_request_project_status
from project_setup.pr_sync import PullRequestContext
from project_setup.project_lookup import resolve_project_number


class PullRequestProjectSyncTests(unittest.TestCase):
    def context(self) -> PullRequestContext:
        return PullRequestContext(
            number=73,
            action="synchronize",
            body="Closes #72",
            base_ref="develop",
            head_ref="feat/issue-72",
            head_repo="owner/repo",
            author="alice",
            draft=False,
            merged=False,
        )

    def test_pr_itself_is_added_to_project_and_statused(self):
        client = Mock(spec=GitHubClient)
        config = {"syncProject": True, "projectStatusField": "Status"}
        status_field = {
            "id": "status-field",
            "name": "Status",
            "options": [{"id": "review-option", "name": "In review"}],
        }
        with (
            patch("project_setup.pr_project_sync.find_project", return_value={"id": "project-id"}),
            patch("project_setup.pr_project_sync.list_project_fields", return_value=[status_field]),
            patch("project_setup.pr_project_sync.list_project_content_items", return_value={}),
            patch("project_setup.pr_project_sync.add_issue_to_project", return_value="item-id") as add_item,
            patch("project_setup.pr_project_sync.update_single_select") as update_status,
        ):
            note = sync_pull_request_project_status(
                client,
                "owner/repo",
                self.context(),
                {"number": 73, "node_id": "PR_node"},
                6,
                "In review",
                config,
                owner="owner",
            )

        add_item.assert_called_once_with(client, "project-id", "PR_node")
        update_status.assert_called_once_with(
            client,
            "project-id",
            "item-id",
            "status-field",
            "review-option",
        )
        self.assertIn("PR #73", note)

    def test_existing_project_item_is_idempotent(self):
        client = Mock(spec=GitHubClient)
        status_field = {
            "id": "status-field",
            "name": "Status",
            "options": [{"id": "review-option", "name": "In review"}],
        }
        with (
            patch("project_setup.pr_project_sync.find_project", return_value={"id": "project-id"}),
            patch("project_setup.pr_project_sync.list_project_fields", return_value=[status_field]),
            patch("project_setup.pr_project_sync.list_project_content_items", return_value={"PR_node": "existing-item"}),
            patch("project_setup.pr_project_sync.add_issue_to_project") as add_item,
            patch("project_setup.pr_project_sync.update_single_select") as update_status,
        ):
            sync_pull_request_project_status(
                client,
                "owner/repo",
                self.context(),
                {"number": 73, "node_id": "PR_node"},
                6,
                "In review",
                {"syncProject": True, "projectStatusField": "Status"},
                owner="owner",
            )
        add_item.assert_not_called()
        update_status.assert_called_once()


class ProjectLookupTests(unittest.TestCase):
    def make_config(self) -> str:
        directory = Path(tempfile.mkdtemp())
        definition = directory / "project.json"
        definition.write_text(json.dumps({"name": "Project Delivery Board"}), encoding="utf-8")
        config = directory / "project_setup.json"
        config.write_text(json.dumps({"projectDefinitionFile": "project.json"}), encoding="utf-8")
        return str(config)

    def test_explicit_project_number_wins_without_remote_lookup(self):
        client = Mock(spec=GitHubClient)
        number, note = resolve_project_number(client, "owner/repo", 42, config_path=self.make_config())
        self.assertEqual(number, 42)
        self.assertEqual(note, "configured explicitly")
        client.assert_not_called()

    def test_unique_project_title_is_auto_discovered(self):
        client = Mock(spec=GitHubClient)
        with patch(
            "project_setup.project_lookup.list_owner_projects",
            return_value=[{"number": 6, "title": "Project Delivery Board"}],
        ):
            number, note = resolve_project_number(
                client,
                "owner/repo",
                None,
                config_path=self.make_config(),
                owner="owner",
            )
        self.assertEqual(number, 6)
        self.assertIn("auto-discovered", note)

    def test_missing_project_is_reported_without_guessing(self):
        client = Mock(spec=GitHubClient)
        with patch("project_setup.project_lookup.list_owner_projects", return_value=[]):
            number, note = resolve_project_number(
                client,
                "owner/repo",
                None,
                config_path=self.make_config(),
                owner="owner",
            )
        self.assertIsNone(number)
        self.assertIn("no Project v2 named", note)


if __name__ == "__main__":
    unittest.main()
