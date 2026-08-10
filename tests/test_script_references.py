from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_REFERENCES = {
    "scripts/validation/repo_quality.py": (
        "Makefile",
    ),
    "scripts/validation/validate_pr_body.py": (
        ".github/workflows/pr-metadata.yml",
    ),
}
INSTALLER = "project_setup/installer.py"
SCRIPT_SUFFIXES = {".py", ".sh", ".ps1"}


class ScriptReferenceTests(unittest.TestCase):
    def test_every_validation_script_has_a_registered_entry_point(self):
        discovered = {
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "scripts").rglob("*")
            if path.is_file() and path.suffix.lower() in SCRIPT_SUFFIXES
        }
        self.assertEqual(discovered, set(SCRIPT_REFERENCES))

    def test_script_callers_and_installer_reference_current_paths(self):
        installer_text = (ROOT / INSTALLER).read_text(encoding="utf-8")
        for script_path, owners in SCRIPT_REFERENCES.items():
            with self.subTest(script=script_path):
                self.assertTrue((ROOT / script_path).is_file())
                self.assertIn(script_path, installer_text)
                for owner in owners:
                    owner_text = (ROOT / owner).read_text(encoding="utf-8")
                    self.assertIn(script_path, owner_text)

    def test_validation_scripts_use_only_the_project_setup_namespace(self):
        legacy_names = (
            "governance" + "_bootstrap",
            "governance" + "_bootstarp",
            "governance" + ".bootstrap.json",
            "governance" + "-bootstrap",
        )
        for script_path in SCRIPT_REFERENCES:
            text = (ROOT / script_path).read_text(encoding="utf-8")
            for legacy_name in legacy_names:
                with self.subTest(script=script_path, legacy_name=legacy_name):
                    self.assertNotIn(legacy_name, text)


if __name__ == "__main__":
    unittest.main()
