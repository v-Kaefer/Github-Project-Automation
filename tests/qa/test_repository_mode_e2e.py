from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
GIT = shutil.which("git")


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


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=clean_environment(),
        capture_output=True,
        text=True,
        check=False,
    )


def install_target(target: Path) -> subprocess.CompletedProcess[str]:
    return run(
        [
            sys.executable,
            "-m",
            "project_setup",
            "init",
            "--source",
            str(ROOT),
            "--target",
            str(target),
            "--live",
        ],
        ROOT,
    )


def prepare_git_repository(target: Path) -> None:
    init = run([GIT, "init"], target)
    if init.returncode != 0:
        raise AssertionError(init.stderr)
    add = run([GIT, "add", "--all"], target)
    if add.returncode != 0:
        raise AssertionError(add.stderr)


@unittest.skipUnless(GIT, "Git is required for repository-mode validation")
class EmbeddedRepositoryModeTests(unittest.TestCase):
    def test_target_test_named_like_tool_test_does_not_change_repository_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory) / "target"
            install = install_target(target)
            self.assertEqual(install.returncode, 0, install.stderr)
            self.assertFalse((target / ".project-setup-source").exists())

            tests = target / "tests"
            tests.mkdir(exist_ok=True)
            (tests / "test_project_setup.py").write_text(
                "def test_target_owned_project_setup_behavior():\n    assert True\n",
                encoding="utf-8",
            )
            prepare_git_repository(target)

            result = run([sys.executable, "scripts/validation/repo_quality.py"], target)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("repository_quality_mode=embedded-target", result.stdout)
            self.assertNotIn("repository_quality_mode=tool-source", result.stdout)

    def test_preserved_target_makefile_does_not_need_managed_script_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory) / "target"
            target.mkdir()
            original_makefile = "custom-check:\n\t@echo target-owned-makefile\n"
            (target / "Makefile").write_text(original_makefile, encoding="utf-8")

            install = install_target(target)
            self.assertEqual(install.returncode, 0, install.stderr)
            self.assertEqual((target / "Makefile").read_text(encoding="utf-8"), original_makefile)
            self.assertNotIn("scripts/validation/repo_quality.py", original_makefile)
            prepare_git_repository(target)

            result = run([sys.executable, "scripts/validation/repo_quality.py"], target)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("repository_quality_mode=embedded-target", result.stdout)
            self.assertIn("caller_contracts=skipped status=embedded-target-preserved-files", result.stdout)


if __name__ == "__main__":
    unittest.main()
