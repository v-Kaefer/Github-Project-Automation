import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from governance_bootstrap.auto_label import infer_issue_labels
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


if __name__ == "__main__":
    unittest.main()
