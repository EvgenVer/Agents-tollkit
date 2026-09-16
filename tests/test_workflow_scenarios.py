"""Offline tests of fixtures/graders. These are not live model pass results."""
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from evals import runner

ROOT = runner.ROOT
TEMP = ROOT / ".artifacts/tests"
TEMP.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location(
    "scenario_checker", ROOT / ".agents/skills/planning/scripts/check_docs.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class WorkflowScenarios(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=TEMP)
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / "workspace"

    def copy(self, fixture):
        shutil.copytree(ROOT / "evals/fixtures" / fixture, self.workspace)

    def grade(self, case):
        state = runner._snapshot(self.workspace)
        stub = runner.ProviderResult(status="success", exit_code=0, duration_ms=1)
        return runner._grade(case, "candidate", self.workspace, state, state, stub)

    def test_all_initial_canonical_fixtures_are_valid(self):
        for root in (ROOT / "evals/fixtures").iterdir():
            if (root / "TASKS.md").exists() and root.name != "legacy-update":
                with self.subTest(fixture=root.name):
                    result = checker.inspect_project(root)
                    self.assertTrue(result["valid"], result["diagnostics"])

    def test_completed_code_does_not_hide_stale_task_ledger(self):
        self.copy("phase-continuation")
        (self.workspace / "src/formatter.py").write_text(
            'from collections import Counter\n'
            'def normalize(value): return " ".join(value.casefold().split())\n'
            'def summarize(value): return dict(Counter(normalize(value).split()))\n',
            encoding="utf-8")
        case = next(c for c in runner._load_cases() if c["id"] == "phase-continuation")
        result = self.grade(case)
        self.assertFalse(result.passed)
        checks = {c["name"]: c["passed"] for c in result.checks}
        self.assertTrue(checks["hidden tests"])
        self.assertFalse(checks["phase 2 recorded complete"])

    def test_done_claims_cannot_hide_unimplemented_code(self):
        self.copy("phase-continuation")
        path = self.workspace / "TASKS.md"
        text = path.read_text(encoding="utf-8").replace("| todo |", "| done |")
        text = text.replace("Result: pending", "Result: passed — synthetic claim")
        text += ("\n### Phase 2\n\n"
            "| ID | Task | Status | After | Verification |\n"
            "|---|---|---|---|---|\n"
            "| T2 | Frequency report | done | T1 | Check: word counts; Result: passed — synthetic claim |")
        path.write_text(text, encoding="utf-8")
        case = next(c for c in runner._load_cases() if c["id"] == "phase-continuation")
        result = self.grade(case)
        self.assertFalse(result.passed)
        self.assertFalse(next(c["passed"] for c in result.checks if c["name"] == "hidden tests"))

    def test_empty_contract_still_checks_structure(self):
        self.copy("bounded-correction")
        result = self.grade({"grade": {"document_contract": {}}})
        self.assertFalse(result.passed)
        self.assertFalse(next(c["passed"] for c in result.checks if c["name"] == "canonical documents"))

    def test_insertion_requires_actual_dependency(self):
        self.copy("insert-prerequisite")
        case = {"grade": {"document_contract": {"tasks": {"T8": {"after": ["T7.1"]}}}}}
        self.assertFalse(self.grade(case).passed)

    def test_independent_task_must_not_depend_on_the_blocker(self):
        self.copy("blocked-independent")
        path = self.workspace / "TASKS.md"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "| T2 | Correct the local README spelling | todo | none |",
            "| T2 | Correct the local README spelling | todo | T1 |"), encoding="utf-8")
        case = {"grade": {"document_contract": {"tasks": {"T2": {"after": []}}}}}
        self.assertFalse(self.grade(case).passed)

    def test_checker_rejects_completed_work_with_a_blocked_prerequisite(self):
        self.copy("blocked-independent")
        path = self.workspace / "TASKS.md"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "| T2 | Correct the local README spelling | todo | none |",
            "| T2 | Correct the local README spelling | done | T1 |").replace(
            "Check: README contains the toolkit; Result: pending",
            "Check: README contains the toolkit; Result: passed — synthetic claim"), encoding="utf-8")
        result = checker.inspect_project(self.workspace)
        self.assertFalse(result["valid"])
        self.assertTrue(any("unfinished prerequisite" in d["message"] for d in result["diagnostics"]))

    def test_benchmark_fingerprint_changes_with_candidate_rules(self):
        self.workspace.mkdir()
        path = self.workspace / "AGENTS.md"
        path.write_text("first instructions", encoding="utf-8")
        before = runner._benchmark_fingerprint(self.workspace)
        path.write_text("changed instructions", encoding="utf-8")
        self.assertNotEqual(before, runner._benchmark_fingerprint(self.workspace))

    def test_grader_rejects_hardlinks_before_reading_content(self):
        self.copy("bounded-correction")
        original = Path(self.temp.name) / "ordinary.txt"
        original.write_text("synthetic", encoding="utf-8")
        (self.workspace / "README.md").unlink()
        os.link(original, self.workspace / "README.md")
        with patch.object(runner, "_hash_file", side_effect=AssertionError("must not open")):
            state = runner._snapshot(self.workspace)
            self.assertEqual(state, {"README.md": "protected-or-link"})
            result = runner._grade({"grade": {"file_contains": {"README.md": "synthetic"}}},
                "candidate", self.workspace, state, state,
                runner.ProviderResult(status="success", exit_code=0, duration_ms=1))
        self.assertFalse(result.passed)

    def test_migration_requires_toolkit_backup_and_future_work(self):
        self.copy("legacy-update")
        case = next(c for c in runner._load_cases() if c["id"] == "agent-led-update")
        result = self.grade(case)
        self.assertFalse(result.passed)
        failed = {c["name"] for c in result.checks if not c["passed"]}
        self.assertIn("AGENTS.md matches reviewed source", failed)
        self.assertIn("task T2 state", failed)
        self.assertIn(".agent-toolkit-backup/*/TASKS.md preserves original", failed)

    def test_coarse_phase_rubric_rejects_premature_decomposition(self):
        self.copy("session-handoff")
        case = {"grade": {"document_contract": {"undecomposed_phases": [2]}}}
        # The fixture is intentionally missing phase 2 decomposition at entry;
        # activate it only after preparing tasks, as the workflow requires.
        path = self.workspace / "TASKS.md"
        path.write_text(path.read_text(encoding="utf-8") + ("\n### Phase 2\n\n"
            "| ID | Task | Status | After | Verification |\n|---|---|---|---|---|\n"
            "| T2 | Frequency report | todo | T1 | Check: counts; Result: pending |"), encoding="utf-8")
        self.assertFalse(self.grade(case).passed)

    def test_minimal_baseline_installs_only_entrypoints(self):
        self.workspace.mkdir()
        identity = runner._materialize_variant("minimal", self.workspace,
            legacy_file=ROOT / "AGENTS_WORKFLOW_LEGACY/AGENTS_v1.md",
            current_ref=runner.DEFAULT_CURRENT_REF, candidate_root=ROOT,
            temp_root=Path(self.temp.name))
        self.assertTrue(identity.startswith("sha256:"))
        self.assertEqual({p.name for p in self.workspace.iterdir()}, {"AGENTS.md", "CLAUDE.md"})

    def test_seeded_handoff_evidence_is_reproducible(self):
        self.copy("session-handoff")
        result = runner._run([runner.sys.executable, "-m", "unittest", "tests.test_normalize"],
                             cwd=self.workspace)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_preserved_evidence_matches_the_original_fixture(self):
        for case in runner._load_cases():
            if case["id"] in {"session-handoff", "insert-prerequisite"}:
                expected = case["grade"]["file_contains"]["TASKS.md"]
                original = (ROOT / "evals/fixtures" / case["fixture"] / "TASKS.md").read_text(encoding="utf-8")
                self.assertIn(expected, original)

    def test_optional_workspace_retention_keeps_reviewable_artifacts(self):
        with runner._temporary_eval_root(Path(self.temp.name), keep=True) as root:
            (root / "evidence.txt").write_text("synthetic", encoding="utf-8")
        self.assertTrue((root / "evidence.txt").exists())
        with runner._temporary_eval_root(Path(self.temp.name)) as removed:
            (removed / "scratch.txt").write_text("synthetic", encoding="utf-8")
        self.assertFalse(removed.exists())


if __name__ == "__main__":
    unittest.main()
