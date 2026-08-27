from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from project_setup.rulesets import apply_rulesets, plan_rulesets


class _Client:
    def __init__(self):
        self.requests: list[tuple[str, str, object]] = []
        self.rulesets: list[dict] = []

    def request_json(self, method, url, payload=None):
        self.requests.append((method, url, payload))
        if url.endswith("/teams/reviewers"):
            return {"id": 42}
        if url.endswith("/rulesets") and method == "GET":
            return self.rulesets
        if "/rulesets/" in url and method == "GET":
            return self.rulesets[0]
        if method == "POST":
            return {}
        if method == "PUT":
            return {}
        raise AssertionError((method, url, payload))


class RulesetTests(unittest.TestCase):
    def manifest(self) -> tuple[tempfile.TemporaryDirectory, Path]:
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "rulesets.json"
        path.write_text(json.dumps({"rulesets": [{
            "name": "GPA: main", "refName": {"include": ["refs/heads/main"]},
            "rules": [{"type": "non_fast_forward"}],
            "bypassActors": [{"type": "team", "slug": "reviewers"}],
        }]}), encoding="utf-8")
        return directory, path

    def test_plan_is_read_only_and_resolves_team_slug(self):
        directory, path = self.manifest()
        self.addCleanup(directory.cleanup)
        client = _Client()
        plan_id, actions = plan_rulesets(client, "owner/repo", str(path))
        self.assertEqual(len(plan_id), 12)
        self.assertEqual(actions[0][0], "create")
        self.assertFalse(any(method in {"POST", "PUT"} for method, _, _ in client.requests))

    def test_apply_requires_matching_plan_id_and_never_deletes(self):
        directory, path = self.manifest()
        self.addCleanup(directory.cleanup)
        client = _Client()
        plan_id, _ = plan_rulesets(client, "owner/repo", str(path))
        apply_rulesets(client, "owner/repo", str(path), plan_id)
        self.assertTrue(any(method == "POST" for method, _, _ in client.requests))
        self.assertFalse(any(method == "DELETE" for method, _, _ in client.requests))

    def test_apply_rejects_stale_or_missing_confirmation(self):
        directory, path = self.manifest()
        self.addCleanup(directory.cleanup)
        with self.assertRaisesRegex(ValueError, "require --confirm"):
            apply_rulesets(_Client(), "owner/repo", str(path), "wrong")


if __name__ == "__main__":
    unittest.main()
