"""Checks for plugins/studio/hooks/studio_hooks.py. Run: python -m unittest discover -s tests"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "plugins" / "studio"
SCRIPT = PLUGIN / "hooks" / "studio_hooks.py"
# Real Antigravity app and IDE payloads, recorded by a probe hook and anonymised.
FIXTURES = json.loads((Path(__file__).resolve().parent / "fixtures" / "antigravity.json")
                      .read_text(encoding="utf-8"))
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


def forget_start(test, session, root):
    """Remove, once the test ends, the note session start keeps in the temp folder."""
    note = hooks.session_file(session, hooks.git_toplevel(root))
    test.addCleanup(note.unlink, missing_ok=True)


class ProjectCase(unittest.TestCase):
    def setUp(self):
        # Run as if Claude Code started in the test project, whatever started the tests.
        saved = os.environ.pop("CLAUDE_PROJECT_DIR", None)
        if saved is not None:
            self.addCleanup(os.environ.__setitem__, "CLAUDE_PROJECT_DIR", saved)
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

    def test_quoted_paths_with_spaces(self):
        folder = self.root / "my config"
        folder.mkdir()
        (folder / ".env").write_text("TOKEN=x\n", encoding="utf-8")
        self.assertDecision("deny", "PowerShell", [f'Get-Content "{folder / ".env"}"',
                                                   "Get-Content 'my config\\.env'"])
        self.assertDecision("deny", "Bash", ['cat "my config/.env"',
                                             'cd "my config" && cat .env'])
        # Prose that only looks like a secret path names no file, so it passes.
        self.assertDecision(None, "Bash", ['git commit -m "drop old config/.env"',
                                           'git commit -m "rotate server.key"'])

    def test_search_patterns_and_existence_checks_read_nothing(self):
        (self.root / ".env").write_text("TOKEN=x\n", encoding="utf-8")
        self.assertDecision(None, "Bash", [
            r"rg -n 'secret|\.env' src", r'rg -n "\.env" app', "grep -rn .env src",
            r"rg -C 2 -e '\.env' app", "test -f .env"])
        self.assertDecision(None, "PowerShell", [
            "Select-String -Pattern '.env' -Path app.py", "Test-Path -LiteralPath .env",
            r"$staged | Where-Object { $_ -match '(^|/)(\.env($|\.)|credentials)' }"])
        # The files a search reads are still checked.
        self.assertDecision("deny", "Bash", ["rg TOKEN .env", "rg -c TOKEN .env",
                                             "grep -f .env app.py", "grep -rn TOKEN .env"])
        self.assertDecision("deny", "PowerShell", ["Select-String -Path .env -Pattern TOKEN"])

    def test_scripts_that_open_a_secret_file_are_denied(self):
        (self.root / ".env").write_text("TOKEN=x\n", encoding="utf-8")
        self.assertDecision("deny", "Bash", [
            "python - <<'EOF'\nfrom pathlib import Path\nprint(Path('.env').read_text())\nEOF"])
        self.assertDecision("deny", "PowerShell", ["@'\nprint(open('.env').read())\n'@ | python -"])
        # A word that only looks like a secret file, and a commit message, read nothing.
        self.assertDecision(None, "Bash", [
            "python - <<'EOF'\nnote = 'the ledger keeps no credentials; 5 runs'\nEOF",
            "git commit -F - <<'EOF'\nKeep .env out of git\nEOF"])


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
            'git commit -m "explain why git reset --hard is blocked"',
            'codex exec -C "proj" "Then run git push origin main and report"'])

    def test_push_needs_the_owner(self):
        self.assertDecision("ask", "Bash", ["git push origin main", "git add . && git push",
                                            "bash <<'EOF'\ngit push\nEOF"])
        # Text that only mentions a push, even after a semicolon inside the quotes.
        self.assertDecision(None, "Bash", ['git commit -m "fix it; then git push later"',
                                           "python - <<'EOF'\nprint('git push')\nEOF"])

    def test_pushing_a_working_branch_is_allowed(self):
        git(self.root, "checkout", "-q", "-b", "feature")
        self.assertDecision(None, "Bash", [
            "git push", "git push -u origin feature", "git push origin HEAD",
            "git push origin feature 2>&1 | tail -3", "git -C . push --set-upstream origin feature",
            'git push origin feature && git commit -m "then push to main"'])
        self.assertDecision(None, "PowerShell", [
            "git push origin feature; \"push $LASTEXITCODE\"",
            "git push origin feature 2>&1 | Select-Object -Last 2"])
        # The main branch, or branches the command does not name, still need the owner.
        self.assertDecision("ask", "Bash", [
            "git push origin main", "git push origin master", "git push origin feature:main",
            "git push origin HEAD:refs/heads/master", "git push --all", "git push --tags",
            "git push origin --delete feature", "git push origin :feature",
            'git push origin "$BRANCH"', "git push origin feature main", "git push -fu origin x"])
        # A branch that tracks main, and the remote's default branch, are the main branch too.
        git(self.root, "config", "branch.feature.merge", "refs/heads/main")
        self.assertDecision("ask", "Bash", ["git push", "git push origin"])
        git(self.root, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/develop")
        self.assertDecision("ask", "Bash", ["git push origin develop"])
        self.assertDecision(None, "Bash", ["git push origin feature"])

    def test_options_before_the_git_command(self):
        self.assertDecision("deny", "Bash", [
            "git -C . reset --hard", f'git -C "{self.root}" clean -fd',
            "git --no-pager checkout -- .", "git -c core.pager=cat push --force",
            "git push origin main; git reset --hard"])
        self.assertDecision("ask", "Bash", [
            "git -C . push origin main", "git -c user.name=x push", "git --no-pager push",
            "git --git-dir .git --work-tree . push"])
        self.assertDecision(None, "Bash", [
            "git -C . status", 'git -C "some dir" log -1', "git --version",
            'git commit -m "use git -C . reset --hard with care"'])


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

    def test_shell_and_patch_writes_outside_need_the_owner(self):
        self.assertDecision("ask", "Bash", [
            f"cp app.py {OUTSIDE}", f"mv app.py {OUTSIDE}", f"echo hi > {OUTSIDE}",
            f"npm test >> {OUTSIDE}", f"cat app.py | tee {OUTSIDE}"])
        self.assertDecision("ask", "PowerShell", [
            f"Set-Content {OUTSIDE} -Value 1", f"Set-Content -Value 1 -Path {OUTSIDE}",
            f"Get-Process | Out-File {OUTSIDE}", f"Copy-Item app.py -Destination {OUTSIDE}"])
        patch = f"*** Begin Patch\n*** Add File: {OUTSIDE}\n+test\n*** End Patch"
        self.assertEqual(self.decision("apply_patch", command=patch), "ask")

    def test_shell_and_patch_writes_inside_are_allowed(self):
        self.assertDecision(None, "Bash", [
            "cp app.py backup.py", "mv app.py src/app.py", "npm test > out.log 2>&1",
            "python app.py > /dev/null", "cat app.py | tee copy.py",
            f"cp app.py {tempfile.gettempdir()}/copy.py"])
        self.assertDecision(None, "PowerShell", [
            "Set-Content notes.txt -Value 'a b'", "Get-Process | Out-File procs.txt",
            "Copy-Item app.py -Destination .\\dist", "npm test > $null",
            "New-Item -ItemType Directory -Path src"])
        patch = "*** Begin Patch\n*** Add File: src/new.py\n+x = 1\n*** End Patch"
        self.assertIsNone(self.decision("apply_patch", command=patch))

    def test_a_greater_than_sign_in_text_is_not_a_redirect(self):
        self.assertDecision(None, "Bash", [
            "printf 'Fix it\\n\\nCo-Authored-By: Claude <noreply@anthropic.com>\\n' > msg.txt",
            'git commit -m "Fix it <noreply@anthropic.com>"',
            "git commit -F - <<'EOF'\nFix it\n\nCo-Authored-By: Claude <noreply@anthropic.com>\nEOF",
            "uv run python - <<'PYEOF'\nif len(modes) > 1:\n    pass\ndef f(x) -> R:\n"
            "    return x\nPYEOF",
            "cat > notes.md <<'EOF'\nThe log goes to `<Work>/<name>_01.txt`.\nEOF"])
        self.assertDecision(None, "PowerShell", [
            "@'\nif a > 1:\n    s = '<a id=\"x\"></a>'\n'@ | .\\.venv\\Scripts\\python.exe -"])
        # Real redirects, also inside a here-document a shell runs, are still checked.
        self.assertDecision("ask", "Bash", [
            f"printf 'Fix it <a@b.c>' > {OUTSIDE}", f"cat > {OUTSIDE} <<'EOF'\nhi\nEOF",
            f"bash <<'EOF'\necho hi > {OUTSIDE}\nEOF"])

    def test_a_change_of_folder_is_followed(self):
        documents = OUTSIDE.parent
        self.assertDecision("ask", "PowerShell", [
            f'cd "{documents}"; Set-Content notes.txt -Value 1',
            f"Set-Location -Path {documents}; Get-Process | Out-File procs.txt",
            f"pushd {documents} && echo hi > x.txt"])
        self.assertDecision(None, "PowerShell", [
            "cd src; Set-Content notes.txt -Value 1",
            f"pushd {documents}; popd; Set-Content notes.txt -Value 1"])
        self.assertDecision("deny", "Bash", ["cd .. && rm -rf project",
                                             f"cd {documents} && rm -rf ."])

    def test_variables_set_in_the_command_are_followed(self):
        work = Path(tempfile.gettempdir()) / "studio-hook-wt"
        documents = OUTSIDE.parent
        self.assertDecision(None, "Bash", [
            f'W="{work.as_posix()}"; cd "$W" && node setup.mjs > ../setup.log 2>&1',
            f'W="{work.as_posix()}"; cat >> "$W/notes.txt" <<\'EOF\'\nx\nEOF',
            "O=build/out; rm -f \"$O\"/*.png \"$O\"/mosaics/*.png",
            f'D="{documents.as_posix()}"; D=$(pwd); cd "$D" && echo hi > x.txt'])
        self.assertDecision(None, "PowerShell", ["$S = 'src'; Set-Content \"$S\\notes.txt\" -Value 1"])
        self.assertDecision("ask", "Bash", [
            'rm -f "$O"/*.png', f'D="{documents.as_posix()}"; cd "$D" && echo hi > x.txt',
            f'D="{documents.as_posix()}"; rm "${{D}}/notes.txt"'])
        self.assertDecision("ask", "PowerShell", [
            f"$S = '{documents}'; Set-Content \"$S\\notes.txt\" -Value 1"])

    def test_a_clone_inside_the_project_is_still_the_project(self):
        clone = self.root / "runtime" / "lib-src"
        clone.mkdir(parents=True)
        git(clone, "init", "-q")
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.root)
        self.addCleanup(os.environ.pop, "CLAUDE_PROJECT_DIR", None)
        for tool, path in [("Edit", self.root / "app.py"), ("Write", clone / "x.py")]:
            result = hooks.guard_decision({"tool_name": tool, "cwd": str(clone),
                                           "tool_input": {"file_path": str(path)}})
            self.assertIsNone(result, (tool, path))
        result = hooks.guard_decision({"tool_name": "Write", "cwd": str(clone),
                                       "tool_input": {"file_path": str(OUTSIDE)}})
        self.assertEqual(result[0], "ask")

    def test_project_temp_and_agent_folders_are_allowed(self):
        notes = Path.home() / ".claude" / "projects" / "demo" / "memory" / "note.md"
        for tool, path in [("Read", self.root / "app.py"), ("Write", "src/new.py"),
                           ("Read", Path(tempfile.gettempdir()) / "x.txt"),
                           ("Read", Path.home() / ".claude" / "settings.json"),
                           ("Write", notes)]:
            self.assertIsNone(self.decision(tool, file_path=str(path)), (tool, path))
        self.assertIsNone(self.decision("Grep", pattern="x"))
        self.assertIsNone(self.decision("Glob", pattern="**/*.py"))

    def test_side_session_notes_of_the_desktop_app_are_allowed(self):
        data = Path.home() / "AppData" / "Local" / "Claude-Data" / "claude_abc"
        notes = data / "side-session-notes" / "local_123" / "t53-progress.md"
        for tool in ["Read", "Write", "Edit"]:
            self.assertIsNone(self.decision(tool, file_path=str(notes)), tool)
        self.assertDecision(None, "Bash", [f'echo done >> "{notes}"'])
        # Elsewhere in the app's data folder is still outside.
        self.assertEqual(self.decision("Write", file_path=str(data / "config.json")), "ask")

    @unittest.skipUnless(os.name == "nt", "Git Bash paths exist on Windows only")
    def test_git_bash_tmp_is_the_temporary_folder(self):
        self.assertDecision(None, "Bash", [
            "python app.py > /tmp/out.txt", "cp app.py /tmp/copy.py", "rm -rf /tmp/scratch-x",
            "cat app.py | tee /tmp/copy.py", "cd /tmp && echo hi > out.txt"])
        for tool in ["Read", "Write"]:
            self.assertIsNone(self.decision(tool, file_path="/tmp/out.txt"), tool)
        # The temporary folder as a whole stays protected, and a similar name is not it.
        self.assertDecision("deny", "Bash", ["rm -rf /tmp", "rm -rf /tmp/*"])
        self.assertDecision("ask", "Bash", ["cp app.py /tmpfiles/copy.py"])


class ExtraFolders(ProjectCase):
    EXTRA = Path.home() / "studio-hook-extra"  # never created: paths are only compared

    def allow(self, *folders, name="settings.local.json"):
        (self.root / ".claude").mkdir(exist_ok=True)
        settings = {"permissions": {"additionalDirectories": [str(f) for f in folders]}}
        (self.root / ".claude" / name).write_text(json.dumps(settings), encoding="utf-8")

    def test_folders_from_claude_settings_are_like_the_temp_folder(self):
        extra = self.EXTRA
        self.assertEqual(self.decision("Write", file_path=str(extra / "a.txt")), "ask")
        self.allow(extra, name="settings.json")
        for tool in ["Read", "Write", "Edit"]:
            self.assertIsNone(self.decision(tool, file_path=str(extra / "Work" / "a.txt")), tool)
        self.assertDecision(None, "Bash", [
            f'echo hi > "{extra}/out.txt"', f'rm "{extra}/Work/a.frame"',
            f'rm -f "{extra.as_posix()}/Work"/*.frame', f'rm "{extra}"/*.txt',
            f'rm -rf "{extra}/Work/tmp"', f'cd "{extra}" && rm -v Data/a.txt Work/b.ald'])
        # The folder itself, everything in it, and other folders stay protected.
        self.assertDecision("deny", "Bash", [f'rm -rf "{extra}"', f'rm -rf "{extra}"/*'])
        self.assertDecision("ask", "Bash", [f"echo hi > {OUTSIDE}"])

    def test_a_whole_drive_does_not_count(self):
        self.allow(Path(OUTSIDE.anchor))
        self.assertEqual(self.decision("Write", file_path=str(OUTSIDE)), "ask")

    def test_changing_the_settings_needs_the_owner(self):
        self.allow(self.EXTRA)
        for name in ["settings.json", "settings.local.json"]:
            path = self.root / ".claude" / name
            self.assertEqual(self.decision("Edit", file_path=str(path)), "ask", name)
            self.assertIsNone(self.decision("Read", file_path=str(path)), name)
        self.assertDecision("ask", "Bash", ["echo {} > .claude/settings.json"])


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

    def test_any_virtual_environment_counts(self):
        self.assertDecision(None, "Bash", [
            "python -m venv tlvenv && ./tlvenv/Scripts/python -m pip install -q comtypes",
            "tools/bin/pip install httpx"])
        python = self.root.parent / "py" / "Scripts" / "python.exe"
        self.assertDecision("ask", "Bash", [f'"{python}" -m pip install httpx'])
        (self.root.parent / "py" / "pyvenv.cfg").parent.mkdir(parents=True)
        (self.root.parent / "py" / "pyvenv.cfg").write_text("home = x\n", encoding="utf-8")
        self.assertDecision(None, "Bash", [f'"{python}" -m pip install httpx'])


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
        git(self.root, "checkout", "-q", "-b", "feature")
        self.assertIsNone(run_hook("guard", self.payload("git push -u origin feature"),
                                   "--host", "codex"))


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

    def test_flags_a_long_now_section_and_keeps_the_reminders(self):
        evidence = "".join(f"- Evidence {n}: " + "measured and recorded. " * 6 + "\n"
                           for n in range(40))
        (self.root / "docs" / "TASKS.md").write_text(
            "# Tasks\n\n## Now\n\n" + evidence + "\n## Stage 1\n", encoding="utf-8")
        (self.root / "app.py").write_text("print('changed')\n", encoding="utf-8")
        context = self.context()
        self.assertLessEqual(len(context), hooks.MAX_CONTEXT_CHARS)
        self.assertIn("The Now section has", context)
        self.assertIn("uncommitted changes in", context)
        self.assertIn("Evidence 0:", context)
        self.assertIn("(cut here", context)

    def test_silent_without_tasks(self):
        os.remove(self.root / "docs" / "TASKS.md")
        self.assertIsNone(run_hook("session-start", {"cwd": str(self.root)}))

    def test_only_codex_gets_the_codex_rules(self):
        output = run_hook("session-start", {"cwd": str(self.root), "source": "compact"},
                          "--host", "codex")
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Next step: add the save button", context)
        for words in ("// @exec:", "write_stdin", "never start it again", "one `exec` call",
                      "three or four", "four commits", "not a stopping point"):
            self.assertIn(words, context)
        claude = self.context()
        self.assertIn("Next step: add the save button", claude)
        for words in ("exec", "write_stdin", "Rules for Codex", "four commits", "stopping point"):
            self.assertNotIn(words, claude)

    def test_codex_gets_its_rules_without_tasks(self):
        os.remove(self.root / "docs" / "TASKS.md")
        output = run_hook("session-start", {"cwd": str(self.root)}, "--host", "codex")
        self.assertEqual(output["hookSpecificOutput"]["additionalContext"], hooks.CODEX_RULES)

    def test_points_an_empty_folder_to_the_idea_skill(self):
        folder = Path(self.tmp.name).resolve() / "new-app"
        (folder / ".git").mkdir(parents=True)
        output = run_hook("session-start", {"cwd": str(folder), "source": "startup"})
        self.assertIn("`idea` skill", output["hookSpecificOutput"]["additionalContext"])
        (folder / "main.py").write_text("", encoding="utf-8")
        self.assertIsNone(run_hook("session-start", {"cwd": str(folder)}))


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

    def start(self, session):
        run_hook("session-start", {"cwd": str(self.root), "session_id": session,
                                   "source": "startup"})
        forget_start(self, session, self.root)

    def commit(self, message):
        git(self.root, "commit", "-q", "-a", "-m", message)

    def test_work_committed_without_a_record_blocks(self):
        session = str(uuid.uuid4())
        self.start(session)
        (self.root / "app.py").write_text("print('changed')\n", encoding="utf-8")
        self.commit("change")
        self.assertIsNone(self.stop())  # without the session the commit is not seen
        self.assertIn("committed in this session", self.stop(session_id=session)["reason"])
        self.assertIsNone(self.stop(session_id=session))  # each reminder is given once
        self.start(session)  # a resumed session keeps the commit it started from
        (self.root / "util.py").write_text("x = 1\n", encoding="utf-8")
        git(self.root, "add", "util.py")
        self.commit("add util")  # a new commit is mentioned, counted from the start
        self.assertIn("2 file(s) were committed", self.stop(session_id=session)["reason"])
        with open(self.root / "docs" / "TASKS.md", "a", encoding="utf-8") as tasks:
            tasks.write("- [x] T2 Save a book — check: click save — done\n")
        self.commit("record")
        self.assertIsNone(self.stop(session_id=session))

    def test_pages_about_committed_and_deleted_files_must_be_checked(self):
        (self.root / "old.py").write_text("x = 1\n", encoding="utf-8")
        page = self.root / "docs" / "components" / "app.md"
        decision = self.root / "docs" / "decisions" / "0001-old.md"
        for path, text in [(page, "`app.py` calls `old.py`."), (decision, "We kept `old.py`.")]:
            path.parent.mkdir(parents=True)
            path.write_text(text + "\n", encoding="utf-8")
        git(self.root, "add", ".")
        self.commit("docs")
        session = str(uuid.uuid4())
        self.start(session)
        (self.root / "app.py").write_text("print('changed')\n", encoding="utf-8")
        set_mtime(self.root / "app.py", 5)
        git(self.root, "rm", "-q", "old.py")
        with open(self.root / "docs" / "TASKS.md", "a", encoding="utf-8") as tasks:
            tasks.write("- [x] T2 Save a book — check: click save — done\n")
        self.commit("work")
        reason = self.stop(session_id=session)["reason"]
        self.assertIn("docs/components/app.md (app.py)", reason)
        self.assertIn("deleted or renamed: docs/components/app.md (old.py)", reason)
        self.assertNotIn("0001-old.md", reason)  # past decisions may name old files
        self.assertNotIn("not updated", reason)
        page.write_text("`app.py` does the work.\n", encoding="utf-8")
        set_mtime(page, 20)
        self.commit("update the page")
        self.assertIsNone(self.stop(session_id=session))

    def test_a_session_hears_each_reminder_once(self):
        page = self.root / "docs" / "components" / "app.md"
        page.parent.mkdir()
        page.write_text("`app.py` uses `util.py`.\n", encoding="utf-8")
        (self.root / "util.py").write_text("x = 1\n", encoding="utf-8")
        git(self.root, "add", ".")
        self.commit("docs")
        session = str(uuid.uuid4())
        self.start(session)
        (self.root / "app.py").write_text("print('changed')\n", encoding="utf-8")
        set_mtime(self.root / "app.py", 5)
        reason = self.stop(session_id=session)["reason"]
        self.assertIn("newer than docs/TASKS.md", reason)
        self.assertIn("docs/components/app.md (app.py)", reason)
        self.assertIsNone(self.stop(session_id=session))
        self.assertEqual(self.stop()["decision"], "block")  # without a session id, always
        (self.root / "util.py").write_text("x = 2\n", encoding="utf-8")
        set_mtime(self.root / "util.py", 10)
        reason = self.stop(session_id=session)["reason"]
        self.assertIn("newer than docs/TASKS.md", reason)  # a newer change is new news
        self.assertIn("docs/components/app.md (util.py)", reason)

    def test_untracked_files_in_hidden_folders_are_not_work(self):
        artifact = self.root / ".artifacts" / "run-1" / "result.json"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("{}\n", encoding="utf-8")
        set_mtime(artifact, 5)
        self.assertIsNone(self.stop())
        (self.root / "notes.md").write_text("draft\n", encoding="utf-8")
        set_mtime(self.root / "notes.md", 5)
        self.assertIn("1 changed file(s)", self.stop()["reason"])

    def transcript(self, meta):
        path = Path(self.tmp.name) / f"rollout-{uuid.uuid4()}.jsonl"
        lines = [{"type": "session_meta", "payload": meta}, {"type": "turn_context"}]
        path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
        return str(path)

    def test_codex_subagents_leave_the_records_to_the_main_agent(self):
        (self.root / "app.py").write_text("print('changed')\n", encoding="utf-8")
        set_mtime(self.root / "app.py", 5)
        subagent = self.transcript({"thread_source": "subagent",
                                    "source": {"subagent": {"thread_spawn": {"depth": 1}}}})
        main = self.transcript({"thread_source": "user", "source": "vscode"})
        for extra in [{"transcript_path": subagent}, {"agent_id": "a1"},
                      {"transcript_path": self.transcript({"source": {"subagent": {}}})}]:
            self.assertIsNone(run_hook("stop", {"cwd": str(self.root), **extra},
                                       "--host", "codex"), extra)
        self.assertEqual(self.stop(transcript_path=main)["decision"], "block")
        claude = Path(self.tmp.name) / "claude.jsonl"
        claude.write_text('{"type": "user", "message": {}}\n', encoding="utf-8")
        self.assertEqual(self.stop(transcript_path=str(claude))["decision"], "block")

    def test_pages_about_uncommitted_deletions_must_be_checked(self):
        page = self.root / "docs" / "components" / "app.md"
        page.parent.mkdir()
        page.write_text("The entry point is `app.py`.\n", encoding="utf-8")
        git(self.root, "add", ".")
        self.commit("docs")
        os.remove(self.root / "app.py")
        self.assertIn("deleted or renamed: docs/components/app.md (app.py)",
                      self.stop()["reason"])


class Robustness(unittest.TestCase):
    def test_bad_input_never_blocks(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "guard"], input="not json",
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_bad_input_never_blocks_antigravity(self):
        # Antigravity reads {} as a denial, so a failed guard must answer allow.
        result = subprocess.run([sys.executable, str(SCRIPT), "guard", "--host", "antigravity"],
                                input="not json", capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {"decision": "allow"})


class Antigravity(ProjectCase):
    def setUp(self):
        super().setUp()
        self.artifacts = Path(self.tmp.name).resolve() / "brain" / "conversation"
        self.artifacts.mkdir(parents=True)
        self.conversation = str(uuid.uuid4())
        forget_start(self, self.conversation, self.root)

    def payload(self, surface, event, **args):
        """A recorded payload moved to this project; args replace recorded tool arguments."""
        def fill(value):
            if isinstance(value, dict):
                return {key: fill(item) for key, item in value.items()}
            if isinstance(value, list):
                return [fill(item) for item in value]
            if isinstance(value, str):
                return (value.replace("{workspace}", str(self.root))
                        .replace("{artifacts}", self.artifacts.as_posix()))
            return value
        payload = fill(FIXTURES[surface][event])
        workspace = self.root.as_posix()
        payload["workspacePaths"] = [workspace[:1].lower() + workspace[1:]]  # as recorded
        payload["conversationId"] = self.conversation
        if args:
            payload["toolCall"]["args"].update({k: str(v) for k, v in args.items()})
        return payload

    def verdict(self, surface, tool, **args):
        calls = hooks.antigravity_calls(self.payload(surface, tool, **args))
        result = hooks.strongest(hooks.guard_decision(call) for call in calls)
        return result[0] if result else None

    def call(self, name, **args):
        """An IDE tool the probe did not record, with the argument names it uses."""
        payload = self.payload("ide", "view_file")
        payload["toolCall"] = {"name": name, "args": args}
        result = hooks.strongest(hooks.guard_decision(call)
                                 for call in hooks.antigravity_calls(payload))
        return result[0] if result else None

    def test_recorded_calls_inside_the_project_pass(self):
        for surface, events in FIXTURES.items():
            for tool in events:
                if tool not in ("SessionStart", "Stop"):
                    self.assertIsNone(self.verdict(surface, tool), (surface, tool))

    def test_files_outside_the_project_need_the_owner(self):
        for tool in ["read_file", "write_file", "edit_file"]:
            self.assertEqual(self.verdict("app", tool, Path=OUTSIDE), "ask", tool)
        self.assertEqual(self.verdict("ide", "view_file", AbsolutePath=OUTSIDE), "ask")
        self.assertEqual(self.verdict("ide", "list_dir", DirectoryPath=OUTSIDE.parent), "ask")
        self.assertEqual(self.verdict("ide", "grep_search", SearchPath=OUTSIDE.parent), "ask")
        for tool in ["write_to_file", "replace_file_content"]:
            self.assertEqual(self.verdict("ide", tool, TargetFile=OUTSIDE), "ask", tool)

    def test_secrets_are_denied(self):
        secret = self.root / ".env"
        self.assertIsNone(self.verdict("app", "write_file", Path=secret))  # a new file
        self.assertIsNone(self.verdict("ide", "write_to_file", TargetFile=secret))
        secret.write_text("TOKEN=x\n", encoding="utf-8")
        self.assertEqual(self.verdict("app", "read_file", Path=secret), "deny")
        self.assertEqual(self.verdict("app", "edit_file", Path=secret), "deny")
        self.assertEqual(self.verdict("ide", "view_file", AbsolutePath=secret), "deny")
        self.assertEqual(self.verdict("ide", "grep_search", SearchPath=secret), "deny")
        self.assertEqual(self.verdict("ide", "write_to_file", TargetFile=secret), "deny")
        self.assertEqual(self.verdict("app", "run_command", CommandLine="Get-Content .env"),
                         "deny")

    def test_commands(self):
        self.assertEqual(self.verdict("app", "run_command", CommandLine="git push"), "ask")
        self.assertEqual(self.verdict("ide", "run_command", CommandLine="npm i -g pnpm"), "ask")
        self.assertEqual(self.verdict("ide", "run_command", CommandLine="git reset --hard"),
                         "deny")
        self.assertEqual(self.verdict("ide", "run_command", Cwd=self.root / "docs",
                                      CommandLine="Remove-Item -Recurse -Force .."), "deny")
        self.assertEqual(self.verdict("app", "run_command",
                                      CommandLine=f"Set-Content {OUTSIDE} -Value 1"), "ask")
        self.assertIsNone(self.verdict("app", "run_command", CommandLine="git status"))

    def test_unrecorded_tools(self):
        (self.root / ".env").write_text("TOKEN=x\n", encoding="utf-8")
        self.assertEqual(self.call("find_by_name", SearchDirectory=str(self.root),
                                   Pattern=".env"), "deny")
        self.assertEqual(self.call("multi_replace_file_content", TargetFile=str(OUTSIDE)),
                         "ask")
        self.assertEqual(self.call("codebase_search", Query="x",
                                   TargetDirectories=[str(OUTSIDE.parent)]), "ask")
        self.assertIsNone(self.call("view_file_outline", AbsolutePath=str(self.root / "app.py")))
        self.assertIsNone(self.call("browser_click_element", Index=3))
        self.assertIsNone(self.call("notify_user"))

    def test_agent_folders(self):
        plan = self.artifacts / "implementation_plan.md"
        self.assertIsNone(self.verdict("ide", "write_to_file", TargetFile=plan))
        skill = PLUGIN / "skills" / "idea" / "SKILL.md"
        self.assertIsNone(self.verdict("ide", "view_file", AbsolutePath=skill))
        builtin = Path.home() / ".gemini" / "antigravity" / "builtin" / "skills" / "x" / "SKILL.md"
        self.assertIsNone(self.verdict("app", "read_file", Path=builtin))
        settings = Path.home() / ".gemini" / "config" / "config.json"
        self.assertEqual(self.verdict("app", "write_file", Path=settings), "ask")

    def test_guard_output(self):
        def guard(**args):
            return run_hook("guard", self.payload("app", "run_command", **args),
                            "--host", "antigravity")
        self.assertEqual(guard(CommandLine="git status"), {"decision": "allow"})
        asked = guard(CommandLine="git push")
        self.assertEqual(asked["decision"], "deny")  # Antigravity shows no prompt for ask
        self.assertIn("Antigravity hooks cannot ask", asked["reason"])
        self.assertIn("pushes to the main branch", asked["reason"])
        self.assertEqual(guard(CommandLine="git clean -fd")["decision"], "deny")

    def test_session_start(self):
        def context():
            output = run_hook("session-start", self.payload("ide", "SessionStart"),
                              "--host", "antigravity")
            steps = output.get("injectSteps", [])
            return steps[0]["systemMessage"]["systemMessage"] if steps else None
        self.assertIn("Next step: add the save button", context())
        os.remove(self.root / "docs" / "TASKS.md")
        self.assertIsNone(context())

    def test_stop_sends_back_once_per_run(self):
        def stop(run, reason="NO_TOOL_CALL"):
            payload = self.payload("app", "Stop")
            payload.update(executionNum=run, terminationReason=reason)
            return run_hook("stop", payload, "--host", "antigravity")["decision"]
        self.assertEqual(stop(0), "stop")
        (self.root / "app.py").write_text("print('changed')\n", encoding="utf-8")
        set_mtime(self.root / "app.py", 5)
        self.assertEqual(stop(0), "continue")
        self.assertEqual(stop(1), "stop")  # the run that was sent back may stop
        self.assertEqual(stop(2), "stop")  # the same reminder is not repeated
        (self.root / "app.py").write_text("print('again')\n", encoding="utf-8")
        set_mtime(self.root / "app.py", 10)
        self.assertEqual(stop(3), "continue")  # a newer change is checked again
        self.assertEqual(stop(5, "USER_CANCELED"), "stop")

    def test_stop_sees_work_committed_in_the_conversation(self):
        run_hook("session-start", self.payload("app", "SessionStart"), "--host", "antigravity")
        (self.root / "app.py").write_text("print('changed')\n", encoding="utf-8")
        git(self.root, "commit", "-q", "-a", "-m", "change")
        output = run_hook("stop", self.payload("app", "Stop"), "--host", "antigravity")
        self.assertEqual(output["decision"], "continue")
        self.assertIn("committed in this session", output["reason"])


class Packaging(unittest.TestCase):
    def read(self, relative):
        return json.loads((PLUGIN / relative).read_text(encoding="utf-8"))

    def test_versions_match(self):
        versions = {self.read(manifest)["version"] for manifest in
                    [".claude-plugin/plugin.json", ".codex-plugin/plugin.json",
                     ".antigravity-plugin/plugin.json"]}
        self.assertEqual(len(versions), 1, versions)

    def test_each_tool_keeps_its_own_hooks(self):
        self.assertEqual(self.read(".codex-plugin/plugin.json")["hooks"],
                         "./hooks/codex-hooks.json")
        for relative in ["hooks/hooks.json", "hooks/codex-hooks.json"]:
            self.assertNotIn("antigravity", (PLUGIN / relative).read_text(encoding="utf-8"))
        self.assertNotIn("codex", (PLUGIN / "hooks/hooks.json").read_text(encoding="utf-8"))
        codex_start = self.read("hooks/codex-hooks.json")["hooks"]["SessionStart"][0]["hooks"][0]
        self.assertIn("session-start --host codex", codex_start["command"])
        self.assertIn("'session-start','--host','codex'", codex_start["commandWindows"])
        hooks_spec = self.read("hooks.json")["studio"]
        commands = [hooks_spec["SessionStart"][0]["command"],
                    hooks_spec["PreToolUse"][0]["hooks"][0]["command"],
                    hooks_spec["Stop"][0]["command"]]
        for command, name in zip(commands, ["session-start", "guard", "stop"]):
            self.assertEqual(command, f"python hooks/studio_hooks.py {name} "
                                      "--host antigravity || exit 0")

    def run_like_antigravity(self, command, payload):
        """Antigravity runs a hook through cmd /c (sh -c elsewhere) in the plugin folder."""
        command = command.replace("python ", f'"{sys.executable}" ', 1)
        shell = f'cmd /s /c "{command}"' if os.name == "nt" else ["sh", "-c", command]
        return subprocess.run(shell, cwd=PLUGIN, input=json.dumps(payload),
                              capture_output=True, text=True, timeout=30)

    def test_antigravity_command_line(self):
        command = self.read("hooks.json")["studio"]["PreToolUse"][0]["hooks"][0]["command"]
        payload = {"toolCall": {"name": "run_command", "args": {"CommandLine": "git status"}},
                   "workspacePaths": [str(PLUGIN)]}
        result = self.run_like_antigravity(command, payload)
        self.assertEqual(json.loads(result.stdout), {"decision": "allow"})
        # Without a working Python the hook says nothing, which Antigravity reads as allow.
        broken = self.run_like_antigravity(command.replace("studio_hooks.py", "missing.py"),
                                           payload)
        self.assertEqual((broken.returncode, broken.stdout.strip()), (0, ""))


if __name__ == "__main__":
    unittest.main()
