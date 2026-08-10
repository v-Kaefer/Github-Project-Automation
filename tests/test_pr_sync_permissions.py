from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PrSyncPermissionContractTests(unittest.TestCase):
    def test_pr_sync_can_mutate_pull_requests(self):
        workflow = (ROOT / ".github/workflows/pr-sync.yml").read_text(encoding="utf-8")

        self.assertIn("permissions:", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("issues: write", workflow)
        self.assertIn("pull-requests: write", workflow)


if __name__ == "__main__":
    unittest.main()
