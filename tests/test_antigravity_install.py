"""Checks for scripts/antigravity.py."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "antigravity.py"
PLUGINS = (REPO / "plugins").resolve()


def run(action, config):
    result = subprocess.run([sys.executable, str(SCRIPT), action, "--config", str(config)],
                            capture_output=True, text=True, encoding="utf-8", timeout=30)
    return result.returncode, result.stdout + result.stderr


class Install(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = Path(self.tmp.name) / "config"
        self.target = self.config / "plugins.json"

    def tearDown(self):
        self.tmp.cleanup()

    def entries(self):
        return json.loads(self.target.read_text(encoding="utf-8"))["entries"]

    def test_install_registers_the_plugins_folder_once(self):
        self.assertEqual(run("install", self.config)[0], 0)
        self.assertEqual(run("install", self.config)[0], 0)
        entries = self.entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(Path(entries[0]["path"]).resolve(), PLUGINS)
        self.assertEqual(entries[0]["include_only"], ["studio"])
        self.assertTrue((PLUGINS / "studio" / ".antigravity-plugin" / "plugin.json").is_file())
        self.assertTrue((PLUGINS / "studio" / "hooks.json").is_file())

    def test_other_entries_are_kept(self):
        self.config.mkdir()
        other = {"path": "~/team-plugins"}
        self.target.write_text(json.dumps({"entries": [other], "inherits": []}),
                               encoding="utf-8")
        run("install", self.config)
        self.assertEqual(self.entries()[0], other)
        run("uninstall", self.config)
        self.assertEqual(json.loads(self.target.read_text(encoding="utf-8")),
                         {"entries": [other], "inherits": []})

    def test_uninstall_removes_a_file_it_alone_used(self):
        run("install", self.config)
        code, output = run("uninstall", self.config)
        self.assertEqual(code, 0, output)
        self.assertFalse(self.target.exists())
        self.assertIn("was not registered", run("uninstall", self.config)[1])

    def test_invalid_file_is_left_alone(self):
        self.config.mkdir()
        self.target.write_text("{not json", encoding="utf-8")
        code, output = run("install", self.config)
        self.assertEqual(code, 1)
        self.assertIn("not valid", output)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "{not json")

    def test_warns_when_studio_is_switched_off(self):
        self.config.mkdir()
        (self.config / "config.json").write_text(
            json.dumps({"plugins": {"studio": {"enabled": False}}}), encoding="utf-8")
        self.assertIn("switched off", run("install", self.config)[1])


if __name__ == "__main__":
    unittest.main()
