from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _minimal_source(root: Path) -> Path:
    source = root / "source"
    _write(source / "AGENTS.md", "candidate agents\n")
    _write(source / "CLAUDE.md", "@AGENTS.md\n")
    _write(source / "docs" / "POLICY.md", "policy\n")
    _write(
        source / ".agents" / "skills" / "demo" / "SKILL.md",
        "---\nname: demo\ndescription: test\n---\n",
    )
    _write(source / ".claude" / "commands" / "demo.md", "demo\n")
    _write(source / ".claude" / "agents" / "executor.md", "default role\n")
    _write(source / ".codex" / "agents" / "executor.toml", 'name = "executor"\n')
    return source


def _git_bash() -> Path | None:
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "Git"
        / "bin"
        / "bash.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "Git"
        / "usr"
        / "bin"
        / "bash.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    found = shutil.which("bash")
    return Path(found) if found and os.name != "nt" else None


def _shell_path(path: Path) -> str:
    resolved = path.resolve()
    if os.name != "nt":
        return str(resolved)
    drive = resolved.drive.rstrip(":").lower()
    tail = resolved.as_posix().split(":", 1)[1]
    return f"/{drive}{tail}"


class InstallerTests(unittest.TestCase):
    def _assert_lifecycle(self, invoke) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = _minimal_source(root)
            target = root / "target"
            target.mkdir()
            _write(target / "project.txt", "keep\n")

            dry = invoke(source, target, ["dry-run"])
            self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)
            self.assertIn("nothing was changed", dry.stdout)
            self.assertFalse((target / ".agent-toolkit-manifest.tsv").exists())

            first = invoke(source, target, [])
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertEqual((target / "project.txt").read_text(encoding="utf-8"), "keep\n")
            self.assertFalse((target / ".git").exists())
            self.assertTrue((target / ".agent-toolkit-manifest.tsv").exists())
            self.assertTrue((target / ".claude" / "skills" / "demo" / "SKILL.md").exists())
            self.assertIn(
                ".agent-toolkit-backup/",
                (target / ".gitignore").read_text(encoding="utf-8"),
            )

            second = invoke(source, target, [])
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("UNCHANGED", second.stdout)

            _write(source / ".claude" / "agents" / "executor.md", "updated role\n")
            role_update = invoke(source, target, [])
            self.assertEqual(
                role_update.returncode, 0, role_update.stdout + role_update.stderr
            )
            self.assertEqual(
                (target / ".claude" / "agents" / "executor.md").read_text(
                    encoding="utf-8"
                ),
                "updated role\n",
            )

            before_agents = (target / "AGENTS.md").read_bytes()
            _write(target / "docs" / "POLICY.md", "local customization\n")
            _write(source / "AGENTS.md", "candidate agents v2\n")
            conflict = invoke(source, target, [])
            self.assertEqual(conflict.returncode, 2, conflict.stdout + conflict.stderr)
            self.assertIn("locally modified", conflict.stdout + conflict.stderr)
            self.assertEqual((target / "AGENTS.md").read_bytes(), before_agents)

            _write(target / "docs" / "POLICY.md", "policy\n")
            authoritative = invoke(source, target, [])
            self.assertEqual(
                authoritative.returncode, 0, authoritative.stdout + authoritative.stderr
            )
            self.assertEqual(
                (target / "AGENTS.md").read_text(encoding="utf-8"), "candidate agents v2\n"
            )

    def test_powershell_lifecycle(self) -> None:
        executable = shutil.which("powershell.exe") or shutil.which("pwsh")
        if not executable:
            self.skipTest("PowerShell is unavailable")

        def invoke(source: Path, target: Path, flags: list[str]):
            args = [
                executable,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ROOT / "install.ps1"),
                "-Source",
                str(source),
            ]
            if "dry-run" in flags:
                args.append("-DryRun")
            return subprocess.run(
                args,
                cwd=target,
                text=True,
                capture_output=True,
                timeout=60,
                check=False,
            )

        self._assert_lifecycle(invoke)

    def test_bash_lifecycle(self) -> None:
        executable = _git_bash()
        if not executable:
            self.skipTest("Bash is unavailable")

        def invoke(source: Path, target: Path, flags: list[str]):
            args = [
                str(executable),
                _shell_path(ROOT / "install.sh"),
                "--source",
                _shell_path(source),
            ]
            if "dry-run" in flags:
                args.append("--dry-run")
            return subprocess.run(
                args,
                cwd=target,
                text=True,
                capture_output=True,
                timeout=60,
                check=False,
            )

        self._assert_lifecycle(invoke)

    def test_legacy_hash_matches_available_baseline(self) -> None:
        legacy = ROOT / "AGENTS_WORKFLOW_LEGACY" / "AGENTS_v1.md"
        if not legacy.exists():
            self.skipTest("legacy baseline is not present in this checkout")
        legacy_bytes = legacy.read_bytes().replace(b"\r\n", b"\n")
        digests = {
            hashlib.sha256(legacy_bytes).hexdigest(),
            hashlib.sha256(legacy_bytes.replace(b"\n", b"\r\n")).hexdigest(),
        }
        for name in ("install.ps1", "install.sh"):
            installer = (ROOT / name).read_text(encoding="utf-8").lower()
            for digest in digests:
                self.assertIn(digest, installer, name)

    def test_installers_fetch_only_the_pinned_toolkit_repo(self) -> None:
        for name in ("install.ps1", "install.sh"):
            text = (ROOT / name).read_text(encoding="utf-8").lower()
            self.assertIn("git clone", text, name)
            self.assertIn("https://github.com/", text, name)
            self.assertIn("evgenver/agents-tollkit", text, name)

    def test_legacy_migration_is_automatic_and_creates_backup(self) -> None:
        legacy = ROOT / "AGENTS_WORKFLOW_LEGACY" / "AGENTS_v1.md"
        powershell = shutil.which("powershell.exe") or shutil.which("pwsh")
        bash = _git_bash()
        if not legacy.exists() or (not powershell and not bash):
            self.skipTest("legacy baseline or installer shells are unavailable")

        installers = []
        if powershell:
            installers.append(
                (
                    "powershell",
                    lambda source, target, migrate: subprocess.run(
                        [
                            powershell,
                            "-NoProfile",
                            "-ExecutionPolicy",
                            "Bypass",
                            "-File",
                            str(ROOT / "install.ps1"),
                            "-Source",
                            str(source),
                            *(["-MigrateLegacy"] if migrate else []),
                        ],
                        cwd=target,
                        text=True,
                        capture_output=True,
                        timeout=60,
                        check=False,
                    ),
                )
            )
        if bash:
            installers.append(
                (
                    "bash",
                    lambda source, target, migrate: subprocess.run(
                        [
                            str(bash),
                            _shell_path(ROOT / "install.sh"),
                            "--source",
                            _shell_path(source),
                            *(["--migrate-legacy"] if migrate else []),
                        ],
                        cwd=target,
                        text=True,
                        capture_output=True,
                        timeout=60,
                        check=False,
                    ),
                )
            )

        for name, invoke in installers:
            with self.subTest(installer=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                source = _minimal_source(root)
                target = root / "target"
                target.mkdir()
                shutil.copy2(legacy, target / "AGENTS.md")
                _write(target / "project.txt", "keep\n")

                migrated = invoke(source, target, False)
                self.assertEqual(migrated.returncode, 0, migrated.stdout + migrated.stderr)
                backups = list(
                    (target / ".agent-toolkit-backup").glob("*/AGENTS.md")
                )
                self.assertEqual(len(backups), 1)
                self.assertEqual(
                    hashlib.sha256(backups[0].read_bytes()).hexdigest(),
                    hashlib.sha256(legacy.read_bytes()).hexdigest(),
                )
                self.assertEqual(
                    (target / "project.txt").read_text(encoding="utf-8"), "keep\n"
                )

    def test_previous_modular_migration_creates_backup(self) -> None:
        powershell = shutil.which("powershell.exe") or shutil.which("pwsh")
        bash = _git_bash()
        if not powershell and not bash:
            self.skipTest("no supported installer shell is available")

        old_agents = subprocess.check_output(
            ["git", "show", "59f7cbc:AGENTS.md"], cwd=ROOT
        )
        old_skill = subprocess.check_output(
            [
                "git",
                "show",
                "59f7cbc:.agents/skills/ai-eval-design/SKILL.md",
            ],
            cwd=ROOT,
        )
        old_workflows = subprocess.check_output(
            ["git", "show", "59f7cbc:docs/AGENT_WORKFLOWS.md"], cwd=ROOT
        )
        old_bug_skill = subprocess.check_output(
            ["git", "show", "59f7cbc:.agents/skills/bug-forensics/SKILL.md"],
            cwd=ROOT,
        )
        installers = []
        if powershell:
            installers.append(
                (
                    "powershell",
                    lambda source, target: subprocess.run(
                        [
                            powershell,
                            "-NoProfile",
                            "-ExecutionPolicy",
                            "Bypass",
                            "-File",
                            str(ROOT / "install.ps1"),
                            "-Source",
                            str(source),
                        ],
                        cwd=target,
                        text=True,
                        capture_output=True,
                        timeout=60,
                        check=False,
                    ),
                )
            )
        if bash:
            installers.append(
                (
                    "bash",
                    lambda source, target: subprocess.run(
                        [
                            str(bash),
                            _shell_path(ROOT / "install.sh"),
                            "--source",
                            _shell_path(source),
                        ],
                        cwd=target,
                        text=True,
                        capture_output=True,
                        timeout=60,
                        check=False,
                    ),
                )
            )

        for name, invoke in installers:
            with self.subTest(installer=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                source = ROOT
                target = root / "target"
                target.mkdir()
                old_agents_custom = old_agents + b"\nlocal customization\n"
                (target / "AGENTS.md").write_bytes(old_agents_custom)
                skill_target = target / ".claude" / "skills" / "ai-eval-design" / "SKILL.md"
                skill_target.parent.mkdir(parents=True, exist_ok=True)
                skill_target.write_bytes(old_skill)
                workflows_target = target / "docs" / "AGENT_WORKFLOWS.md"
                workflows_target.parent.mkdir(parents=True, exist_ok=True)
                workflows_target.write_bytes(old_workflows)
                bug_skill_target = target / ".agents" / "skills" / "bug-forensics" / "SKILL.md"
                bug_skill_target.parent.mkdir(parents=True, exist_ok=True)
                bug_skill_target.write_bytes(old_bug_skill)
                _write(target / "project.txt", "keep\n")

                migrated = invoke(source, target)
                self.assertEqual(migrated.returncode, 0, migrated.stdout + migrated.stderr)
                backups = list(
                    (target / ".agent-toolkit-backup").glob("*/AGENTS.md")
                )
                self.assertEqual(len(backups), 1)
                self.assertEqual(backups[0].read_bytes(), old_agents_custom)
                self.assertEqual(
                    (target / "project.txt").read_text(encoding="utf-8"), "keep\n"
                )


if __name__ == "__main__":
    unittest.main()
