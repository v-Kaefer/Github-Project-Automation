from __future__ import annotations

import unittest

from project_setup.pr_validation import validate_branch


class BranchPromotionTests(unittest.TestCase):
    def test_develop_can_promote_to_qa(self):
        self.assertEqual(validate_branch("develop", "Q.A"), [])

    def test_qa_can_promote_to_main(self):
        self.assertEqual(validate_branch("Q.A", "main"), [])

    def test_develop_cannot_skip_qa_and_promote_to_main(self):
        findings = validate_branch("develop", "main")
        self.assertEqual(len(findings), 1)
        self.assertIn("develop -> Q.A -> main", findings[0].fix)

    def test_qa_is_not_a_generic_implementation_branch(self):
        findings = validate_branch("Q.A", "develop")
        self.assertEqual(len(findings), 1)

    def test_prefixed_implementation_branch_remains_valid_for_develop(self):
        self.assertEqual(validate_branch("ci/qa-validation-suite", "develop"), [])


if __name__ == "__main__":
    unittest.main()
