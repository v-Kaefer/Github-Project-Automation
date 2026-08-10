from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MAKE = shutil.which("make")


@unittest.skipUnless(MAKE, "GNU Make is not available on PATH")
class MakefileEnvironmentDefaultTests(unittest.TestCase):
    def _base_environment(self, env_file: Path) -> dict[str, str]:
        environment = os.environ.copy()
        for name in (
            "PROJECT_SETUP_TARGET",
            "GITHUB_REPOSITORY",
            "PROJECT_SETUP_CONFIG",
            "PROJECT_SETUP_PROJECT_NUMBER",
            "PROJECT_SETUP_OWNER_TYPE",
        ):
            environment.pop(name, None)
        environment["PROJECT_SETUP_ENV_FILE"] = str(env_file)
        return environment

    def test_help_resolves_make_defaults_from_env_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            env_file = Path(temporary_directory) / ".env"
            env_file.write_text(
                "PROJECT_SETUP_TARGET=../configured-target\n"
                "GITHUB_REPOSITORY=owner/configured-repository\n"
                "PROJECT_SETUP_CONFIG=custom/project_setup.json\n"
                "PROJECT_SETUP_PROJECT_NUMBER=17\n"
                "PROJECT_SETUP_OWNER_TYPE=organization\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [MAKE, "--no-print-directory", "help"],
                cwd=ROOT,
                env=self._base_environment(env_file),
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PROJECT_SETUP_TARGET=../configured-target", result.stdout)
        self.assertIn("GITHUB_REPOSITORY=owner/configured-repository", result.stdout)
        self.assertIn("PROJECT_SETUP_CONFIG=custom/project_setup.json", result.stdout)
        self.assertIn("PROJECT_SETUP_PROJECT_NUMBER=17", result.stdout)
        self.assertIn("PROJECT_SETUP_OWNER_TYPE=organization", result.stdout)

    def test_make_command_line_values_override_env_defaults(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            env_file = Path(temporary_directory) / ".env"
            env_file.write_text(
                "PROJECT_SETUP_TARGET=../configured-target\n"
                "GITHUB_REPOSITORY=owner/configured-repository\n"
                "PROJECT_SETUP_PROJECT_NUMBER=17\n"
                "PROJECT_SETUP_OWNER_TYPE=user\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    MAKE,
                    "--no-print-directory",
                    "help",
                    "TARGET=../override-target",
                    "REPO=owner/override-repository",
                    "PROJECT_NUMBER=23",
                    "OWNER_TYPE=organization",
                ],
                cwd=ROOT,
                env=self._base_environment(env_file),
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PROJECT_SETUP_TARGET=../override-target", result.stdout)
        self.assertIn("GITHUB_REPOSITORY=owner/override-repository", result.stdout)
        self.assertIn("PROJECT_SETUP_PROJECT_NUMBER=23", result.stdout)
        self.assertIn("PROJECT_SETUP_OWNER_TYPE=organization", result.stdout)


if __name__ == "__main__":
    unittest.main()
