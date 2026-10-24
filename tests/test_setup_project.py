"""Checks for plugins/studio/skills/idea/scripts/setup_project.py."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = (Path(__file__).resolve().parents[1] / "plugins" / "studio" / "skills" / "idea"
          / "scripts" / "setup_project.py")
CREATED = ["AGENTS.md", "CLAUDE.md", ".gitignore", ".claude/settings.json",
           ".codex/config.toml", "zensical.toml", "requirements-docs.txt", "docs/index.md",
           "docs/.terms.md"]
GIT_USER = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def setup(root, *args, **env):
    environment = {**os.environ, **GIT_USER}
    environment.pop("CODEX_SANDBOX", None)
    environment.update(env)
    result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), *args],
                            capture_output=True, text=True, encoding="utf-8", env=environment,
                            timeout=60)
    assert result.returncode == 0, result.stderr
    return result.stdout


def git_log(root):
    result = subprocess.run(["git", "log", "--oneline"], cwd=root, capture_output=True,
                            text=True)
    return result.stdout.strip()


class SetupProject(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "Книжная полка"

    def tearDown(self):
        self.tmp.cleanup()

    def test_new_folder_gets_every_file_and_a_commit(self):
        output = setup(self.root, "--language", "ru")
        for name in CREATED:
            self.assertTrue((self.root / name).is_file(), name)
        config = (self.root / "zensical.toml").read_text(encoding="utf-8")
        self.assertIn('site_name = "Книжная полка"', config)
        self.assertIn('language = "ru"', config)
        self.assertIn("created  git repository", output)
        self.assertIn("set up project", git_log(self.root))

    def test_existing_files_are_kept(self):
        self.root.mkdir(parents=True)
        (self.root / "AGENTS.md").write_text("# Own rules\n", encoding="utf-8")
        (self.root / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
        output = setup(self.root)
        self.assertEqual((self.root / "AGENTS.md").read_text(encoding="utf-8"), "# Own rules\n")
        self.assertIn("kept     AGENTS.md", output)
        ignore = (self.root / ".gitignore").read_text(encoding="utf-8")
        self.assertTrue(ignore.startswith("node_modules/\n"))
        self.assertIn(".venv/", ignore)
        self.assertEqual(ignore.count("node_modules/"), 1)
        self.assertIn("kept", setup(self.root))

    def test_inside_the_codex_sandbox_git_is_left_to_the_agent(self):
        output = setup(self.root, CODEX_SANDBOX="windows")
        self.assertTrue((self.root / "AGENTS.md").is_file())
        self.assertFalse((self.root / ".git").exists())
        self.assertIn("outside the sandbox", output)


if __name__ == "__main__":
    unittest.main()
