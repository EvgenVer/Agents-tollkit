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
# A place outside the test project, the temp folder and the agents' own folders.
OUTSIDE = Path.home() / "Documents" / "studio-hook-test.txt"


def run_hook(command, payload, *args):
    result = subprocess.run([sys.executable, str(SCRIPT), command, *args],
                            input=json.dumps(payload), capture_output=True, text=True,
                            encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout) if result.stdout.strip() else None


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd,
                   check=True, capture_output=True)


def set_mtime(path, offset):
    moment = time.time() + offset
    os.utime(path, (moment, moment))


class ProjectCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve() / "project"
        (self.root / "docs").mkdir(parents=True)
        (self.root / "docs" / "TASKS.md").write_text(TASKS_TEXT, encoding="utf-8")
        (self.root / "app.py").write_text("print('hi')\n", encoding="utf-8")
        git(self.root, "init", "-q")
        git(self.root, "add", ".")
        git(self.root, "commit", "-q", "-m", "init")

    def tearDown(self):
        self.tmp.cleanup()

    def decision(self, tool, **tool_input):
        result = hooks.guard_decision({"tool_name": tool, "tool_input": tool_input,
                                       "cwd": str(self.root)})
        return result[0] if result else None

    def assertDecision(self, expected, tool, items, field="command"):
        for item in items:
            self.assertEqual(self.decision(tool, **{field: str(item)}), expected, item)


class SecretPaths(unittest.TestCase):
    def test_secret_names(self):
        for path in [".env", "config/.env.local", "C:\\proj\\.env", "id_rsa", "server.key",
                     "certs/site.pem", "~/.ssh/config", ".aws/credentials"]:
            self.assertTrue(hooks.is_secret_path(path), path)

    def test_ordinary_names(self):
        for path in [".env.example", "env.py", "README.md", "id_rsa.pub", "keys.py",
                     "docs/TASKS.md", "", None]:
            self.assertFalse(hooks.is_secret_path(path), path)


class Secrets(ProjectCase):
    def test_reading_secrets_is_denied(self):
        (self.root / ".env").write_text("TOKEN=x\n", encoding="utf-8")
        self.assertEqual(self.decision("Read", file_path=str(self.root / ".env")), "deny")
        self.assertEqual(self.decision("Write", file_path=str(self.root / ".env")), "deny")
        self.assertEqual(self.decision("Grep", pattern="TOKEN", path=".env"), "deny")
        self.assertEqual(self.decision("Glob", pattern="**/.env"), "deny")
        self.assertDecision("deny", "Bash", ["cat .env", "type config\\.env.local"])
        self.assertDecision("deny", "PowerShell", ["Get-Content .\\.env"])
        patch = "*** Begin Patch\n*** Update File: .env\n@@\n-A=1\n+A=2\n*** End Patch"
        self.assertEqual(self.decision("apply_patch", command=patch), "deny")

    def test_safe_secret_handling_is_allowed(self):
        self.assertIsNone(self.decision("Write", file_path=str(self.root / ".env")))  # new file
        self.assertIsNone(self.decision("Read", file_path=str(self.root / ".env.example")))
        self.assertIsNone(self.decision("Grep", pattern=r"\.env", path="."))
        self.assertDecision(None, "Bash", ["cp .env.example .env",
                                           'git commit -m "Ignore .env files"'])


class Git(ProjectCase):
    def test_destructive_git_is_denied(self):
        self.assertDecision("deny", "Bash", [
            "git push --force", "git push -f origin main", "git push origin +main",
            "git reset --hard HEAD~1", "git clean -fd", "git checkout -- .", "git restore .",
            "npm test && git reset --hard"])

    def test_ordinary_git_is_allowed(self):
        self.assertDecision(None, "Bash", [
            "git status", "git restore --staged .", "git checkout main",
            "git commit -am 'save'", "git reset HEAD app.py",
            'git commit -m "explain why git reset --hard is blocked"'])

    def test_push_needs_the_owner(self):
        self.assertDecision("ask", "Bash", ["git push origin main", "git add . && git push"])


