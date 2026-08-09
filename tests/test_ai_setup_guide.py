from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from project_setup.installer import install_repository, template_files


ROOT = Path(__file__).resolve().parents[1]


class AISetupGuideTests(unittest.TestCase):
    def test_ai_guide_contains_required_safety_checkpoints(self):
        guide = (ROOT / "AI_SETUP_GUIDE.md").read_text(encoding="utf-8")
        required_contract = (
            "Inspect before asking",
            "Never request secrets in chat",
            "Re-read after user modifications",
            "Stop at decision checkpoints",
            "Issue generation is currently **not idempotent**",
            "Live checkpoint",
            "Verify applied results",
            "Do not use `LIVE=1` without a fresh, explicit live checkpoint",
        )
        for requirement in required_contract:
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, guide)

    def test_core_profile_distributes_ai_guide(self):
        destinations = {destination for _, destination in template_files(ROOT, "core")}
        self.assertIn("AI_SETUP_GUIDE.md", destinations)

    def test_installer_preserves_existing_target_ai_guide(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory)
            guide = target / "AI_SETUP_GUIDE.md"
            guide.write_text("target-specific AI instructions\n", encoding="utf-8")

            result = install_repository(target, source=ROOT, profile="core")

            self.assertEqual(guide.read_text(encoding="utf-8"), "target-specific AI instructions\n")
            self.assertIn("AI_SETUP_GUIDE.md", result.skipped)


if __name__ == "__main__":
    unittest.main()
