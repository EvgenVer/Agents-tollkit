from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents/skills/planning/scripts/check_docs.py"
EXAMPLE = ROOT / ".agents/skills/planning/examples/reading-list"
spec = importlib.util.spec_from_file_location("check_docs", SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class DocumentChecks(unittest.TestCase):
    def setUp(self):
        parent = ROOT / ".artifacts/tests"
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "project"
        shutil.copytree(EXAMPLE, self.project)

    def change(self, name, old, new):
        path = self.project / name
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def check(self):
        return checker.inspect_project(self.project)

    def test_example_ready_order_and_no_future_placeholder_tasks(self):
        result = self.check()
        self.assertTrue(result["valid"], result["diagnostics"])
        self.assertEqual(result["ready_tasks"], ["T3", "T5"])
        self.assertEqual(result["phases"][-1]["state"], "not decomposed")

    def test_both_cli_operations_are_read_only(self):
        before = {p.relative_to(self.project): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        for operation in ("check", "status"):
            run = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), operation,
                                  "--root", str(self.project), "--json"], capture_output=True,
                                 text=True, encoding="utf-8", timeout=15)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertTrue(json.loads(run.stdout)["valid"])
        after = {p.relative_to(self.project): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_insertion_prerequisite_blocks_dependent_until_verified(self):
        self.change("TASKS.md", "| T4 |", "| T3.1 | Escape link syntax | todo | T3 | Check: escaped output; Result: pending |\n| T4 |")
        self.change("TASKS.md", "| todo | T3 | Check: CLI", "| todo | T3, T3.1 | Check: CLI")
        self.change("TASKS.md", "| T3 | Render records as ordered Markdown links | todo |", "| T3 | Render records as ordered Markdown links | done |")
        self.change("TASKS.md", "expected document; Result: pending", "expected document; Result: passed — fixture assertion")
        self.assertEqual(self.check()["ready_tasks"], ["T3.1", "T5"])

    def test_blocked_task_does_not_block_independent_task(self):
        self.change("TASKS.md", "| T3 | Render records as ordered Markdown links | todo |", "| T3 | Render records as ordered Markdown links | blocked |")
        with (self.project / "TASKS.md").open("a", encoding="utf-8") as handle:
            handle.write("\n- T3: Reason: required rendering decision is unanswered\n")
        result = self.check()
        self.assertTrue(result["valid"], result["diagnostics"])
        self.assertEqual(result["ready_tasks"], ["T5"])

    def test_dependency_cycles_and_forward_order_are_rejected(self):
        self.change("TASKS.md", "| todo | T2 | Check: compare full", "| todo | T4 | Check: compare full")
        result = self.check()
        self.assertFalse(result["valid"])
        self.assertTrue(any("cycle" in d["message"] for d in result["diagnostics"]))
        self.assertEqual(result["ready_tasks"], [])

    def test_cancelled_dependency_is_not_complete(self):
        self.change("TASKS.md", "| T2 | Reject missing columns and malformed rows with useful errors | done |", "| T2 | Reject missing columns and malformed rows with useful errors | cancelled |")
        with (self.project / "TASKS.md").open("a", encoding="utf-8") as handle:
            handle.write("\n- T2: Reason: requested cancellation; dependent work must be reconciled\n")
        self.assertFalse(self.check()["valid"])

    def test_pending_command_cannot_be_evidence_for_done(self):
        self.change("TASKS.md", "| T3 | Render records as ordered Markdown links | todo |", "| T3 | Render records as ordered Markdown links | done |")
        self.assertFalse(self.check()["valid"])

    def test_historical_evidence_gap_is_disclosed_not_used_as_dependency_pass(self):
        self.change("TASKS.md", "Result: passed — illustrative validation", "Result: unverified — illustrative validation")
        result = self.check()
        self.assertTrue(any(d["level"] == "warning" for d in result["diagnostics"]))
        self.assertEqual(result["ready_tasks"], [])

    def test_multiple_doing_rows_require_matching_current_references(self):
        self.change("TASKS.md", "| T3 | Render records as ordered Markdown links | todo |", "| T3 | Render records as ordered Markdown links | doing |")
        self.assertFalse(self.check()["valid"])
        self.change("TASKS.md", "Current task: none", "Current task: T3")
        self.assertTrue(self.check()["valid"])

    def test_phase_prerequisite_evidence_blocks_otherwise_independent_tasks(self):
        self.change("TASKS.md", "Result: passed — illustrative validation", "Result: unverified — illustrative validation")
        self.change("TASKS.md", "| todo | T2 |", "| todo | none |")
        result = self.check()
        self.assertEqual(result["ready_tasks"], [])
        self.assertEqual(result["phases"][1]["state"], "waiting for phases")

    def test_future_phase_is_waiting_when_prior_phase_is_unfinished(self):
        self.change("TASKS.md", "Current phase: 2", "Current phase: 1")
        self.change("TASKS.md", "| T2 | Reject missing columns and malformed rows with useful errors | done |", "| T2 | Reject missing columns and malformed rows with useful errors | todo |")
        self.change("TASKS.md", "| todo | T2 |", "| todo | none |")
        result = self.check()
        self.assertTrue(result["valid"], result["diagnostics"])
        self.assertEqual(result["phases"][1]["state"], "waiting for phases")

    def test_phase_must_be_decomposed_before_activation(self):
        self.change("TASKS.md", "Current phase: 2", "Current phase: 3")
        self.assertFalse(self.check()["valid"])

    def test_numeric_suffix_order_not_lexicographic(self):
        rows = ("| T3.2 | First insertion | todo | T3 | Check: first outcome; Result: pending |\n"
                "| T3.10 | Later insertion | todo | T3 | Check: later outcome; Result: pending |\n")
        self.change("TASKS.md", "| T4 |", rows + "| T4 |")
        self.assertTrue(self.check()["valid"])
        self.change("TASKS.md", rows, "\n".join(reversed(rows.rstrip().splitlines())) + "\n")
        self.assertFalse(self.check()["valid"])

    def test_legacy_completed_id_and_deeper_suffix_are_rejected(self):
        for invalid in ("OLD-1.2.3", "T1.2.3", "T01"):
            with self.subTest(invalid=invalid):
                self.change("TASKS.md", "| T1 |", f"| {invalid} |")
                self.assertFalse(self.check()["valid"])
                self.change("TASKS.md", f"| {invalid} |", "| T1 |")

    def test_migration_mapping_is_history_and_targets_must_resolve(self):
        with (self.project / "TASKS.md").open("a", encoding="utf-8") as handle:
            handle.write("\n### ID changes\n\n| Previous reference | Current reference |\n|---|---|\n| old-A.4 | T3 |\n")
        self.assertTrue(self.check()["valid"])
        self.change("TASKS.md", "| old-A.4 | T3 |", "| old-A.4 | T99 |")
        self.assertFalse(self.check()["valid"])

    def test_broken_table_and_duplicate_ids_report_errors(self):
        self.change("TASKS.md", "| T5 |", "| T3 |")
        self.assertFalse(self.check()["valid"])
        self.change("PLAN.md", "| Phase | Outcome | After | Completion check |", "| Phase | Outcome | Status | After | Completion check |")
        self.assertFalse(self.check()["valid"])

    def test_phase_closure_reuses_checks_without_extra_task(self):
        self.change("TASKS.md", "| todo |", "| done |")
        self.change("TASKS.md", "Result: pending", "Result: passed — fixture assertion")
        result = self.check()
        self.assertTrue(result["valid"], result["diagnostics"])
        self.assertEqual(len(result["tasks"]), 5)
        self.assertEqual(result["phases"][1]["state"], "checks recorded")
        self.assertEqual(result["phases"][2]["state"], "not decomposed")

    def test_missing_docs_are_errors_without_creating_files(self):
        (self.project / "DESCRIPTION.md").unlink()
        self.assertFalse(self.check()["valid"])
        self.assertFalse((self.project / "DESCRIPTION.md").exists())

    def test_fenced_examples_do_not_become_live_tasks(self):
        with (self.project / "TASKS.md").open("a", encoding="utf-8") as handle:
            handle.write("\n```markdown\n### Phase 99\n| T999 | fake |\n```\n")
        self.assertTrue(self.check()["valid"])

    def test_hardlinked_document_is_rejected_before_open(self):
        path = self.project / "DESCRIPTION.md"
        alias = Path(self.temp.name) / "alias.md"
        try:
            os.link(path, alias)
        except OSError as exc:
            self.skipTest(f"Hardlinks unavailable: {exc}")
        with patch.object(checker.os, "open", side_effect=AssertionError("must not open linked contents")):
            with self.assertRaises(ValueError):
                checker.read_document(self.project, "DESCRIPTION.md")

    def test_protected_directory_is_rejected_without_filesystem_access(self):
        for name in ("secrets", ".ssh", ".aws", ".env.local", "credentials"):
            with self.subTest(name=name), patch.object(checker, "linked", side_effect=AssertionError("must reject before inspection")):
                with self.assertRaises(ValueError):
                    checker.read_document(self.project / name, "TASKS.md")

    def test_symlinked_document_is_rejected_before_open(self):
        path = self.project / "DESCRIPTION.md"
        original = path.read_text(encoding="utf-8")
        path.unlink()
        outside = Path(self.temp.name) / "outside.md"
        outside.write_text(original, encoding="utf-8")
        try:
            path.symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"Symlinks unavailable: {exc}")
        with patch.object(checker.os, "open", side_effect=AssertionError("must not follow links")):
            with self.assertRaises(ValueError):
                checker.read_document(self.project, "DESCRIPTION.md")


if __name__ == "__main__":
    unittest.main()