class Deleting(ProjectCase):
    def test_deleting_folders_outside_is_denied(self):
        self.assertDecision("deny", "Bash", [
            "rm -rf /", "rm -rf ..", "rm -rf ~", "rm -rf $HOME/x", "rm -rf .", "rm -rf *",
            f"rm -r -f {Path.home() / 'other'}", "Remove-Item -Recurse -Force C:\\Users",
            "rd /s /q ..", "rm -rf"])

    def test_deleting_files_outside_needs_the_owner(self):
        self.assertDecision("ask", "Bash", [f"rm {OUTSIDE}", f"del {OUTSIDE}",
                                            "rm ~/notes.txt"])
        self.assertDecision("ask", "PowerShell", [f"Remove-Item -Force {OUTSIDE}"])

    def test_deleting_inside_the_project_is_allowed(self):
        self.assertDecision(None, "Bash", [
            "rm -rf node_modules", "rm -rf build/*", "rm app.py", "rm -f *.log", "rm *",
            "Remove-Item -Recurse -Force .\\dist", "rd /s /q build", "rm -Force app.py",
            f"rm -rf {tempfile.gettempdir()}/scratch-x"])


class OutsideFiles(ProjectCase):
    def test_files_outside_the_project_need_the_owner(self):
        for tool in ["Read", "Write", "Edit"]:
            self.assertEqual(self.decision(tool, file_path=str(OUTSIDE)), "ask", tool)
        self.assertEqual(self.decision("Grep", pattern="x", path=str(OUTSIDE.parent)), "ask")
        self.assertEqual(self.decision("Glob", pattern=f"{OUTSIDE.parent.as_posix()}/**/*.pdf"),
                         "ask")
        claude_settings = Path.home() / ".claude" / "settings.json"
        self.assertEqual(self.decision("Write", file_path=str(claude_settings)), "ask")

    def test_project_temp_and_agent_folders_are_allowed(self):
        notes = Path.home() / ".claude" / "projects" / "demo" / "memory" / "note.md"
        for tool, path in [("Read", self.root / "app.py"), ("Write", "src/new.py"),
                           ("Read", Path(tempfile.gettempdir()) / "x.txt"),
                           ("Read", Path.home() / ".claude" / "settings.json"),
                           ("Write", notes)]:
            self.assertIsNone(self.decision(tool, file_path=str(path)), (tool, path))
        self.assertIsNone(self.decision("Grep", pattern="x"))
        self.assertIsNone(self.decision("Glob", pattern="**/*.py"))


class Installs(ProjectCase):
    def test_global_installs_need_the_owner(self):
        self.assertDecision("ask", "Bash", [
            "npm install -g typescript", "npm i --global pnpm", "pip install requests",
            "python -m pip install -r requirements.txt", "pip install --user httpx",
            "winget install Git.Git", "uv tool install ruff", "cargo install ripgrep",
            "yarn global add serve", "uv pip install --system httpx"])
        self.assertDecision("ask", "PowerShell", ["Install-Module PSReadLine"])

    def test_project_installs_are_allowed(self):
        self.assertDecision(None, "Bash", [
            "npm install express", "npm ci", ".venv\\Scripts\\python -m pip install requests",
            ".venv/bin/pip install -r requirements.txt", "uv pip install httpx", "uv add httpx",
            "source .venv/bin/activate && pip install httpx",
            'git commit -m "document npm install -g usage"'])
        self.assertDecision(None, "PowerShell", [".venv\\Scripts\\activate; pip install requests"])


