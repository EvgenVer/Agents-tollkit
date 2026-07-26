from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evals import runner


class EvalRunnerTests(unittest.TestCase):
    def test_eval_workspaces_are_created_beneath_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            artifacts = Path(temp) / "reports"
            with runner._temporary_eval_root(artifacts) as temp_root:
                workspace_root = runner._eval_workspace_root(artifacts)

                self.assertEqual(workspace_root, temp_root.parent)
                self.assertTrue(temp_root.is_dir())

            self.assertFalse(temp_root.exists())
            self.assertTrue(workspace_root.is_dir())

    def test_codex_command_pins_model_reasoning_and_service_tier(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            command, _ = runner._provider_command(
                "codex",
                cwd=Path(temp),
                prompt="Do the task.",
                model="gpt-5.6-sol",
                reasoning_effort="high",
                service_tier="default",
                windows_sandbox="unelevated",
                orchestration=True,
                max_budget_usd=None,
            )

        self.assertIn("--model", command)
        self.assertIn("gpt-5.6-sol", command)
        self.assertIn('approval_policy="never"', command)
        self.assertIn('model_reasoning_effort="high"', command)
        self.assertIn('service_tier="default"', command)
        self.assertIn('windows.sandbox="unelevated"', command)
        self.assertIn("multi_agent", command)

    def test_codex_provider_drops_parent_desktop_session_environment(self) -> None:
        with patch.dict(
            runner.os.environ,
            {
                "CODEX_THREAD_ID": "thread",
                "CODEX_INTERNAL_ORIGINATOR_OVERRIDE": "Codex Desktop",
                "CODEX_PERMISSION_PROFILE": ":read-only",
                "EVAL_KEEP_ME": "yes",
            },
        ):
            env = runner._provider_env("codex")

        self.assertEqual(env["EVAL_KEEP_ME"], "yes")
        for key in runner.CODEX_SESSION_ENV_KEYS:
            self.assertNotIn(key, env)

    def test_snapshot_failure_is_classified_as_infrastructure(self) -> None:
        provider_result = runner.ProviderResult(
            status="success",
            exit_code=0,
            duration_ms=1,
        )
        before = {"README.md": "hash"}

        with patch.object(
            runner,
            "_snapshot",
            side_effect=PermissionError("access denied"),
        ):
            after = runner._snapshot_after_provider(
                Path("workspace"),
                before,
                provider_result,
            )

        self.assertEqual(before, after)
        self.assertEqual("infrastructure_failure", provider_result.status)
        self.assertIn("workspace snapshot failed", provider_result.error)
        self.assertIn("access denied", provider_result.error)

    def test_model_cli_version_mismatch_is_infrastructure(self) -> None:
        output = (
            "The gpt-5.6-sol model requires a newer version of Codex. "
            "Please upgrade to the latest app or CLI and try again."
        )
        self.assertEqual(
            runner._classify_infrastructure_failure(1, output),
            "provider model requires a newer Codex CLI",
        )

    def test_read_only_write_block_is_an_infrastructure_failure_even_on_exit_zero(
        self,
    ) -> None:
        output = "patch rejected: writing is blocked by read-only sandbox"
        self.assertEqual(
            runner._classify_infrastructure_failure(
                0, output, requires_write=True
            ),
            "provider workspace is not writable",
        )
        self.assertIsNone(
            runner._classify_infrastructure_failure(
                0, output, requires_write=False
            )
        )
        self.assertEqual(
            runner._classify_infrastructure_failure(
                0,
                "Get-ChildItem: Access to the path workspace is denied. "
                "Access is denied.",
                requires_write=True,
            ),
            "provider workspace is not writable",
        )

    def test_dispatch_count_recognizes_namespaced_spawn_agent(self) -> None:
        events = [
            {"tool_name": "collaboration.spawn_agent"},
            {"item": {"function": "mcp__collaboration__spawn_agent"}},
            {"tool_name": "shell_command"},
        ]
        self.assertEqual(runner._dispatch_count(events), 2)

    def test_collaboration_thread_failure_is_infrastructure(self) -> None:
        self.assertEqual(
            runner._classify_infrastructure_failure(
                0,
                "Parallel executor creation failed because the collaboration "
                "environment could not resolve the active thread.",
            ),
            "provider collaboration infrastructure failure",
        )

    def test_build_jobs_can_select_one_repetition(self) -> None:
        cases = [
            {
                "id": "case",
                "suite": "workflow",
                "variants": ["candidate"],
            }
        ]
        jobs, _ = runner._build_jobs(
            cases,
            ["candidate"],
            runs=3,
            seed=1,
            repetitions=[3],
        )
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0][2], 3)

    def test_full_matrix_has_84_calls_and_starts_with_reused_write_canary(
        self,
    ) -> None:
        cases = runner._load_cases()
        jobs, canary = runner._build_jobs(
            cases,
            ["legacy", "current", "candidate"],
            runs=3,
            seed=20260724,
        )

        self.assertEqual(len(jobs), 84)
        self.assertEqual(
            canary,
            ("trivial-fast-path", "candidate", 1),
        )
        first_case, first_variant, first_repetition, _ = jobs[0]
        self.assertEqual(
            (first_case["id"], first_variant, first_repetition),
            canary,
        )

    def test_noninferiority_and_parallel_speed_gates(self) -> None:
        cases = [
            {
                "id": "core",
                "suite": "workflow",
                "variants": ["legacy", "current", "candidate"],
            },
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

        def row(
            case_id: str,
            variant: str,
            *,
            duration: int,
            tokens: int,
            dispatches: int = 0,
            uncached_tokens: int | None = None,
        ) -> dict[str, object]:
            return {
                "case_id": case_id,
                "variant": variant,
                "runs": 3,
                "valid_runs": 3,
                "passes": 3,
                "pass_rate": 1.0,
                "pass_all": True,
                "median_duration_ms": duration,
                "median_total_tokens": tokens,
                "median_uncached_plus_output_tokens": (
                    uncached_tokens if uncached_tokens is not None else tokens
                ),
                "median_dispatch_count": dispatches,
                "median_collaboration_wait_count": 0,
                "median_command_count": 3,
                "median_command_round_count": 2,
            }

        aggregate = {
            "rows": [
                row("core", "legacy", duration=100, tokens=100),
                row("core", "current", duration=100, tokens=100),
                row(
                    "core",
                    "candidate",
                    duration=110,
                    tokens=110,
                    uncached_tokens=100,
                ),
                row(
                    "parallel",
                    "candidate",
                    duration=80,
                    tokens=140,
                    dispatches=2,
                ),
                row(
                    "parallel-sequential",
                    "candidate",
                    duration=100,
                    tokens=100,
                ),
            ]
        }

        gates = runner._comparison_gates(
            cases, aggregate, enforce_performance=True
        )
        self.assertEqual(len(gates), 3)
        self.assertTrue(all(gate["passed"] for gate in gates))

        aggregate["rows"][2]["median_duration_ms"] = 116
        gates = runner._comparison_gates(
            cases, aggregate, enforce_performance=True
        )
        legacy_gate = next(
            gate for gate in gates if gate["case_id"] == "workflow-vs-legacy"
        )
        self.assertFalse(legacy_gate["passed"])

        aggregate["rows"][2]["median_duration_ms"] = 110
        aggregate["rows"][2]["median_command_round_count"] = 26
        gates = runner._comparison_gates(
            cases, aggregate, enforce_performance=True
        )
        legacy_gate = next(
            gate for gate in gates if gate["case_id"] == "workflow-vs-legacy"
        )
        self.assertFalse(legacy_gate["passed"])

    def test_fresh_results_replace_reused_baseline_rows(self) -> None:
        def result(duration: int) -> runner.RunResult:
            return runner.RunResult(
                case_id="case",
                suite="workflow",
                variant="candidate",
                provider="codex",
                repetition=1,
                seed=1,
                source_identity="source",
                provider_result=runner.ProviderResult(
                    status="success",
                    exit_code=0,
                    duration_ms=duration,
                ),
                grade=runner.GradeResult(passed=True, checks=[]),
            )

        merged = runner._merge_results([result(100)], [result(50)])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].provider_result.duration_ms, 50)


if __name__ == "__main__":
    unittest.main()
