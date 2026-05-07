import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from governance_bootstrap.auto_label import infer_issue_labels
from governance_bootstrap.discovery import detect_auth_status, detect_project_matches
from governance_bootstrap.cli import main
from governance_bootstrap.issue_milestones import milestone_from_body, parent_issue_number_from_body
from governance_bootstrap.project import label_value


class GovernanceBootstrapTests(unittest.TestCase):
    def test_auto_label_infers_type_status_priority_and_test(self):
        issue = {
            "title": "US-01 | Example",
            "body": "Severity\nHigh\n\nTest type: smoke",
            "labels": [],
        }

        self.assertEqual(
            infer_issue_labels(issue),
            {"type:user-story", "status:backlog", "priority:high", "test:smoke"},
        )

    def test_issue_metadata_parsers_accept_generic_milestones(self):
        body = "Parent story: US-01 (#42)\n\n- Milestone: Release-1.0"

        self.assertEqual(milestone_from_body(body), "Release-1.0")
        self.assertEqual(parent_issue_number_from_body(body), 42)

    def test_label_value_reads_github_label_payloads(self):
        labels = [{"name": "type:task"}, {"name": "priority:critical"}]

        self.assertEqual(label_value(labels, "priority:"), "critical")

    def test_bootstrap_dry_run_does_not_require_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            labels = os.path.join(tmp, "labels.json")
            milestones = os.path.join(tmp, "milestones.json")
            project = os.path.join(tmp, "project.json")
            backlog = os.path.join(tmp, "backlog.json")
            config = os.path.join(tmp, "governance.bootstrap.json")

            with open(labels, "w", encoding="utf-8") as f:
                f.write('[{"name":"status:backlog","color":"C5DEF5","description":"Backlog"}]')
            with open(milestones, "w", encoding="utf-8") as f:
                f.write('[{"title":"M1","description":"Milestone"}]')
            with open(project, "w", encoding="utf-8") as f:
                f.write('{"name":"Board","fields":[]}')
            with open(backlog, "w", encoding="utf-8") as f:
                f.write('{"phases":[]}')
            with open(config, "w", encoding="utf-8") as f:
                f.write(
                    "{"
                    f'"labelsFile":"{labels}",'
                    f'"milestonesFile":"{milestones}",'
                    f'"projectDefinitionFile":"{project}",'
                    f'"backlogManifestFile":"{backlog}",'
                    '"defaults":{"dryRun":true,"runLabels":true,"runMilestones":true,'
                    '"runProjectCreation":true,"runIssueGeneration":true}'
                    "}"
                )

            with patch.dict(os.environ, {"GITHUB_TOKEN": "", "GH_TOKEN": ""}, clear=False):
                output = io.StringIO()
                with redirect_stdout(output):
                    result = main(["bootstrap", "--repo", "owner/repo", "--config", config, "--dry-run"])

        self.assertEqual(result, 0)
        self.assertIn("[DRY-RUN] Would sync 1 labels", output.getvalue())
        self.assertIn("Governance bootstrap finished.", output.getvalue())

    def test_discovery_prefers_env_token(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "token-from-env", "GH_TOKEN": ""}, clear=False):
            auth = detect_auth_status()

        self.assertTrue(auth.configured)
        self.assertEqual(auth.source, "environment")

    def test_get_token_falls_back_to_gh_auth(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "", "GH_TOKEN": ""}, clear=False), patch(
            "governance_bootstrap.github.shutil.which", return_value="/usr/bin/gh"
        ), patch("governance_bootstrap.github.subprocess.run") as run:
            run.return_value = SimpleNamespace(returncode=0, stdout="token-from-gh\n")

            from governance_bootstrap.github import get_token

            token = get_token()

        self.assertEqual(token, "token-from-gh")

    def test_discovery_detects_project_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "pyproject.toml"), "w", encoding="utf-8") as f:
                f.write("[project]\nname = 'demo'\n")
            with open(os.path.join(tmp, "package.json"), "w", encoding="utf-8") as f:
                f.write('{"name":"demo"}')

            matches = detect_project_matches(tmp)

        self.assertGreaterEqual(len(matches), 2)
        self.assertEqual(matches[0].project_type, "python")
        self.assertIn("pyproject.toml", matches[0].markers)

    def test_discover_auto_mode_reports_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = os.path.join(tmp, "governance.bootstrap.json")
            root = os.path.join(tmp, "repo")
            os.makedirs(root, exist_ok=True)
            with open(os.path.join(root, "go.mod"), "w", encoding="utf-8") as f:
                f.write("module example.com/demo\n")
            with open(config, "w", encoding="utf-8") as f:
                f.write(
                    "{"
                    '"secretName":"GOVERNANCE_PAT",'
                    '"defaults":{"dryRun":true,"runLabels":true,"runMilestones":true,'
                    '"runProjectCreation":false,"runIssueGeneration":true,"linkSubissues":true}'
                    "}"
                )

            with patch.dict(os.environ, {"GITHUB_TOKEN": "token-from-env", "GH_TOKEN": ""}, clear=False):
                output = io.StringIO()
                with redirect_stdout(output):
                    result = main(["discover", "--repo", "owner/repo", "--config", config, "--root", root, "--auto"])

        self.assertEqual(result, 0)
        text = output.getvalue()
        self.assertIn("Configured: yes (environment)", text)
        self.assertIn("Detected project type: go", text)
        self.assertIn("Recommended command", text)
        self.assertIn("python -m governance_bootstrap bootstrap", text)

    def test_discover_reports_missing_auth(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = os.path.join(tmp, "governance.bootstrap.json")
            with open(config, "w", encoding="utf-8") as f:
                f.write('{"secretName":"GOVERNANCE_PAT","defaults":{"dryRun":true}}')

            with patch.dict(os.environ, {"GITHUB_TOKEN": "", "GH_TOKEN": ""}, clear=False), patch(
                "governance_bootstrap.discovery.shutil.which", return_value=None
            ):
                output = io.StringIO()
                with redirect_stdout(output):
                    result = main(["discover", "--repo", "owner/repo", "--config", config, "--auto"])

        self.assertEqual(result, 1)
        self.assertIn("Configured: no (missing)", output.getvalue())
        self.assertIn("Expected workflow secret: GOVERNANCE_PAT", output.getvalue())


if __name__ == "__main__":
    unittest.main()
