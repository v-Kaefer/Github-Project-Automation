from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class QaWorkflowContractTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_qa_source_requires_develop(self):
        text = self.read(".github/workflows/qa-source-branch.yml")
        self.assertIn('branches: ["Q.A"]', text)
        self.assertIn('HEAD_REF" != "develop', text)
        self.assertIn("name: validate-qa-source", text)

    def test_main_source_requires_qa(self):
        text = self.read(".github/workflows/main-source-branch.yml")
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

    def test_live_workflow_uses_protected_environment_and_dedicated_credentials(self):
        text = self.read(".github/workflows/qa-live.yml")
        self.assertIn("environment: qa", text)
        self.assertIn("name: qa-live-gate", text)
        self.assertIn("vars.QA_REPOSITORY", text)
        self.assertIn("secrets.QA_PROJECT_SETUP_PAT", text)
        self.assertIn("tests/qa/live_sandbox.py", text)
        self.assertIn("QA_REPOSITORY must not be the source repository", text)

    def test_issue_generation_is_manual_and_requires_explicit_confirmation(self):
        text = self.read(".github/workflows/qa-issue-generation.yml")
        self.assertIn("workflow_dispatch", text)
        self.assertNotIn("push:", text)
        self.assertIn("RUN_NON_IDEMPOTENT_TEST", text)
        self.assertIn("tests/qa/live_issue_generation.py", text)


if __name__ == "__main__":
    unittest.main()