class GuardOutput(ProjectCase):
    def payload(self, command):
        return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(self.root)}

    def test_output_shapes(self):
        denied = run_hook("guard", self.payload("cat .env"))["hookSpecificOutput"]
        self.assertEqual(denied["permissionDecision"], "deny")
        self.assertIn("secrets", denied["permissionDecisionReason"])
        asked = run_hook("guard", self.payload("git push"))["hookSpecificOutput"]
        self.assertEqual(asked["permissionDecision"], "ask")
        self.assertIsNone(run_hook("guard", self.payload("ls")))

    def test_codex_cannot_ask_so_it_denies(self):
        output = run_hook("guard", self.payload("git push"), "--host", "codex")
        decision = output["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("Codex", decision["permissionDecisionReason"])


class SessionStart(ProjectCase):
    def context(self):
        output = run_hook("session-start", {"cwd": str(self.root), "source": "compact"})
        return output["hookSpecificOutput"]["additionalContext"]

    def test_injects_now_section(self):
        context = self.context()
        self.assertIn("Next step: add the save button", context)
        self.assertNotIn("Show the list", context)

    def test_mentions_uncommitted_changes(self):
        (self.root / "app.py").write_text("print('changed')\n", encoding="utf-8")
        self.assertIn("uncommitted changes in 1 file", self.context())

    def test_flags_a_long_tasks_file(self):
        filler = "".join(f"- [x] T{n} done\n" for n in range(200))
        (self.root / "docs" / "TASKS.md").write_text(TASKS_TEXT + filler, encoding="utf-8")
        self.assertIn("Move finished stages", self.context())
        self.assertNotIn("T150 done", self.context())

    def test_flags_missing_project_commands(self):
        (self.root / "docs" / "ARCHITECTURE.md").write_text("Status: approved 2026-10-23\n",
                                                            encoding="utf-8")
        agents = self.root / "AGENTS.md"
        agents.write_text("# AGENTS.md\n\n## Project commands\n\n<!-- later -->\n",
                          encoding="utf-8")
        self.assertIn("Project skeleton", self.context())
        agents.write_text("# AGENTS.md\n\n## Project commands\n\n- Test: pytest\n",
                          encoding="utf-8")
        self.assertNotIn("Project skeleton", self.context())

    def test_silent_without_tasks(self):
        os.remove(self.root / "docs" / "TASKS.md")
        self.assertIsNone(run_hook("session-start", {"cwd": str(self.root)}))


class Stop(ProjectCase):
    def stop(self, **extra):
        return run_hook("stop", {"cwd": str(self.root), **extra})

    def test_clean_project_can_stop(self):
        self.assertIsNone(self.stop())

    def test_unrecorded_change_blocks_once(self):
        (self.root / "app.py").write_text("print('changed')\n", encoding="utf-8")
        set_mtime(self.root / "app.py", 5)
        self.assertEqual(self.stop()["decision"], "block")
        self.assertIsNone(self.stop(stop_hook_active=True))

    def test_recorded_change_can_stop(self):
        (self.root / "app.py").write_text("print('changed')\n", encoding="utf-8")
        set_mtime(self.root / "docs" / "TASKS.md", 5)
        self.assertIsNone(self.stop())

    def test_pages_about_changed_code_must_be_checked(self):
        page = self.root / "docs" / "components" / "app.md"
        page.parent.mkdir()
        page.write_text("# App\n\nThe entry point is `app.py`.\n", encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-q", "-m", "docs")
        (self.root / "app.py").write_text("print('changed')\n", encoding="utf-8")
        set_mtime(self.root / "app.py", 5)
        set_mtime(self.root / "docs" / "TASKS.md", 10)
        reason = self.stop()["reason"]
        self.assertIn("docs/components/app.md (app.py)", reason)
        self.assertNotIn("newer than docs/TASKS.md", reason)
        set_mtime(page, 20)
        self.assertIsNone(self.stop())

    def test_other_projects_are_ignored(self):
        os.remove(self.root / "docs" / "TASKS.md")
        (self.root / "app.py").write_text("print('changed')\n", encoding="utf-8")
        self.assertIsNone(self.stop())


class Robustness(unittest.TestCase):
    def test_bad_input_never_blocks(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "guard"], input="not json",
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
