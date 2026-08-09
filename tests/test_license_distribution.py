from __future__ import annotations

from pathlib import Path
import tempfile
import tomllib
import unittest

from project_setup.installer import install_repository, template_files


ROOT = Path(__file__).resolve().parents[1]


class LicenseDistributionTests(unittest.TestCase):
    def test_repository_uses_apache_license_and_notice(self):
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        notice_text = (ROOT / "NOTICE").read_text(encoding="utf-8")
        self.assertIn("Apache License", license_text)
        self.assertIn("Version 2.0", license_text)
        self.assertIn("v-Kaefer", notice_text)
        self.assertIn("created and originally developed", notice_text)

    def test_pyproject_declares_apache_classifier(self):
        with (ROOT / "pyproject.toml").open("rb") as file:
            pyproject = tomllib.load(file)
        classifiers = pyproject["project"]["classifiers"]
        self.assertIn("License :: OSI Approved :: Apache Software License", classifiers)

    def test_installer_maps_license_and_notice_without_replacing_target_license(self):
        mappings = dict(template_files(ROOT, "core"))
        self.assertEqual(mappings["LICENSE"], "licenses/project_setup/LICENSE")
        self.assertEqual(mappings["NOTICE"], "licenses/project_setup/NOTICE")

        with tempfile.TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory)
            target_license = target / "LICENSE"
            target_license.write_text("Target project's own license\n", encoding="utf-8")

            install_repository(target, source=ROOT, profile="core")

            self.assertEqual(target_license.read_text(encoding="utf-8"), "Target project's own license\n")
            self.assertTrue((target / "licenses" / "project_setup" / "LICENSE").is_file())
            self.assertTrue((target / "licenses" / "project_setup" / "NOTICE").is_file())
            self.assertIn(
                "v-Kaefer",
                (target / "licenses" / "project_setup" / "NOTICE").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
