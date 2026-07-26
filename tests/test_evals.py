from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path

from evals import runner


class EvalCaseTests(unittest.TestCase):
    def test_skill_frontmatter_is_minimal(self) -> None:
        for path in (runner.ROOT / ".agents" / "skills").glob("*/SKILL.md"):
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], "---", path)
            end = lines.index("---", 1)
            keys = {
                line.split(":", 1)[0].strip()
                for line in lines[1:end]
                if ":" in line
            }
            self.assertEqual(keys, {"name", "description"}, path)

    def test_orchestration_contract_contains_benefit_controls(self) -> None:
        text = (
            runner.ROOT / ".agents" / "skills" / "orchestration" / "SKILL.md"
        ).read_text(encoding="utf-8")
        for required in (
            "ORCHESTRATION_NOT_BENEFICIAL",
            "at least three meaningful active tasks",
            "at least two tasks are ready",
            "capped at three",
            "before waiting for any result",
            "Do not dispatch a reviewer per successful task",
            "Allow one correction iteration",
        ):
            self.assertIn(required, text)

    def test_case_catalog_is_valid_and_unique(self) -> None:
        cases = runner._load_cases()
        self.assertGreaterEqual(len(cases), 9)
        self.assertEqual(len(cases), len({case["id"] for case in cases}))
        for case in cases:
            self.assertTrue((runner.ROOT / "evals" / "fixtures" / case["fixture"]).exists())
            if case.get("hidden"):
                self.assertTrue(
                    (runner.ROOT / "evals" / "hidden" / case["hidden"]).exists()
                )

    def test_known_bad_bug_fixture_fails_hidden_tests(self) -> None:
        case = next(
            item for item in runner._load_cases() if item["id"] == "bug-forensics"
        )
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            runner.shutil.copytree(
                runner.ROOT / "evals" / "fixtures" / case["fixture"], workspace
            )
            before = runner._snapshot(workspace)
            provider = runner.ProviderResult(
                status="success", exit_code=0, duration_ms=1
            )
            grade = runner._grade(
                case, "candidate", workspace, before, before, provider
            )
            self.assertFalse(grade.passed)
            hidden = next(
                check for check in grade.checks if check["name"] == "hidden tests"
            )
            self.assertFalse(hidden["passed"])

    def test_injection_marker_is_rejected(self) -> None:
        case = next(
            item for item in runner._load_cases() if item["id"] == "external-injection"
        )
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            runner.shutil.copytree(
                runner.ROOT / "evals" / "fixtures" / case["fixture"], workspace
            )
            before = runner._snapshot(workspace)
            (workspace / "INJECTION_EXECUTED").write_text("bad", encoding="utf-8")
            after = runner._snapshot(workspace)
            provider = runner.ProviderResult(
                status="success", exit_code=0, duration_ms=1
            )
            grade = runner._grade(
                case, "candidate", workspace, before, after, provider
            )
            self.assertFalse(grade.passed)

    def test_dispatch_parser_counts_only_tool_fields(self) -> None:
        events = [
            {"type": "item.started", "item": {"tool_name": "spawn_agent"}},
            {"type": "assistant", "message": "please spawn_agent someday"},
            {"type": "tool_use", "name": "Task"},
        ]
        self.assertEqual(runner._dispatch_count(events), 2)

    def test_collaboration_waits_are_separate_parallel_evidence(self) -> None:
        events = [
            {
                "type": "item.started",
                "item": {"type": "collab_tool_call", "tool": "wait"},
            },
            {
                "type": "item.completed",
                "item": {"type": "collab_tool_call", "tool": "wait"},
            },
        ]
        self.assertEqual(runner._dispatch_count(events), 0)
        self.assertEqual(runner._collaboration_wait_count(events), 1)

    def test_grade_accepts_collaboration_wait_evidence_when_spawn_is_hidden(
        self,
    ) -> None:
        case = {"grade": {"min_dispatches": 2}}
        provider = runner.ProviderResult(
            status="success",
            exit_code=0,
            duration_ms=1,
            collaboration_wait_count=2,
        )
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            grade = runner._grade(
                case, "candidate", workspace, {}, {}, provider
            )
        self.assertTrue(grade.passed)

    def test_candidate_efficiency_budgets_do_not_regrade_baselines(self) -> None:
        case = {
            "grade": {
                "candidate_max_commands": 2,
                "candidate_max_command_rounds": 1,
                "candidate_max_model_turns": 1,
                "candidate_max_skill_reads": 0,
            }
        }
        provider = runner.ProviderResult(
            status="success",
            exit_code=0,
            duration_ms=1,
            command_count=3,
            command_round_count=2,
            model_turn_count=2,
            skill_read_count=1,
        )
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            candidate = runner._grade(
                case, "candidate", workspace, {}, {}, provider
            )
            legacy = runner._grade(
                case, "legacy", workspace, {}, {}, provider
            )
        self.assertFalse(candidate.passed)
        self.assertTrue(legacy.passed)

    def test_trajectory_metrics_count_started_actions_once(self) -> None:
        events = [
            {
                "type": "item.started",
                "item": {
                    "type": "command_execution",
                    "command": (
                        "Get-Content .agents/skills/code-review/SKILL.md; "
                        "Get-Content docs/CODE_REVIEW.md; git diff"
                    ),
                },
            },
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": "same completed command",
                },
            },
            {
                "type": "item.started",
                "item": {
                    "type": "command_execution",
                    "command": "python -m unittest",
                },
            },
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": "python -m unittest",
                },
            },
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "done"},
            },
        ]
        metrics = runner._trajectory_metrics(events)
        self.assertEqual(metrics["command_count"], 2)
        self.assertEqual(metrics["command_round_count"], 2)
        self.assertEqual(metrics["model_turn_count"], 1)
        self.assertEqual(metrics["skill_read_count"], 1)
        self.assertEqual(metrics["review_skill_read_count"], 1)
        self.assertEqual(metrics["docs_read_count"], 1)
        self.assertEqual(metrics["git_command_count"], 1)

    def test_parallel_commands_share_one_round(self) -> None:
        events = [
            {
                "type": "item.started",
                "item": {"type": "command_execution", "command": "git status"},
            },
            {
                "type": "item.started",
                "item": {"type": "command_execution", "command": "rg --files"},
            },
            {
                "type": "item.completed",
                "item": {"type": "command_execution", "command": "git status"},
            },
            {
                "type": "item.completed",
                "item": {"type": "command_execution", "command": "rg --files"},
            },
        ]
        metrics = runner._trajectory_metrics(events)
        self.assertEqual(metrics["command_count"], 2)
        self.assertEqual(metrics["command_round_count"], 1)

    def test_fixture_copy_ignores_generated_python_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            cache = source / "__pycache__"
            cache.mkdir(parents=True)
            (source / "main.py").write_text("pass\n", encoding="utf-8")
            (cache / "main.pyc").write_bytes(b"generated")
            target = root / "target"

            runner._copy_path(source, target)

            self.assertTrue((target / "main.py").exists())
            self.assertFalse((target / "__pycache__").exists())

    def test_metrics_parser_uses_last_numeric_value(self) -> None:
        events = [
            {"usage": {"input_tokens": 10, "output_tokens": 2}},
            {
                "type": "result",
                "input_tokens": 20,
                "output_tokens": 4,
                "total_cost_usd": 0.25,
            },
        ]
        self.assertEqual(runner._last_numeric(events, {"input_tokens"}), 20)
        self.assertEqual(runner._last_numeric(events, {"output_tokens"}), 4)
        self.assertEqual(runner._last_numeric(events, {"total_cost_usd"}), 0.25)

    def test_aggregate_separates_cached_and_uncached_tokens(self) -> None:
        result = runner.RunResult(
            case_id="case",
            suite="workflow",
            variant="candidate",
            provider="codex",
            repetition=1,
            seed=1,
            source_identity="test",
            provider_result=runner.ProviderResult(
                status="success",
                exit_code=0,
                duration_ms=100,
                input_tokens=100,
                cached_input_tokens=80,
                output_tokens=10,
            ),
            grade=runner.GradeResult(passed=True, checks=[]),
        )
        row = runner._aggregate([result])["rows"][0]
        self.assertEqual(row["median_total_tokens"], 110)
        self.assertEqual(row["median_uncached_input_tokens"], 20)
        self.assertEqual(row["median_uncached_plus_output_tokens"], 30)

    def test_network_failure_is_infrastructure_not_behavior(self) -> None:
        self.assertTrue(
            runner._classify_infrastructure_failure(
                1,
                "stream disconnected before completion: "
                "error sending request (os error 10013)",
            )
        )
        result = runner.RunResult(
            case_id="case",
            suite="workflow",
            variant="candidate",
            provider="codex",
            repetition=1,
            seed=1,
            source_identity="test",
            provider_result=runner.ProviderResult(
                status="infrastructure_failure",
                exit_code=1,
                duration_ms=100,
            ),
            grade=runner.GradeResult(passed=False, checks=[]),
        )
        row = runner._aggregate([result])["rows"][0]
        self.assertEqual(row["valid_runs"], 0)
        self.assertIsNone(row["pass_rate"])

    def test_performance_gate_compares_orchestration_to_sequential_control(
        self,
    ) -> None:
        cases = [
            {
                "id": "parallel",
                "suite": "orchestration",
                "variants": ["current", "candidate"],
                "performance_gate": True,
                "performance_baseline_case": "parallel-sequential",
            },
            {
                "id": "parallel-sequential",
                "suite": "orchestration",
                "variants": ["candidate"],
            },
        ]
        aggregate = {
            "rows": [
                {
                    "case_id": "parallel",
                    "variant": "candidate",
                    "runs": 3,
                    "valid_runs": 3,
                    "passes": 3,
                    "pass_rate": 1.0,
                    "pass_all": True,
                    "median_duration_ms": 750,
                    "median_total_tokens": 150,
                    "median_dispatch_count": 2,
                    "median_collaboration_wait_count": 0,
                },
                {
                    "case_id": "parallel-sequential",
                    "variant": "candidate",
                    "runs": 3,
                    "valid_runs": 3,
                    "passes": 3,
                    "pass_rate": 1.0,
                    "pass_all": True,
                    "median_duration_ms": 1000,
                    "median_total_tokens": 100,
                    "median_dispatch_count": 0,
                    "median_collaboration_wait_count": 0,
                },
            ]
        }
        gates = runner._comparison_gates(
            cases, aggregate, enforce_performance=True
        )
        self.assertTrue(gates[0]["passed"])

        aggregate["rows"][0]["median_duration_ms"] = 900
        gates = runner._comparison_gates(
            cases, aggregate, enforce_performance=True
        )
        self.assertFalse(gates[0]["passed"])

    def test_materialize_legacy_creates_claude_entrypoint(self) -> None:
        legacy = runner.ROOT / "AGENTS_WORKFLOW_LEGACY" / "AGENTS_v1.md"
        if not legacy.exists():
            self.skipTest("legacy baseline is not present in this checkout")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "target"
            target.mkdir()
            identity = runner._materialize_variant(
                "legacy",
                target,
                legacy_file=legacy,
                current_ref=runner.DEFAULT_CURRENT_REF,
                candidate_root=runner.ROOT,
                temp_root=root,
            )
            self.assertTrue(identity.startswith("sha256:"))
            self.assertEqual(
                (target / "CLAUDE.md").read_text(encoding="utf-8"), "@AGENTS.md\n"
            )
            self.assertTrue((target / "AGENTS.md").exists())

    def test_pinned_current_ref_exists(self) -> None:
        resolved = runner._git("rev-parse", runner.DEFAULT_CURRENT_REF, cwd=runner.ROOT)
        self.assertTrue(resolved.startswith(runner.DEFAULT_CURRENT_REF))

    def test_candidate_materialization_generates_claude_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "target"
            target.mkdir()
            identity = runner._materialize_variant(
                "candidate",
                target,
                legacy_file=runner.ROOT
                / "AGENTS_WORKFLOW_LEGACY"
                / "AGENTS_v1.md",
                current_ref=runner.DEFAULT_CURRENT_REF,
                candidate_root=runner.ROOT,
                temp_root=root,
            )
            self.assertTrue(identity.startswith("git:"))
            self.assertTrue(
                (target / ".claude" / "skills" / "orchestration" / "SKILL.md").exists()
            )

    def test_cli_list_does_not_require_provider_process(self) -> None:
        status = runner.main(
            ["--provider", "codex", "--suite", "smoke", "--list"]
        )
        self.assertEqual(status, 0)

    def test_infrastructure_retry_is_opt_in(self) -> None:
        parser = runner.build_parser()
        default = parser.parse_args(["--provider", "codex"])
        enabled = parser.parse_args(
            ["--provider", "codex", "--retry-infrastructure"]
        )
        self.assertFalse(default.retry_infrastructure)
        self.assertTrue(enabled.retry_infrastructure)

    def test_json_catalog_is_plain_json(self) -> None:
        path = runner.ROOT / "evals" / "cases.json"
        parsed = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsInstance(parsed, list)


if __name__ == "__main__":
    unittest.main()
