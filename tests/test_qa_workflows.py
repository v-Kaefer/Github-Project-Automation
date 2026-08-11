from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class QaWorkflowContractTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_qa_source_requires_develop(self):
        text = self.read(".github/workflows/qa-source-branch.yml")
        self.assertIn("pull_request_target:", text)
        self.assertNotIn("actions/checkout", text)
        self.assertIn('branches: ["Q.A"]', text)
        self.assertIn('HEAD_REF" != "develop', text)
        self.assertIn("name: validate-qa-source", text)

    def test_main_source_requires_qa(self):
        text = self.read(".github/workflows/main-source-branch.yml")
        self.assertIn("pull_request_target:", text)
        self.assertNotIn("actions/checkout", text)
        self.assertIn('HEAD_REF" != "Q.A', text)
        self.assertNotIn('HEAD_REF" != "develop', text)
        self.assertIn("name: validate-main-source", text)

    def test_qa_validation_matrix_covers_supported_platforms_and_versions(self):
        text = self.read(".github/workflows/qa-validation.yml")
        for expected in (
            "ubuntu-latest",
            "windows-latest",
            "macos-latest",
            'python: "3.11"',
            'python: "3.12"',
            'python: "3.13"',
            'python: "3.14"',
            "tests/qa",
            "make doctor",
            "python -m build",
            "name: qa-gate",
            "needs: [repository-quality, compatibility, package-artifact]",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_live_workflow_uses_protected_environment_without_deployment_records(self):
        text = self.read(".github/workflows/qa-live.yml")
        self.assertIn("environment:", text)
        self.assertIn("name: qa", text)
        self.assertIn("deployment: false", text)
        self.assertIn("name: qa-live-gate", text)
        self.assertIn("vars.QA_REPOSITORY", text)
        self.assertIn("secrets.QA_PROJECT_SETUP_PAT", text)
        self.assertIn("tests/qa/live_sandbox.py", text)
        self.assertIn("tests/qa/live_pr_sync.py", text)
        self.assertIn("QA_REPOSITORY must not be the source repository", text)

    def test_live_qa_is_reusable_only_and_guardrail_gated(self):
        live = self.read(".github/workflows/qa-live.yml")
        metadata = self.read(".github/workflows/pr-metadata.yml")

        self.assertIn("workflow_call:", live)
        self.assertNotIn("push:", live)
        self.assertNotIn("workflow_dispatch:", live)
        self.assertIn("group: qa-live-sandbox", live)
        self.assertIn("cancel-in-progress: true", live)
        self.assertIn("ref: ${{ inputs.checkout_ref }}", live)

        self.assertIn("pull_request_target:", metadata)
        self.assertIn("needs: validate-pr", metadata)
        self.assertIn("needs.validate-pr.result == 'success'", metadata)
        self.assertIn("github.event.pull_request.head.ref == 'Q.A'", metadata)
        self.assertIn("github.event.pull_request.base.ref == 'main'", metadata)
        self.assertIn("uses: ./.github/workflows/qa-live.yml", metadata)

    def test_live_sandbox_prunes_only_prefixed_stale_resources(self):
        text = self.read("tests/qa/live_sandbox.py")
        for expected in (
            'QA_LABEL_PREFIX = "qa:run-"',
            'QA_MILESTONE_PREFIX = "QA-"',
            'QA_PROJECT_PREFIX = "QA validation "',
            "def cleanup_stale_resources(",
            "title.startswith(QA_PROJECT_PREFIX)",
            "title.startswith(QA_MILESTONE_PREFIX)",
            "name.startswith(QA_LABEL_PREFIX)",
            "Q.A stale cleanup failed before creating new resources",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_live_pr_sync_verifies_structured_metadata_on_non_default_base(self):
        text = self.read("tests/qa/live_pr_sync.py")
        workflow = self.read(".github/workflows/qa-live.yml")

        for expected in (
            "DEFAULT_SYNC_CONFIG",
            "apply_pr_sync(",
            'config["labelPrefixes"] = ["type:", "priority:", "test:"]',
            "pr_labels=passed",
            "pr_milestone=passed",
            "pr_assignees=passed",
            "project_v2_task_status=passed",
            "non_default_base_branch=passed",
            "pr_sync_structured_metadata=passed",
            "pr_sync_cleanup=passed",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

        self.assertIn("python tests/qa/live_pr_sync.py", workflow)
        self.assertIn("PROJECT_SETUP_PAT: ${{ secrets.QA_PROJECT_SETUP_PAT }}", workflow)

    def test_old_qa_deployment_history_is_cleaned_after_live_qa(self):
        metadata = self.read(".github/workflows/pr-metadata.yml")
        cleanup = self.read("tests/qa/cleanup_deployments.py")

        for expected in (
            "qa-deployment-cleanup:",
            "needs: qa-live",
            "always()",
            "deployments: write",
            "tests/qa/cleanup_deployments.py",
            "--environment qa",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, metadata)

        self.assertIn("/deployments?environment=", cleanup)
        self.assertIn('"state": "inactive"', cleanup)
        self.assertIn('"DELETE"', cleanup)
        self.assertIn("--environment must be exactly 'qa'", cleanup)

    def test_issue_generation_is_manual_and_requires_explicit_confirmation(self):
        text = self.read(".github/workflows/qa-issue-generation.yml")
        self.assertIn("workflow_dispatch", text)
        self.assertNotIn("push:", text)
        self.assertIn("RUN_NON_IDEMPOTENT_TEST", text)
        self.assertIn("tests/qa/live_issue_generation.py", text)


if __name__ == "__main__":
    unittest.main()
