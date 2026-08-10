from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from project_setup.github import GitHubClient
from project_setup.pr_autofill import apply_pr_autofill, rewrite_pr_body


ROOT = Path(__file__).resolve().parents[1]


class PrSyncAutofillTests(unittest.TestCase):
    def event(self, **pull_request_overrides):
        pull_request = {
            "number": 41,
            "body": "## Linked Issue\n- Closes #<issue-number>\n\n## Milestone\n- <milestone>\n\n## Summary\n- Keep me\n",
            "base": {"ref": "develop"},
            "head": {
                "ref": "feat/US-00-repository-automation",
                "repo": {"full_name": "owner/repo"},
            },
            "user": {"login": "alice"},
            "draft": False,
            "merged": False,
        }
        pull_request.update(pull_request_overrides)
        return {"action": "opened", "pull_request": pull_request}

    def test_rewrite_only_replaces_recoverable_sections(self):
        body = "## Linked Issue\n- old\n\n## Milestone\n- old\n\n## Summary\n- preserve this\n"
        updated, changed = rewrite_pr_body(body, 12, "M0")
        self.assertTrue(changed)
        self.assertIn("- Closes #12", updated)
        self.assertIn("## Milestone\n- M0", updated)
        self.assertIn("## Summary\n- preserve this", updated)

    def test_explicit_link_is_authoritative(self):
        client = Mock(spec=GitHubClient)
        event = self.event(body="## Linked Issue\n- Closes #99\n")
        result = apply_pr_autofill(client, "owner/repo", event)
        self.assertEqual(result, 0)
        client.get_issue.assert_not_called()
        client.paginated.assert_not_called()
        client.request_json.assert_not_called()

    def test_story_token_autofills_body_and_local_event_payload(self):
        client = Mock(spec=GitHubClient)
        client.paginated.return_value = [
            {
                "number": 12,
                "title": "US-00 | Configure repository automation",
                "state": "open",
                "milestone": {"title": "M0"},
            }
        ]
        event = self.event()

        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as handle:
            json.dump(event, handle)
            event_path = handle.name

        result = apply_pr_autofill(
            client,
            "owner/repo",
            event,
            event_path=event_path,
            backlog_file=str(ROOT / "config/stories/backlog-manifest.json"),
            config_file=str(ROOT / "project_setup.json"),
        )

        self.assertEqual(result, 0)
        client.request_json.assert_called_once()
        method, url, payload = client.request_json.call_args.args
        self.assertEqual(method, "PATCH")
        self.assertTrue(url.endswith("/pulls/41"))
        self.assertIn("Closes #12", payload["body"])
        self.assertIn("## Milestone\n- M0", payload["body"])

        persisted = json.loads(Path(event_path).read_text(encoding="utf-8"))
        self.assertIn("Closes #12", persisted["pull_request"]["body"])

    def test_promotion_pr_is_not_autofilled(self):
        client = Mock(spec=GitHubClient)
        event = self.event(
            base={"ref": "Q.A"},
            head={"ref": "develop", "repo": {"full_name": "owner/repo"}},
        )
        result = apply_pr_autofill(
            client,
            "owner/repo",
            event,
            config_file=str(ROOT / "project_setup.json"),
        )
        self.assertEqual(result, 0)
        client.get_issue.assert_not_called()
        client.paginated.assert_not_called()
        client.request_json.assert_not_called()

    def test_unresolvable_branch_does_not_invent_metadata(self):
        client = Mock(spec=GitHubClient)
        event = self.event(
            head={"ref": "feat/free-form-description", "repo": {"full_name": "owner/repo"}}
        )
        result = apply_pr_autofill(
            client,
            "owner/repo",
            event,
            backlog_file=str(ROOT / "config/stories/backlog-manifest.json"),
            config_file=str(ROOT / "project_setup.json"),
        )
        self.assertEqual(result, 0)
        client.request_json.assert_not_called()


class PrSyncAutofillWorkflowContractTests(unittest.TestCase):
    def test_autofill_runs_before_sync_in_same_workflow(self):
        text = (ROOT / ".github/workflows/pr-sync.yml").read_text(encoding="utf-8")
        autofill = "python -m project_setup.pr_autofill"
        sync = "python -m project_setup.pr_sync"
        self.assertIn(autofill, text)
        self.assertIn(sync, text)
        self.assertLess(text.index(autofill), text.index(sync))
        self.assertIn("pull-requests: write", text)


if __name__ == "__main__":
    unittest.main()
