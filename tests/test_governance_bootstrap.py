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
from governance_bootstrap.issues import load_backlog
from governance_bootstrap.labels import load_labels
from governance_bootstrap.milestones import load_milestones
from governance_bootstrap.project import label_value


class GovernanceBootstrapTests(unittest.TestCase):
    # ------------------------------------------------------------------ #
    # Label helpers                                                         #
    # ------------------------------------------------------------------ #

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

    def test_label_value_reads_github_label_payloads(self):
        labels = [{"name": "type:task"}, {"name": "priority:critical"}]

        self.assertEqual(label_value(labels, "priority:"), "critical")

    def test_label_value_returns_none_when_no_match(self):
        labels = [{"name": "type:task"}]

        self.assertIsNone(label_value(labels, "priority:"))

    # ------------------------------------------------------------------ #
    # Manifest loaders — validation errors                                 #
    # ------------------------------------------------------------------ #

    def test_load_backlog_raises_when_milestones_key_missing(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write('{"version": "1.0.0", "stories": []}')
            path = f.name
        try:
            with self.assertRaises(ValueError):
                load_backlog(path)
        finally:
            os.unlink(path)

    def test_load_labels_raises_when_color_missing(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write('[{"name": "status:backlog"}]')
            path = f.name
        try:
            with self.assertRaises(ValueError):
                load_labels(path)
        finally:
            os.unlink(path)

    def test_load_milestones_raises_when_title_missing(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write('[{"description": "no title here"}]')
            path = f.name
        try:
            with self.assertRaises(ValueError):
                load_milestones(path)
        finally:
            os.unlink(path)

    # ------------------------------------------------------------------ #
    # Issue metadata parsers                                               #
    # ------------------------------------------------------------------ #

    def test_issue_metadata_parsers_accept_generic_milestones(self):
        body = "Parent story: US-01 (#42)\n\n- Milestone: Release-1.0"

        self.assertEqual(milestone_from_body(body), "Release-1.0")
        self.assertEqual(parent_issue_number_from_body(body), 42)

    # ------------------------------------------------------------------ #
    # Sync dry-run output                                                  #
    # ------------------------------------------------------------------ #

    def test_sync_labels_dry_run_prints_label_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            labels_file = os.path.join(tmp, "labels.json")
            with open(labels_file, "w", encoding="utf-8") as f:
                f.write('[{"name":"status:backlog","color":"C5DEF5","description":"Backlog"}]')

            from governance_bootstrap.labels import sync_labels
            from governance_bootstrap.github import GitHubClient

            output = io.StringIO()
            with redirect_stdout(output):
                sync_labels(GitHubClient(""), "owner/repo", labels_file, dry_run=True)

        text = output.getvalue()
        self.assertIn("[DRY-RUN] Would sync 1 labels", text)
        self.assertIn("status:backlog", text)

    def test_sync_milestones_dry_run_prints_milestone_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            milestones_file = os.path.join(tmp, "milestones.json")
            with open(milestones_file, "w", encoding="utf-8") as f:
                f.write('[{"title":"M0","description":"Setup","due_on":"2026-01-31T00:00:00Z"}]')

            from governance_bootstrap.milestones import sync_milestones
            from governance_bootstrap.github import GitHubClient

            output = io.StringIO()
            with redirect_stdout(output):
                sync_milestones(GitHubClient(""), "owner/repo", milestones_file, dry_run=True)

        text = output.getvalue()
        self.assertIn("[DRY-RUN] Would sync 1 milestones", text)
        self.assertIn("M0", text)

    # ------------------------------------------------------------------ #
    # Issue generation dry run                                             #
    # ------------------------------------------------------------------ #

    def test_issue_generation_dry_run_prints_stories_and_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            labels = os.path.join(tmp, "labels.json")
            milestones = os.path.join(tmp, "milestones.json")
            project = os.path.join(tmp, "project.json")
            backlog = os.path.join(tmp, "backlog.json")
            config = os.path.join(tmp, "governance.bootstrap.json")

            with open(labels, "w", encoding="utf-8") as f:
                f.write('[{"name":"status:backlog","color":"C5DEF5","description":"Backlog"},'
                        '{"name":"type:user-story","color":"1D76DB","description":"Story"},'
                        '{"name":"type:task","color":"0E8A16","description":"Task"}]')
            with open(milestones, "w", encoding="utf-8") as f:
                f.write('[{"title":"M0","description":"Setup"}]')
            with open(project, "w", encoding="utf-8") as f:
                f.write('{"name":"Board","fields":[]}')
            with open(backlog, "w", encoding="utf-8") as f:
                f.write(
                    '{"milestones":[{"milestone":"M0","stories":[{'
                    '"storyId":"US-00","title":"US-00 | Setup",'
                    '"labels":["type:user-story"],"body":"As a team...",'
                    '"tasks":["T-00.1 | Create milestones"]'
                    '}]}]}'
                )
            with open(config, "w", encoding="utf-8") as f:
                f.write(
                    "{"
                    f'"labelsFile":"{labels}",'
                    f'"milestonesFile":"{milestones}",'
                    f'"projectDefinitionFile":"{project}",'
                    f'"backlogManifestFile":"{backlog}",'
                    '"defaults":{"dryRun":true,"runLabels":false,"runMilestones":false,'
                    '"runProjectCreation":false,"runIssueGeneration":true}'
                    "}"
                )

            with patch.dict(os.environ, {"GITHUB_TOKEN": "", "GH_TOKEN": ""}, clear=False):
                output = io.StringIO()
                with redirect_stdout(output):
                    result = main(["bootstrap", "--repo", "owner/repo", "--config", config, "--dry-run"])

        self.assertEqual(result, 0)
        text = output.getvalue()
        self.assertIn("[DRY-RUN] Story: US-00 | Setup", text)
        self.assertIn("[DRY-RUN]   Task: T-00.1 | Create milestones", text)

    # ------------------------------------------------------------------ #
    # Full bootstrap dry run                                               #
    # ------------------------------------------------------------------ #

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
                f.write('{"milestones":[]}')
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

    # ------------------------------------------------------------------ #
    # Auth detection                                                       #
    # ------------------------------------------------------------------ #

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

    # ------------------------------------------------------------------ #
    # Discovery / project detection                                        #
    # ------------------------------------------------------------------ #

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
                    '"workflowVar":"GOVERNANCE_PAT",'
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
                f.write('{"workflowVar":"GOVERNANCE_PAT","defaults":{"dryRun":true}}')

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
