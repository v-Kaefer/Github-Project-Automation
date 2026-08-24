from __future__ import annotations

import unittest
from unittest.mock import Mock

from project_setup.github import GitHubClient
from project_setup.linked_branch import create_linked_branch, manually_linked_pr_numbers


class LinkedBranchTests(unittest.TestCase):
    def test_create_linked_branch_uses_issue_repository_name_and_base_oid(self):
        client = Mock(spec=GitHubClient)
        client.get_issue.return_value = {"number": 72, "node_id": "I_issue"}
        client.request_json.side_effect = [
            {"node_id": "R_repo"},
            {"commit": {"sha": "abc123"}},
        ]
        client.graphql.return_value = {
            "createLinkedBranch": {
                "issue": {"id": "I_issue", "number": 72},
                "linkedBranch": {"id": "LB_1", "ref": {"name": "feat/issue-72"}},
            }
        }

        result = create_linked_branch(
            client,
            "owner/repo",
            72,
            "feat/issue-72",
            base_ref="develop",
        )

        self.assertEqual(result["linkedBranch"]["ref"]["name"], "feat/issue-72")
        mutation, variables = client.graphql.call_args.args
        self.assertIn("createLinkedBranch", mutation)
        self.assertEqual(
            variables,
            {
                "issue": "I_issue",
                "repository": "R_repo",
                "name": "feat/issue-72",
                "oid": "abc123",
            },
        )
        self.assertIn("branches/develop", client.request_json.call_args_list[1].args[1])

    def test_dry_run_does_not_touch_github(self):
        client = Mock(spec=GitHubClient)
        result = create_linked_branch(
            client,
            "owner/repo",
            72,
            "fix/issue-72",
            base_ref="develop",
            dry_run=True,
        )
        self.assertEqual(result["linkedBranch"]["ref"]["name"], "fix/issue-72")
        client.get_issue.assert_not_called()
        client.request_json.assert_not_called()
        client.graphql.assert_not_called()

    def test_manual_development_query_returns_linked_pr_numbers(self):
        client = Mock(spec=GitHubClient)
        client.graphql.return_value = {
            "repository": {
                "issue": {
                    "closedByPullRequestsReferences": {
                        "nodes": [{"number": 81}, {"number": 82}]
                    }
                }
            }
        }
        self.assertEqual(manually_linked_pr_numbers(client, "owner/repo", 72), [81, 82])
        query, variables = client.graphql.call_args.args
        self.assertIn("userLinkedOnly:true", query)
        self.assertEqual(variables["number"], 72)


if __name__ == "__main__":
    unittest.main()
