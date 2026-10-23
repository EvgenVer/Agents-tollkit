"""Checks for plugins/studio/hooks/studio_hooks.py. Run: python -m unittest discover -s tests"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "plugins" / "studio" / "hooks" / "studio_hooks.py"
spec = importlib.util.spec_from_file_location("studio_hooks", SCRIPT)
hooks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hooks)

TASKS_TEXT = """# Tasks — Demo

## Now

- Stage: 1 — Save books
- Active task: T2
- Next step: add the save button

## Stage 1 — Save books

- [x] T1 Show the list — check: open page — done
- [ ] T2 Save a book — check: click save
"""


def run_hook(command, payload):
    result = subprocess.run([sys.executable, str(SCRIPT), command], input=json.dumps(payload),
                            capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout) if result.stdout.strip() else None


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class ProjectCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve() / "project"
        (self.root / "docs").mkdir(parents=True)
        (self.root / "docs" / "TASKS.md").write_text(TASKS_TEXT, encoding="utf-8")
        (self.root / "app.py").write_text("print('hi')\n", encoding="utf-8")
        git(self.root, "init", "-q")
        git(self.root, "-c", "user.name=t", "-c", "user.email=t@t", "add", ".")
        git(self.root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init")

    def tearDown(self):
        self.tmp.cleanup()

    def guard(self, tool, **tool_input):
        return hooks.guard_reason({"tool_name": tool, "tool_input": tool_input,
                                   "cwd": str(self.root)})


class SecretPaths(unittest.TestCase):
    def test_secret_names(self):
        for path in [".env", "config/.env.local", "C:\\proj\\.env", "id_rsa", "server.key",
                     "certs/site.pem", "~/.ssh/config", ".aws/credentials"]:
            self.assertTrue(hooks.is_secret_path(path), path)

    def test_ordinary_names(self):
        for path in [".env.example", "env.py", "README.md", "id_rsa.pub", "keys.py",
                     "docs/TASKS.md", "", None]:
            self.assertFalse(hooks.is_secret_path(path), path)


class Guard(ProjectCase):
    def test_reading_secrets_is_blocked(self):
        (self.root / ".env").write_text("TOKEN=x\n", encoding="utf-8")
        self.assertIsNotNone(self.guard("Read", file_path=str(self.root / ".env")))
        self.assertIsNotNone(self.guard("Write", file_path=str(self.root / ".env")))
        self.assertIsNotNone(self.guard("Grep", pattern="TOKEN", path=".env"))
        self.assertIsNotNone(self.guard("Bash", command="cat .env"))
        self.assertIsNotNone(self.guard("PowerShell", command="Get-Content .\\.env"))
        patch = "*** Begin Patch\n*** Update File: .env\n@@\n-A=1\n+A=2\n*** End Patch"
        self.assertIsNotNone(self.guard("apply_patch", command=patch))

    def test_safe_secret_handling_is_allowed(self):
        self.assertIsNone(self.guard("Write", file_path=str(self.root / ".env")))  # new file
        self.assertIsNone(self.guard("Read", file_path=str(self.root / ".env.example")))
        self.assertIsNone(self.guard("Bash", command="cp .env.example .env"))
        self.assertIsNone(self.guard("Bash", command='git commit -m "Ignore .env files"'))
        self.assertIsNone(self.guard("Read", file_path=str(self.root / "app.py")))

    def test_destructive_git_is_blocked(self):
        for command in ["git push --force", "git push -f origin main", "git push origin +main",
                        "git reset --hard HEAD~1", "git clean -fd", "git checkout -- .",
                        "git restore .", "npm test && git reset --hard"]:
            self.assertIsNotNone(self.guard("Bash", command=command), command)

    def test_ordinary_git_is_allowed(self):
        for command in ["git push origin main", "git status", "git restore --staged .",
                        "git checkout main", "git commit -am 'save'", "git reset HEAD app.py"]:
            self.assertIsNone(self.guard("Bash", command=command), command)

    def test_deleting_outside_the_project_is_blocked(self):
        for command in ["rm -rf /", "rm -rf ..", "rm -rf ~", "rm -rf $HOME/x", "rm -rf .",
                        "rm -rf *", f"rm -r -f {Path.home() / 'other'}",
                        "Remove-Item -Recurse -Force C:\\Users",
                        "rd /s /q ..", "rm -rf"]:
            self.assertIsNotNone(self.guard("Bash", command=command), command)

    def test_deleting_inside_the_project_is_allowed(self):
        for command in ["rm -rf node_modules", "rm -rf build/*", "rm app.py", "rm -f *.log",
                        "Remove-Item -Recurse -Force .\\dist", "rd /s /q build",
                        f"rm -rf {tempfile.gettempdir()}/scratch-x"]:
            self.assertIsNone(self.guard("Bash", command=command), command)

    def test_deny_output_shape(self):
        output = run_hook("guard", {"tool_name": "Bash", "tool_input": {"command": "cat .env"},
                                    "cwd": str(self.root)})
        decision = output["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("secrets", decision["permissionDecisionReason"])
        self.assertIsNone(run_hook("guard", {"tool_name": "Bash", "tool_input": {"command": "ls"},
                                             "cwd": str(self.root)}))


class SessionStart(ProjectCase):
    def test_injects_now_section(self):
        output = run_hook("session-start", {"cwd": str(self.root), "source": "compact"})
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Next step: add the save button", context)
        self.assertNotIn("Show the list", context)

    def test_mentions_uncommitted_changes(self):
        (self.root / "app.py").write_text("print('changed')\n", encoding="utf-8")
        output = run_hook("session-start", {"cwd": str(self.root)})
        self.assertIn("uncommitted changes in 1 file", output["hookSpecificOutput"]["additionalContext"])

    def test_silent_without_tasks(self):
        os.remove(self.root / "docs" / "TASKS.md")
        self.assertIsNone(run_hook("session-start", {"cwd": str(self.root)}))


class Stop(ProjectCase):
    def touch_later(self, path):
        later = time.time() + 5
        os.utime(path, (later, later))

    def test_clean_project_can_stop(self):
        self.assertIsNone(run_hook("stop", {"cwd": str(self.root)}))

    def test_unrecorded_change_blocks_once(self):
        (self.root / "app.py").write_text("print('changed')\n", encoding="utf-8")
        self.touch_later(self.root / "app.py")
        output = run_hook("stop", {"cwd": str(self.root)})
        self.assertEqual(output["decision"], "block")
        self.assertIsNone(run_hook("stop", {"cwd": str(self.root), "stop_hook_active": True}))

    def test_recorded_change_can_stop(self):
        (self.root / "app.py").write_text("print('changed')\n", encoding="utf-8")
        self.touch_later(self.root / "docs" / "TASKS.md")
        self.assertIsNone(run_hook("stop", {"cwd": str(self.root)}))

    def test_other_projects_are_ignored(self):
        os.remove(self.root / "docs" / "TASKS.md")
        (self.root / "app.py").write_text("print('changed')\n", encoding="utf-8")
        self.assertIsNone(run_hook("stop", {"cwd": str(self.root)}))


class Robustness(unittest.TestCase):
    def test_bad_input_never_blocks(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "guard"], input="not json",
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
