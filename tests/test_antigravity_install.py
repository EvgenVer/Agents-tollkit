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
                            capture_output=True, text=True, encoding="utf-8", timeout=60)
    return result.returncode, result.stdout + result.stderr


class Install(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = Path(self.tmp.name) / "config"
        self.copy = self.config / "plugins" / "studio"

    def tearDown(self):
        run("uninstall", self.config)
        self.tmp.cleanup()

    def assertPluginIntact(self):
        self.assertTrue((PLUGIN / "hooks.json").is_file())
        self.assertTrue((PLUGIN / "hooks" / "studio_hooks.py").is_file())

    def test_install_copies_the_plugin(self):
        code, output = run("install", self.config)
        self.assertEqual(code, 0, output)
        for relative in ["hooks.json", ".antigravity-plugin/plugin.json",
                         "hooks/studio_hooks.py", "skills/idea/SKILL.md"]:
            self.assertEqual((self.copy / relative).read_bytes(),
                             (PLUGIN / relative).read_bytes(), relative)
        self.assertFalse(list(self.copy.rglob("__pycache__")))
        # The IDE reads the manifest only from the plugin root; the checkout has none there.
        self.assertEqual((self.copy / "plugin.json").read_bytes(),
                         (PLUGIN / ".antigravity-plugin" / "plugin.json").read_bytes())
        self.assertFalse((PLUGIN / "plugin.json").exists())

    def test_install_again_replaces_the_copy(self):
        run("install", self.config)
        (self.copy / "hooks.json").write_text("stale", encoding="utf-8")
        (self.copy / "leftover.txt").write_text("old", encoding="utf-8")
        self.assertEqual(run("install", self.config)[0], 0)
        self.assertEqual((self.copy / "hooks.json").read_bytes(),
                         (PLUGIN / "hooks.json").read_bytes())
        self.assertFalse((self.copy / "leftover.txt").exists())

    def test_uninstall_removes_the_copy_only(self):
        run("install", self.config)
        code, output = run("uninstall", self.config)
        self.assertEqual(code, 0, output)
        self.assertFalse(os.path.lexists(self.copy))
        self.assertPluginIntact()
        self.assertIn("was not installed", run("uninstall", self.config)[1])

    def test_a_foreign_folder_is_left_alone(self):
        self.copy.mkdir(parents=True)
        (self.copy / "mine.txt").write_text("keep", encoding="utf-8")
        for action in ["install", "uninstall"]:
            code, output = run(action, self.config)
            self.assertEqual(code, 1, output)
            self.assertIn("not created by this script", output)
        self.assertEqual((self.copy / "mine.txt").read_text(encoding="utf-8"), "keep")

    @unittest.skipUnless(os.name == "nt", "junctions exist on Windows only")
    def test_a_link_from_an_earlier_version_is_replaced(self):
        self.copy.parent.mkdir(parents=True)
        subprocess.run(["cmd", "/c", "mklink", "/J", str(self.copy), str(PLUGIN)],
                       check=True, capture_output=True)
        code, output = run("install", self.config)
        self.assertEqual(code, 0, output)
        with self.assertRaises(OSError):
            os.readlink(self.copy)  # a real folder now, not a link
        self.assertTrue((self.copy / "hooks.json").is_file())
        self.assertPluginIntact()

    def test_warns_when_studio_is_switched_off(self):
        self.config.mkdir()
        (self.config / "config.json").write_text(
            json.dumps({"plugins": {"studio": {"enabled": False}}}), encoding="utf-8")
        self.assertIn("switched off", run("install", self.config)[1])


if __name__ == "__main__":
    unittest.main()
