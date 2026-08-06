from __future__ import annotations

import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from project_setup.auto_label import infer_issue_labels
from project_setup.cli import main
from project_setup.discovery import build_apply_command, detect_project_matches
from project_setup.github import GitHubClient, get_token, load_env_file, require_project_client
from project_setup.installer import install_repository
from project_setup.issue_milestones import milestone_from_body, parent_issue_number_from_body
from project_setup.issues import load_backlog
from project_setup.labels import load_labels, sync_labels
from project_setup.milestones import load_milestones, sync_milestones
from project_setup.pr_validation import validate_pull_request
from project_setup.project import label_value


ROOT = Path(__file__).resolve().parents[1]


class ProjectSetupTests(unittest.TestCase):
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

    def test_manifest_loaders_validate_required_fields(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            labels = root / "labels.json"
            milestones = root / "milestones.json"
            backlog = root / "backlog.json"
            labels.write_text('[{"name":"missing-color"}]', encoding="utf-8")
            milestones.write_text('[{"description":"missing-title"}]', encoding="utf-8")
            backlog.write_text('{"stories":[]}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_labels(str(labels))
            with self.assertRaises(ValueError):
                load_milestones(str(milestones))
            with self.assertRaises(ValueError):
                load_backlog(str(backlog))

    def test_issue_metadata_parsers_accept_generic_milestones(self):
        body = "Parent story: US-01 (#42)\n\n- Milestone: Release-1.0"
        self.assertEqual(milestone_from_body(body), "Release-1.0")
        self.assertEqual(parent_issue_number_from_body(body), 42)

    def test_label_value_reads_github_label_payloads(self):
        labels = [{"name": "type:task"}, {"name": "priority:critical"}]
        self.assertEqual(label_value(labels, "priority:"), "critical")
        self.assertIsNone(label_value(labels, "status:"))

    def test_sync_dry_runs_print_planned_resources(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            labels = root / "labels.json"
            milestones = root / "milestones.json"
            labels.write_text('[{"name":"status:backlog","color":"C5DEF5"}]', encoding="utf-8")
            milestones.write_text('[{"title":"M1","description":"Delivery"}]', encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                sync_labels(GitHubClient(""), "owner/repository", str(labels), dry_run=True)
                sync_milestones(GitHubClient(""), "owner/repository", str(milestones), dry_run=True)
        text = output.getvalue()
        self.assertIn("[DRY-RUN] Would sync 1 labels", text)
        self.assertIn("[DRY-RUN] Would sync 1 milestones", text)

    def test_apply_dry_run_does_not_require_token(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "labels.json").write_text('[{"name":"status:backlog","color":"C5DEF5"}]', encoding="utf-8")
            (root / "milestones.json").write_text('[{"title":"M1"}]', encoding="utf-8")
            (root / "project.json").write_text('{"name":"Board","fields":[]}', encoding="utf-8")
            (root / "backlog.json").write_text('{"phases":[]}', encoding="utf-8")
            config = root / "project_setup.json"
            config.write_text(
                json.dumps(
                    {
                        "labelsFile": str(root / "labels.json"),
                        "milestonesFile": str(root / "milestones.json"),
                        "projectDefinitionFile": str(root / "project.json"),
                        "backlogManifestFile": str(root / "backlog.json"),
                        "defaults": {
                            "dryRun": True,
                            "runLabels": True,
                            "runMilestones": True,
                            "runProjectCreation": True,
                            "runIssueGeneration": True,
                        },
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"GITHUB_TOKEN": "", "GH_TOKEN": "", "PROJECT_SETUP_PAT": ""}, clear=False), patch(
                "project_setup.github.shutil.which", return_value=None
            ):
                output = io.StringIO()
                with redirect_stdout(output):
                    result = main(["apply", "--repo", "owner/repository", "--config", str(config), "--dry-run"])
        self.assertEqual(result, 0)
        self.assertIn("[DRY-RUN] Would sync 1 labels", output.getvalue())
        self.assertIn("Project setup finished.", output.getvalue())

    def test_env_file_loads_values_without_overriding_process_environment(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            env_file = Path(temporary_directory) / ".env"
            env_file.write_text(
                "GITHUB_REPOSITORY=owner/from-file\nPROJECT_SETUP_PAT=token-from-file\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/from-process"}, clear=True):
                loaded = load_env_file(env_file)
                self.assertEqual(loaded, env_file.resolve())
                self.assertEqual(os.environ["GITHUB_REPOSITORY"], "owner/from-process")
                self.assertEqual(os.environ["PROJECT_SETUP_PAT"], "token-from-file")

    def test_invalid_env_file_reports_line_number(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            env_file = Path(temporary_directory) / ".env"
            env_file.write_text("THIS IS NOT VALID\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "line 1"):
                load_env_file(env_file)

    def test_project_client_error_explains_pat_setup(self):
        with patch.dict(os.environ, {"PROJECT_SETUP_PAT": "", "GITHUB_TOKEN": "token"}, clear=False):
            with self.assertRaises(SystemExit) as context:
                require_project_client()
        message = str(context.exception)
        self.assertIn("PROJECT_SETUP_PAT", message)
        self.assertIn("Tokens (classic)", message)
        self.assertIn("repo", message)
        self.assertIn("project", message)
        self.assertIn(".env", message)

    def test_installer_copies_core_files_and_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory)
            existing = target / ".github" / "pull_request_template.md"
            existing.parent.mkdir(parents=True)
            existing.write_text("custom template", encoding="utf-8")
            result = install_repository(target, source=ROOT, profile="core")
            self.assertEqual(existing.read_text(encoding="utf-8"), "custom template")
            self.assertIn(".github/pull_request_template.md", result.skipped)
            self.assertTrue((target / "project_setup" / "cli.py").is_file())
            self.assertTrue((target / "project_setup" / "discovery.py").is_file())
            self.assertTrue((target / ".github" / "workflows" / "project-setup.yml").is_file())
            self.assertTrue((target / ".env.example").is_file())
            self.assertTrue((target / "Makefile").is_file())
            self.assertFalse((target / ".github" / "workflows" / "godot-smoke.yml").exists())

    def test_godot_profile_copies_optional_workflow(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory)
            install_repository(target, source=ROOT, profile="godot")
            self.assertTrue((target / ".github" / "workflows" / "godot-smoke.yml").is_file())

    def test_pull_request_validation_accepts_complete_template(self):
        body = """## Linked Issue
- Closes #123

## Milestone
- M1

## Summary
- Add repository setup.

## How to test
- Run make check.

## Known risks
- None identified.

## DoD checklist
- [x] Checks passed.
"""
        self.assertEqual(validate_pull_request("feat/project-setup", body, "develop"), [])

    def test_discovery_detects_multiple_project_types(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            (root / "package.json").write_text('{"name":"demo"}', encoding="utf-8")
            matches = detect_project_matches(root)
        self.assertEqual([match.project_type for match in matches[:2]], ["python", "node"])

    def test_discovery_builds_project_setup_command(self):
        command = build_apply_command(
            "owner/repository",
            "project_setup.json",
            True,
            True,
            True,
            False,
            False,
            True,
        )
        self.assertIn("python -m project_setup apply", command)
        self.assertIn("--dry-run", command)
        self.assertIn("--skip-project-creation", command)

    def test_get_token_falls_back_to_gh_auth(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "", "GH_TOKEN": "", "PROJECT_SETUP_PAT": ""}, clear=False), patch(
            "project_setup.github.shutil.which", return_value="/usr/bin/gh"
        ), patch("project_setup.github.subprocess.run") as run:
            run.return_value = SimpleNamespace(returncode=0, stdout="token-from-gh\n")
            token = get_token()
        self.assertEqual(token, "token-from-gh")

    def test_discover_auto_mode_reports_summary(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            target = root / "repository"
            target.mkdir()
            (target / "go.mod").write_text("module example.com/demo\n", encoding="utf-8")
            config = root / "project_setup.json"
            config.write_text(
                json.dumps(
                    {
                        "labelsFile": "labels.json",
                        "milestonesFile": "milestones.json",
                        "projectDefinitionFile": "project.json",
                        "backlogManifestFile": "backlog.json",
                        "secretName": "PROJECT_SETUP_PAT",
                        "defaults": {"dryRun": True, "runLabels": True, "runMilestones": True},
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"PROJECT_SETUP_PAT": "token", "GITHUB_TOKEN": "", "GH_TOKEN": ""}, clear=False):
                output = io.StringIO()
                with redirect_stdout(output):
                    result = main(
                        [
                            "discover",
                            "--repo",
                            "owner/repository",
                            "--config",
                            str(config),
                            "--root",
                            str(target),
                            "--auto",
                        ]
                    )
        self.assertEqual(result, 0)
        text = output.getvalue()
        self.assertIn("Configured: yes (environment)", text)
        self.assertIn("Detected project type: go", text)
        self.assertIn("python -m project_setup apply", text)


if __name__ == "__main__":
    unittest.main()
