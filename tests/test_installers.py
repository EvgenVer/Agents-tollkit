from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEMP = ROOT / ".artifacts" / "tests"
TEMP.mkdir(parents=True, exist_ok=True)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def source_at(root):
    source = root / "source with spaces"
    for relative, text in {
        "AGENTS.md": "candidate rules\n",
        "CLAUDE.md": "@AGENTS.md\n",
        ".agents/docs/AGENT_WORKFLOWS.md": "workflow\n",
        ".agents/skills/demo/SKILL.md": "---\nname: demo\ndescription: demo\n---\n",
        ".claude/commands/demo.md": "command\n",
        ".claude/agents/executor.md": "model: sonnet\n",
        ".codex/agents/executor.toml": 'name = "executor"\n',
        ".agents/skills/demo/__pycache__/demo.pyc": "skip\n",
    }.items():
        write(source / relative, text)
    return source


def git_bash():
    if os.name == "nt":
        for sub in ("bin", "usr/bin"):
            path = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git" / sub / "bash.exe"
            if path.exists():
                return str(path)
        return None
    return shutil.which("bash")


def shell_path(path):
    value = path.resolve().as_posix()
    return "/" + value[0].lower() + value[2:] if os.name == "nt" else value


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file() and not p.is_symlink()}


class InstallerTests(unittest.TestCase):
    def exercise(self, shell):
        with tempfile.TemporaryDirectory(dir=TEMP) as temp:
            root = Path(temp)
            source = source_at(root)
            target = root / "target with spaces"
            target.mkdir()
            write(target / "README.md", "# My project\n")
            write(target / ".gitignore", "custom-cache/\n")
            (target / ".git").mkdir()
            before = snapshot(target)

            def invoke(*flags, selected_source=source):
                if shell == "powershell":
                    exe = shutil.which("pwsh") or shutil.which("powershell")
                    if not exe:
                        self.skipTest("PowerShell unavailable")
                    args = [exe, "-NoProfile", "-NonInteractive", "-File", str(ROOT / "install.ps1"),
                            "-Source", str(selected_source)]
                    args += [{"dry": "-DryRun", "legacy": "-MigrateLegacy"}[f] for f in flags]
                else:
                    exe = git_bash()
                    if not exe:
                        self.skipTest("Bash unavailable")
                    args = [exe, shell_path(ROOT / "install.sh"), "--source", shell_path(selected_source)]
                    args += [{"dry": "--dry-run", "legacy": "--migrate-legacy"}[f] for f in flags]
                env = dict(os.environ, TMP=str(TEMP), TEMP=str(TEMP), TMPDIR=shell_path(TEMP))
                return subprocess.run(args, cwd=target, capture_output=True, text=True,
                                      encoding="utf-8", errors="replace", timeout=90, env=env)

            for flag in ("legacy",):
                result = invoke(flag)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("README", result.stdout + result.stderr)
                self.assertEqual(snapshot(target), before)
            result = invoke("dry")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("nothing was changed", result.stdout)
            self.assertEqual(snapshot(target), before)
            # Application files cause refusal even if a toolkit source is unavailable.
            write(target / "app.py", "print('application')\n")
            app_snapshot = snapshot(target)
            result = invoke(selected_source=root / "missing")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Existing project", result.stdout + result.stderr)
            self.assertEqual(snapshot(target), app_snapshot)
            (target / "app.py").unlink()
            for marker in ("PLAN.md", "TASKS.md", "AGENTS.md", "CLAUDE.md", ".agent-toolkit-manifest.tsv"):
                write(target / marker, "existing project state\n")
                existing = snapshot(target)
                result = invoke("dry")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Existing project", result.stdout + result.stderr)
                self.assertEqual(snapshot(target), existing)
                (target / marker).unlink()
            # A nested protected source is refused before any install writes.
            write(source / ".agents" / ".env.fixture", "SYNTHETIC_SENTINEL\n")
            result = invoke()
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("SYNTHETIC_SENTINEL", result.stdout + result.stderr)
            self.assertEqual(snapshot(target), before)
            (source / ".agents" / ".env.fixture").unlink()
            # A source hardlink is also refused before any install writes.
            original = root / "ordinary-source.txt"
            original.write_text("synthetic link fixture", encoding="utf-8")
            linked = source / ".agents" / "linked.md"
            os.link(original, linked)
            result = invoke()
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(snapshot(target), before)
            linked.unlink()
            result = invoke()
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for name, data in before.items():
                self.assertEqual((target / name).read_bytes(), data)
            self.assertTrue((target / ".agents/docs/AGENT_WORKFLOWS.md").exists())
            self.assertTrue((target / ".claude/skills/demo/SKILL.md").exists())
            self.assertTrue((target / ".codex/agents/executor.toml").exists())
            self.assertFalse((target / "docs").exists())
            self.assertFalse((target / ".agents/skills/demo/__pycache__").exists())
            self.assertFalse((target / "PLAN.md").exists())
            self.assertIn("local-unversioned", (target / ".agent-toolkit-manifest.tsv").read_text(encoding="utf-8"))
            installed = snapshot(target)
            result = invoke()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Existing project", result.stdout + result.stderr)
            self.assertEqual(snapshot(target), installed)

    def test_powershell_clean_install_and_refusals(self):
        self.exercise("powershell")

    def test_bash_clean_install_and_refusals(self):
        self.exercise("bash")

    def test_bash_download_uses_physical_temporary_directory(self):
        bash = git_bash()
        if not bash:
            self.skipTest("Bash unavailable")
        with tempfile.TemporaryDirectory(dir=TEMP) as temp:
            root = Path(temp)
            source = source_at(root)
            physical = root / "physical-temp"
            physical.mkdir()
            linked = root / "linked-temp"
            try:
                linked.symlink_to(physical, target_is_directory=True)
            except OSError:
                self.skipTest("Directory symlinks unavailable on this Windows host")
            target = root / "target"
            target.mkdir()
            script = root / "standalone/install.sh"
            script.parent.mkdir()
            shutil.copyfile(ROOT / "install.sh", script)
            shim = root / "bin/git"
            write(shim, '#!/bin/sh\n[ "$1" = clone ] || exit 1\n'
                  'for destination do :; done\n'
                  'cp -R "$INSTALL_TEST_SOURCE/." "$destination"\n')
            shim.chmod(0o755)
            env = dict(os.environ, PATH=shell_path(shim.parent) + ":" + os.environ.get("PATH", ""),
                       INSTALL_TEST_SOURCE=shell_path(source))
            # Do not resolve the synthetic link before giving it to the installer.
            logical = linked.absolute().as_posix()
            env["TMPDIR"] = "/" + logical[0].lower() + logical[2:] if os.name == "nt" else logical
            env.pop("TK_SRC", None)
            result = subprocess.run([bash, shell_path(script)], cwd=target, env=env,
                                    capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((target / "AGENTS.md").exists())
            self.assertEqual(list(physical.iterdir()), [])

    def test_real_toolkit_install_matches_both_skill_copies(self):
        exe = shutil.which("pwsh") or shutil.which("powershell")
        if not exe:
            self.skipTest("PowerShell unavailable")
        with tempfile.TemporaryDirectory(dir=TEMP) as temp:
            target = Path(temp)
            result = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-File", str(ROOT / "install.ps1"),
                                     "-Source", str(ROOT)], cwd=target, capture_output=True,
                                    text=True, encoding="utf-8", errors="replace", timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for original in (ROOT / ".agents/skills").glob("*/SKILL.md"):
                for directory in (".agents/skills", ".claude/skills"):
                    self.assertEqual(original.read_bytes(),
                        (target / directory / original.parent.name / "SKILL.md").read_bytes())
            manifest = (target / ".agent-toolkit-manifest.tsv").read_text(encoding="utf-8")
            self.assertIn("# source: git:", manifest)
            self.assertFalse((target / "docs").exists())


if __name__ == "__main__":
    unittest.main()
