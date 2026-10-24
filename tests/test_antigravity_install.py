"""Checks for scripts/antigravity.py."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "antigravity.py"
PLUGIN = (REPO / "plugins" / "studio").resolve()


def run(action, config):
    result = subprocess.run([sys.executable, str(SCRIPT), action, "--config", str(config)],
                            capture_output=True, text=True, encoding="utf-8", timeout=30)
    return result.returncode, result.stdout + result.stderr


class Install(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = Path(self.tmp.name) / "config"
        self.link = self.config / "plugins" / "studio"

    def tearDown(self):
        run("uninstall", self.config)  # remove the link first: cleanup must not reach the checkout
        self.tmp.cleanup()

    def test_install_links_the_plugin_folder(self):
        for _ in range(2):
            code, output = run("install", self.config)
            self.assertEqual(code, 0, output)
        self.assertEqual(Path(os.readlink(self.link).removeprefix("\\\\?\\")).resolve(),
                         PLUGIN)
        self.assertTrue((self.link / "hooks.json").is_file())
        self.assertTrue((self.link / ".antigravity-plugin" / "plugin.json").is_file())

    def test_uninstall_removes_only_the_link(self):
        run("install", self.config)
        code, output = run("uninstall", self.config)
        self.assertEqual(code, 0, output)
        self.assertFalse(os.path.lexists(self.link))
        self.assertTrue((PLUGIN / "hooks.json").is_file())
        self.assertTrue((PLUGIN / "hooks" / "studio_hooks.py").is_file())
        self.assertIn("was not installed", run("uninstall", self.config)[1])

    def test_a_real_folder_is_left_alone(self):
        self.link.mkdir(parents=True)
        (self.link / "mine.txt").write_text("keep", encoding="utf-8")
        for action in ["install", "uninstall"]:
            code, output = run(action, self.config)
            self.assertEqual(code, 1, output)
            self.assertIn("not a link", output)
        self.assertEqual((self.link / "mine.txt").read_text(encoding="utf-8"), "keep")

    def test_warns_when_studio_is_switched_off(self):
        self.config.mkdir()
        (self.config / "config.json").write_text(
            json.dumps({"plugins": {"studio": {"enabled": False}}}), encoding="utf-8")
        self.assertIn("switched off", run("install", self.config)[1])


if __name__ == "__main__":
    unittest.main()
