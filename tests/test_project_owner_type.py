from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from project_setup.cli import build_parser
from project_setup.project import find_project, normalize_owner_type, owner_node, resolve_owner_type


class FakeClient:
    def __init__(self, github_type: str = "User") -> None:
        self.github_type = github_type
        self.request_calls: list[tuple[str, str]] = []
        self.graphql_calls: list[tuple[str, dict]] = []

    def request_json(self, method: str, url: str, **_: object) -> dict:
        self.request_calls.append((method, url))
        return {"type": self.github_type}

    def graphql(self, query: str, variables: dict) -> dict:
        self.graphql_calls.append((query, variables))
        if "projectV2" in query:
            owner_type = "organization" if "organization(login:" in query else "user"
            return {
                owner_type: {
                    "projectV2": {
                        "id": "PVT_test",
                        "title": "Board",
                        "url": "https://example.invalid/project",
                    }
                }
            }
        owner_type = "organization" if "organization(login:" in query else "user"
        return {owner_type: {"id": "OWNER_test"}}


class ProjectOwnerTypeTests(unittest.TestCase):
    def test_normalizes_documented_and_friendly_values(self) -> None:
        self.assertIsNone(normalize_owner_type(None))
        self.assertIsNone(normalize_owner_type(""))
        self.assertIsNone(normalize_owner_type("   "))
        self.assertEqual(normalize_owner_type("user"), "user")
        self.assertEqual(normalize_owner_type("organization"), "organization")
        self.assertEqual(normalize_owner_type("org"), "organization")
        self.assertEqual(normalize_owner_type("company"), "organization")
        with self.assertRaisesRegex(ValueError, "user.*organization"):
            normalize_owner_type("team")

    def test_explicit_user_queries_only_user_namespace(self) -> None:
        client = FakeClient()
        project = find_project(client, "person", 1, owner_type="user")
        self.assertEqual(project["title"], "Board")
        self.assertEqual(client.request_calls, [])
        query = client.graphql_calls[-1][0]
        self.assertIn("user(login:", query)
        self.assertNotIn("organization(login:", query)

    def test_explicit_organization_queries_only_organization_namespace(self) -> None:
        client = FakeClient()
        project = find_project(client, "company", 1, owner_type="organization")
        self.assertEqual(project["title"], "Board")
        self.assertEqual(client.request_calls, [])
        query = client.graphql_calls[-1][0]
        self.assertIn("organization(login:", query)
        self.assertNotIn("user(login:", query)

    def test_auto_detects_user_before_graphql_lookup(self) -> None:
        client = FakeClient("User")
        with patch.dict(os.environ, {"PROJECT_SETUP_OWNER_TYPE": ""}, clear=False):
            self.assertEqual(resolve_owner_type(client, "person"), "user")
            node_id = owner_node(client, "person")
        self.assertEqual(node_id, "OWNER_test")
        self.assertTrue(client.request_calls)
        self.assertIn("user(login:", client.graphql_calls[-1][0])

    def test_auto_detects_organization_before_graphql_lookup(self) -> None:
        client = FakeClient("Organization")
        with patch.dict(os.environ, {"PROJECT_SETUP_OWNER_TYPE": ""}, clear=False):
            self.assertEqual(resolve_owner_type(client, "company"), "organization")
            node_id = owner_node(client, "company")
        self.assertEqual(node_id, "OWNER_test")
        self.assertTrue(client.request_calls)
        self.assertIn("organization(login:", client.graphql_calls[-1][0])

    def test_environment_selection_takes_precedence_over_auto_detection(self) -> None:
        client = FakeClient("Organization")
        with patch.dict(os.environ, {"PROJECT_SETUP_OWNER_TYPE": "user"}, clear=False):
            self.assertEqual(resolve_owner_type(client, "person"), "user")
        self.assertEqual(client.request_calls, [])

    def test_cli_accepts_owner_type_for_project_create(self) -> None:
        args = build_parser().parse_args(
            ["project", "create", "--repo", "company/repository", "--owner-type", "organization"]
        )
        self.assertEqual(args.owner_type, "organization")

    def test_cli_accepts_owner_type_for_project_sync(self) -> None:
        args = build_parser().parse_args(
            [
                "project",
                "sync",
                "--repo",
                "person/repository",
                "--project-number",
                "3",
                "--owner-type",
                "user",
            ]
        )
        self.assertEqual(args.owner_type, "user")

    def test_cli_accepts_owner_type_for_apply(self) -> None:
        args = build_parser().parse_args(["apply", "--owner-type", "organization"])
        self.assertEqual(args.owner_type, "organization")


if __name__ == "__main__":
    unittest.main()
