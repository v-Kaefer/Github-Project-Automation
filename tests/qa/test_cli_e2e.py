from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


def clean_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in (
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "PROJECT_SETUP_PAT",
        "GITHUB_REPOSITORY",
        "PROJECT_SETUP_TARGET",
        "PROJECT_SETUP_PROJECT_NUMBER",
        "PROJECT_SETUP_ENV_FILE",
    ):
        environment.pop(name, None)
    return environment


def run_cli(*arguments: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "project_setup", *arguments],
        cwd=cwd or ROOT,
        env=clean_environment(),
        capture_output=True,
        text=True,
        check=False,
    )


class QaCliEndToEndTests(unittest.TestCase):
    def test_install_dry_run_does_not_create_target(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory) / "not-created"
            result = run_cli(
                "init",
                "--source",
                str(ROOT),
                "--target",
                str(target),
                "--dry-run",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("[DRY-RUN] Would copy", result.stdout)
            self.assertFalse(target.exists())

    def test_live_install_preserves_target_files_and_embeds_required_contracts(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory) / "target"
            target.mkdir()
            preserved = {
                "README.md": "target readme\n",
                "LICENSE": "target license\n",
                "Makefile": "target makefile\n",
                ".env.example": "TARGET_SPECIFIC=value\n",
                "AGENTS.md": "target agent instructions\n",
            }
            for relative, content in preserved.items():
                (target / relative).write_text(content, encoding="utf-8")

            result = run_cli(
                "init",
                "--source",
                str(ROOT),
                "--target",
                str(target),
                "--live",
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            for relative, content in preserved.items():
                self.assertEqual((target / relative).read_text(encoding="utf-8"), content)

            self.assertTrue((target / "project_setup" / "cli.py").is_file())
            self.assertTrue((target / "AI_SETUP_GUIDE.md").is_file())
            self.assertTrue((target / "licenses" / "project_setup" / "LICENSE").is_file())
            self.assertTrue((target / "licenses" / "project_setup" / "NOTICE").is_file())
            self.assertTrue((target / ".github" / "workflows" / "project-setup.yml").is_file())
            self.assertTrue((target / "config" / "project" / "labels.json").is_file())

    def test_embedded_commands_remain_dry_run_without_credentials(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory) / "target"
            install = run_cli(
                "init",
                "--source",
                str(ROOT),
                "--target",
                str(target),
                "--live",
            )
            self.assertEqual(install.returncode, 0, install.stderr)
            (target / ".env").write_text(
                "PROJECT_SETUP_TARGET=.\n"
                "GITHUB_REPOSITORY=owner/qa-sandbox\n"
                "PROJECT_SETUP_CONFIG=project_setup.json\n",
                encoding="utf-8",
            )

            commands = (
                ("labels", "sync"),
                ("milestones", "sync"),
                ("issues", "generate"),
                ("project", "create"),
                ("apply",),
            )
            for command in commands:
                with self.subTest(command=command):
                    result = run_cli(*command, cwd=target)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("DRY-RUN", result.stdout)

            project_sync = run_cli(
                "project",
                "sync",
                "--project-number",
                "1",
                cwd=target,
            )
            self.assertEqual(project_sync.returncode, 0, project_sync.stderr)
            self.assertIn("Offline Project v2 preview", project_sync.stdout)
            self.assertIn("Remote Project fields, items, and issues were not queried", project_sync.stdout)

    def test_doctor_is_read_only_and_uses_embedded_configuration(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory) / "target"
            install = run_cli(
                "init",
                "--source",
                str(ROOT),
                "--target",
                str(target),
                "--live",
            )
            self.assertEqual(install.returncode, 0, install.stderr)
            (target / ".env").write_text(
                "PROJECT_SETUP_TARGET=.\n"
                "GITHUB_REPOSITORY=owner/qa-sandbox\n",
                encoding="utf-8",
            )

            result = run_cli("doctor", cwd=target)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Doctor completed", result.stdout)
            self.assertIn("No GitHub API changes were made", result.stdout)


if __name__ == "__main__":
    unittest.main()
