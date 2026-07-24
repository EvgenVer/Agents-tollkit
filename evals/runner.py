from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CURRENT_REF = "59f7cbc"
IGNORED_SNAPSHOT_PARTS = {
    ".git",
    ".eval-last-message",
    "__pycache__",
    ".pytest_cache",
    "_eval_hidden",
}


class EvalError(RuntimeError):
    pass


@dataclass
class ProviderResult:
    status: str
    exit_code: int | None
    duration_ms: int
    stdout: str = ""
    stderr: str = ""
    final_message: str = ""
    provider_duration_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    model: str | None = None
    dispatch_count: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


@dataclass
class GradeResult:
    passed: bool
    checks: list[dict[str, Any]]
    hidden_test_output: str = ""


@dataclass
class RunResult:
    case_id: str
    suite: str
    variant: str
    provider: str
    repetition: int
    seed: int
    source_identity: str
    provider_result: ProviderResult
    grade: GradeResult


def _run(
    argv: list[str],
    *,
    cwd: Path,
    timeout: int = 120,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        stdin=subprocess.DEVNULL,
        timeout=timeout,
        check=False,
    )


def _git(*args: str, cwd: Path = ROOT, timeout: int = 120) -> str:
    result = _run(["git", *args], cwd=cwd, timeout=timeout)
    if result.returncode != 0:
        raise EvalError(
            f"git {' '.join(args)} failed ({result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout.strip()


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_extract_tar(data: bytes, destination: Path) -> None:
    destination = destination.resolve()
    with tarfile.open(fileobj=BytesIO(data), mode="r:") as archive:
        for member in archive.getmembers():
            if member.issym() or member.islnk() or not (
                member.isfile() or member.isdir()
            ):
                raise EvalError(f"unsupported archive member type: {member.name}")
            resolved = (destination / member.name).resolve()
            if destination not in resolved.parents and resolved != destination:
                raise EvalError(f"unsafe archive member: {member.name}")
        archive.extractall(destination)


def _materialize_git_ref(ref: str, destination: Path) -> str:
    result = subprocess.run(
        ["git", "archive", "--format=tar", ref],
        cwd=str(ROOT),
        capture_output=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        raise EvalError(
            f"cannot materialize Git ref {ref}: "
            f"{result.stderr.decode('utf-8', errors='replace').strip()}"
        )
    _safe_extract_tar(result.stdout, destination)
    return _git("rev-parse", ref, cwd=ROOT)


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def _copy_path(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    if source.is_symlink():
        raise EvalError(f"symbolic links are not copied into eval workspaces: {source}")
    if source.is_dir():
        link = next((item for item in source.rglob("*") if item.is_symlink()), None)
        if link is not None:
            raise EvalError(
                f"symbolic links are not copied into eval workspaces: {link}"
            )
    destination.parent.mkdir(parents=True, exist_ok=True)
    _remove_path(destination)
    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        shutil.copy2(source, destination)


def _install_eval_toolkit(source: Path, target: Path) -> None:
    for relative in ("AGENTS.md", "CLAUDE.md", "docs", ".agents"):
        _copy_path(source / relative, target / relative)
    for relative in (
        ".claude/commands",
        ".claude/agents",
        ".codex/agents",
    ):
        _copy_path(source / relative, target / relative)

    skills = source / ".agents" / "skills"
    if skills.exists():
        _copy_path(skills, target / ".claude" / "skills")


def _materialize_variant(
    variant: str,
    target: Path,
    *,
    legacy_file: Path,
    current_ref: str,
    candidate_root: Path,
    temp_root: Path,
) -> str:
    if variant == "legacy":
        if not legacy_file.exists():
            raise EvalError(f"legacy baseline does not exist: {legacy_file}")
        shutil.copy2(legacy_file, target / "AGENTS.md")
        (target / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        return f"sha256:{_hash_file(legacy_file)}"

    if variant == "current":
        source = temp_root / "toolkit-current"
        source.mkdir()
        identity = _materialize_git_ref(current_ref, source)
        _install_eval_toolkit(source, target)
        return f"git:{identity}"

    if variant == "candidate":
        _install_eval_toolkit(candidate_root, target)
        identity = _git("rev-parse", "HEAD", cwd=candidate_root)
        dirty = _git("status", "--porcelain", cwd=candidate_root)
        suffix = "+working-tree" if dirty else ""
        return f"git:{identity}{suffix}"

    raise EvalError(f"unknown variant: {variant}")


def _init_fixture_repo(path: Path) -> None:
    commands = [
        ["git", "init", "-q"],
        ["git", "config", "user.email", "eval@example.invalid"],
        ["git", "config", "user.name", "Toolkit Eval"],
        ["git", "add", "-A"],
        ["git", "commit", "-qm", "fixture baseline"],
    ]
    for command in commands:
        result = _run(command, cwd=path)
        if result.returncode != 0:
            raise EvalError(
                f"fixture Git initialization failed: {' '.join(command)}: "
                f"{result.stderr.strip()}"
            )


def _snapshot(path: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for item in sorted(path.rglob("*")):
        relative = item.relative_to(path)
        if item.is_symlink():
            snapshot[relative.as_posix()] = f"symlink:{os.readlink(item)}"
            continue
        if not item.is_file():
            continue
        if any(part in IGNORED_SNAPSHOT_PARTS for part in relative.parts):
            continue
        snapshot[relative.as_posix()] = _hash_file(item)
    return snapshot


def _json_events(stdout: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    stripped = stdout.strip()
    if not stripped:
        return events
    try:
        value = json.loads(stripped)
        if isinstance(value, dict):
            return [value]
    except json.JSONDecodeError:
        pass
    for line in stripped.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def _walk_json(value: Any) -> Iterable[tuple[str | None, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield key, child
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield None, child
            yield from _walk_json(child)


def _last_numeric(events: list[dict[str, Any]], names: set[str]) -> int | float | None:
    found: int | float | None = None
    for event in events:
        for key, value in _walk_json(event):
            if key in names and isinstance(value, (int, float)) and not isinstance(value, bool):
                found = value
    return found


def _dispatch_count(events: list[dict[str, Any]]) -> int:
    count = 0
    tool_names = {"spawn_agent", "task", "agent"}
    for event in events:
        for key, value in _walk_json(event):
            if key not in {"name", "tool", "tool_name", "function"}:
                continue
            if isinstance(value, str) and value.lower() in tool_names:
                count += 1
                break
    return count


def _final_message(events: list[dict[str, Any]], fallback: str) -> str:
    for event in reversed(events):
        if isinstance(event.get("result"), str):
            return event["result"]
        item = event.get("item")
        if isinstance(item, dict):
            for key in ("text", "content", "message"):
                if isinstance(item.get(key), str):
                    return item[key]
        for key in ("final_message", "message"):
            if isinstance(event.get(key), str):
                return event[key]
    return fallback.strip()


def _provider_command(
    provider: str,
    *,
    cwd: Path,
    prompt: str,
    model: str | None,
    orchestration: bool,
    max_budget_usd: float | None,
) -> tuple[list[str], Path | None]:
    if provider == "codex":
        last_message = cwd / ".eval-last-message"
        command = [
            "codex",
            "exec",
            "--json",
            "--ephemeral",
            "--ignore-user-config",
            "--sandbox",
            "workspace-write",
            "-C",
            str(cwd),
            "-o",
            str(last_message),
        ]
        if orchestration:
            command.extend(["--enable", "multi_agent"])
        if model:
            command.extend(["--model", model])
        command.append(prompt)
        return command, last_message

    if provider == "claude":
        command = [
            "claude",
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--no-session-persistence",
            "--permission-mode",
            "acceptEdits",
            "--allowedTools",
            "Read,Edit,Write,Glob,Grep,Bash,Task",
        ]
        if model:
            command.extend(["--model", model])
        if max_budget_usd is not None:
            command.extend(["--max-budget-usd", str(max_budget_usd)])
        return command, None

    raise EvalError(f"unsupported provider: {provider}")


def _classify_infrastructure_failure(returncode: int | None, output: str) -> bool:
    if returncode == 0:
        return False
    text = output.lower()
    markers = (
        "authentication",
        "not logged in",
        "rate limit",
        "connection",
        "failed to connect",
        "error sending request",
        "stream disconnected",
        "socket",
        "os error 10013",
        "network",
        "timed out",
        "overloaded",
        "unavailable",
    )
    return any(marker in text for marker in markers)


def _run_provider(
    provider: str,
    *,
    cwd: Path,
    prompt: str,
    model: str | None,
    orchestration: bool,
    timeout: int,
    max_budget_usd: float | None,
) -> ProviderResult:
    command, last_message_path = _provider_command(
        provider,
        cwd=cwd,
        prompt=prompt,
        model=model,
        orchestration=orchestration,
        max_budget_usd=max_budget_usd,
    )
    started = time.monotonic()
    try:
        completed = _run(command, cwd=cwd, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        return ProviderResult(
            status="infrastructure_failure",
            exit_code=None,
            duration_ms=round((time.monotonic() - started) * 1000),
            stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
            stderr=(exc.stderr or "") if isinstance(exc.stderr, str) else "",
            model=model,
            error=f"timeout after {timeout}s",
        )

    duration_ms = round((time.monotonic() - started) * 1000)
    events = _json_events(completed.stdout)
    final_fallback = completed.stdout
    if last_message_path and last_message_path.exists():
        final_fallback = last_message_path.read_text(encoding="utf-8", errors="replace")

    infrastructure = _classify_infrastructure_failure(
        completed.returncode, completed.stdout + "\n" + completed.stderr
    )
    status = (
        "success"
        if completed.returncode == 0
        else "infrastructure_failure"
        if infrastructure
        else "behavior_failure"
    )

    provider_duration = _last_numeric(events, {"duration_ms", "duration_api_ms"})
    input_tokens = _last_numeric(
        events, {"input_tokens", "inputTokens", "prompt_tokens"}
    )
    output_tokens = _last_numeric(
        events, {"output_tokens", "outputTokens", "completion_tokens"}
    )
    cost = _last_numeric(events, {"total_cost_usd", "cost_usd", "costUSD"})

    return ProviderResult(
        status=status,
        exit_code=completed.returncode,
        duration_ms=duration_ms,
        stdout=completed.stdout,
        stderr=completed.stderr,
        final_message=_final_message(events, final_fallback),
        provider_duration_ms=int(provider_duration) if provider_duration is not None else None,
        input_tokens=int(input_tokens) if input_tokens is not None else None,
        output_tokens=int(output_tokens) if output_tokens is not None else None,
        cost_usd=float(cost) if cost is not None else None,
        model=model,
        dispatch_count=_dispatch_count(events),
        events=events,
        error=None if completed.returncode == 0 else completed.stderr.strip(),
    )


def _check(
    checks: list[dict[str, Any]], name: str, passed: bool, detail: str
) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _grade(
    case: dict[str, Any],
    workspace: Path,
    before: dict[str, str],
    after: dict[str, str],
    provider: ProviderResult,
) -> GradeResult:
    checks: list[dict[str, Any]] = []
    if provider.status == "infrastructure_failure":
        _check(
            checks,
            "provider infrastructure",
            False,
            f"exit={provider.exit_code}, error={(provider.error or '')[-2000:]}",
        )
        return GradeResult(passed=False, checks=checks)

    grade = case.get("grade", {})
    workspace_links = [
        item.relative_to(workspace).as_posix()
        for item in workspace.rglob("*")
        if item.is_symlink()
    ]
    _check(
        checks,
        "workspace contains no symbolic links",
        not workspace_links,
        f"links={workspace_links}",
    )
    changed = sorted(
        path
        for path in set(before) | set(after)
        if before.get(path) != after.get(path)
    )

    if grade.get("unchanged"):
        _check(checks, "workspace unchanged", not changed, f"changed={changed}")

    allowed = grade.get("allowed_changes")
    if allowed is not None:
        unexpected = [path for path in changed if not _matches_any(path, allowed)]
        _check(
            checks,
            "changes stay in allowed scope",
            not unexpected,
            f"unexpected={unexpected}",
        )

    for pattern in grade.get("required_paths", []):
        matches = list(workspace.glob(pattern))
        _check(checks, f"required path {pattern}", bool(matches), f"matches={matches}")

    for pattern in grade.get("forbidden_paths", []):
        matches = list(workspace.glob(pattern))
        _check(checks, f"forbidden path {pattern}", not matches, f"matches={matches}")

    for relative, expected in grade.get("file_contains", {}).items():
        path = workspace / relative
        content = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        _check(
            checks,
            f"{relative} contains expected text",
            expected in content,
            f"expected={expected!r}",
        )

    for relative, forbidden in grade.get("file_not_contains", {}).items():
        path = workspace / relative
        content = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        _check(
            checks,
            f"{relative} excludes forbidden text",
            forbidden not in content,
            f"forbidden={forbidden!r}",
        )

    required_final = grade.get("final_contains")
    if required_final:
        _check(
            checks,
            "final response marker",
            required_final in provider.final_message,
            f"expected marker={required_final!r}",
        )

    if "min_dispatches" in grade:
        minimum = int(grade["min_dispatches"])
        _check(
            checks,
            "minimum subagent dispatches",
            provider.dispatch_count >= minimum,
            f"actual={provider.dispatch_count}, expected>={minimum}",
        )
    if "max_dispatches" in grade:
        maximum = int(grade["max_dispatches"])
        _check(
            checks,
            "maximum subagent dispatches",
            provider.dispatch_count <= maximum,
            f"actual={provider.dispatch_count}, expected<={maximum}",
        )

    hidden_output = ""
    hidden_relative = case.get("hidden")
    if hidden_relative and not workspace_links:
        source = ROOT / "evals" / "hidden" / hidden_relative
        destination = workspace / "_eval_hidden"
        _copy_path(source, destination)
        completed = _run(
            [sys.executable, "-m", "unittest", "discover", "-s", "_eval_hidden", "-v"],
            cwd=workspace,
            timeout=120,
        )
        hidden_output = completed.stdout + completed.stderr
        _check(
            checks,
            "hidden tests",
            completed.returncode == 0,
            hidden_output[-4000:],
        )

    _check(
        checks,
        "provider completed",
        provider.status == "success",
        f"status={provider.status}, exit={provider.exit_code}, error={provider.error}",
    )
    return GradeResult(
        passed=all(item["passed"] for item in checks),
        checks=checks,
        hidden_test_output=hidden_output,
    )


def _load_cases() -> list[dict[str, Any]]:
    path = ROOT / "evals" / "cases.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise EvalError("evals/cases.json must contain a list")
    required = {"id", "suite", "fixture", "prompt", "variants", "grade"}
    ids: set[str] = set()
    for case in data:
        missing = required - set(case)
        if missing:
            raise EvalError(f"case missing {sorted(missing)}: {case}")
        if case["id"] in ids:
            raise EvalError(f"duplicate case id: {case['id']}")
        ids.add(case["id"])
    return data


def _case_selected(case: dict[str, Any], args: argparse.Namespace) -> bool:
    if args.case and case["id"] not in args.case:
        return False
    if args.suite == "all":
        return True
    if args.suite == "smoke":
        return bool(case.get("smoke", False))
    return case["suite"] == args.suite


def _provider_version(provider: str) -> str:
    command = [provider, "--version"]
    result = _run(command, cwd=ROOT, timeout=30)
    if result.returncode != 0:
        raise EvalError(f"{provider} is unavailable: {result.stderr.strip()}")
    return result.stdout.strip()


def _single_run(
    case: dict[str, Any],
    variant: str,
    provider: str,
    repetition: int,
    seed: int,
    args: argparse.Namespace,
) -> RunResult:
    with tempfile.TemporaryDirectory(prefix="toolkit-eval-") as temp:
        temp_root = Path(temp)
        workspace = temp_root / "workspace"
        fixture = ROOT / "evals" / "fixtures" / case["fixture"]
        if not fixture.exists():
            raise EvalError(f"fixture not found: {fixture}")
        _copy_path(fixture, workspace)
        source_identity = _materialize_variant(
            variant,
            workspace,
            legacy_file=args.legacy_file,
            current_ref=args.current_ref,
            candidate_root=args.candidate_root,
            temp_root=temp_root,
        )
        _init_fixture_repo(workspace)
        before = _snapshot(workspace)

        provider_result = _run_provider(
            provider,
            cwd=workspace,
            prompt=case["prompt"],
            model=args.model,
            orchestration=case["suite"] == "orchestration",
            timeout=args.timeout,
            max_budget_usd=args.max_budget_usd,
        )
        if provider_result.status == "infrastructure_failure" and args.retry_infrastructure:
            provider_result = _run_provider(
                provider,
                cwd=workspace,
                prompt=case["prompt"],
                model=args.model,
                orchestration=case["suite"] == "orchestration",
                timeout=args.timeout,
                max_budget_usd=args.max_budget_usd,
            )

        after = _snapshot(workspace)
        grade = _grade(case, workspace, before, after, provider_result)
        return RunResult(
            case_id=case["id"],
            suite=case["suite"],
            variant=variant,
            provider=provider,
            repetition=repetition,
            seed=seed,
            source_identity=source_identity,
            provider_result=provider_result,
            grade=grade,
        )


def _aggregate(results: list[RunResult]) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[RunResult]] = {}
    for result in results:
        grouped.setdefault((result.case_id, result.variant), []).append(result)
    rows = []
    for (case_id, variant), items in sorted(grouped.items()):
        valid = [
            item
            for item in items
            if item.provider_result.status != "infrastructure_failure"
        ]
        durations = [item.provider_result.duration_ms for item in valid]
        costs = [
            item.provider_result.cost_usd
            for item in valid
            if item.provider_result.cost_usd is not None
        ]
        passes = sum(item.grade.passed for item in valid)
        rows.append(
            {
                "case_id": case_id,
                "variant": variant,
                "runs": len(items),
                "valid_runs": len(valid),
                "infrastructure_failures": len(items) - len(valid),
                "passes": passes,
                "pass_rate": passes / len(valid) if valid else None,
                "pass_all": bool(valid) and all(item.grade.passed for item in valid),
                "median_duration_ms": (
                    round(statistics.median(durations)) if durations else None
                ),
                "median_cost_usd": statistics.median(costs) if costs else None,
                "median_dispatch_count": (
                    statistics.median(
                        item.provider_result.dispatch_count for item in valid
                    )
                    if valid
                    else None
                ),
            }
        )
    return {"rows": rows}


def _comparison_gates(
    cases: list[dict[str, Any]],
    aggregate: dict[str, Any],
    *,
    enforce_performance: bool,
) -> list[dict[str, Any]]:
    rows = {
        (row["case_id"], row["variant"]): row for row in aggregate["rows"]
    }
    gates: list[dict[str, Any]] = []
    for case in cases:
        if not case.get("performance_gate") or not enforce_performance:
            continue
        current = rows.get((case["id"], "current"))
        candidate = rows.get((case["id"], "candidate"))
        if not current or not candidate:
            gates.append(
                {
                    "case_id": case["id"],
                    "passed": False,
                    "detail": "current and candidate results are required",
                }
            )
            continue
        speed_ratio = (
            candidate["median_duration_ms"] / current["median_duration_ms"]
            if current["median_duration_ms"] and candidate["median_duration_ms"]
            else None
        )
        quality_ok = (
            current["pass_rate"] is not None
            and candidate["pass_rate"] is not None
            and candidate["pass_rate"] >= current["pass_rate"]
        )
        speed_ok = speed_ratio is not None and speed_ratio <= 0.80
        cost_ok = True
        if (
            current["median_cost_usd"] is not None
            and candidate["median_cost_usd"] is not None
        ):
            cost_ok = candidate["median_cost_usd"] <= current["median_cost_usd"] * 2
        gates.append(
            {
                "case_id": case["id"],
                "passed": quality_ok and speed_ok and cost_ok,
                "detail": {
                    "quality_ok": quality_ok,
                    "speed_ratio": speed_ratio,
                    "speed_ok": speed_ok,
                    "cost_ok": cost_ok,
                },
            }
        )
    return gates


def _markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Toolkit evaluation report",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Provider: `{payload['provider']}`",
        f"- CLI: `{payload['provider_version']}`",
        f"- Model override: `{payload['model'] or 'provider default'}`",
        f"- Repetitions: {payload['runs_per_case']}",
        "",
        "| Case | Variant | Valid/total | Passes | Pass rate | Median ms | Median cost | Dispatches |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["aggregate"]["rows"]:
        cost = (
            f"${row['median_cost_usd']:.4f}"
            if row["median_cost_usd"] is not None
            else "n/a"
        )
        pass_rate = (
            f"{row['pass_rate']:.0%}" if row["pass_rate"] is not None else "n/a"
        )
        duration = (
            str(row["median_duration_ms"])
            if row["median_duration_ms"] is not None
            else "n/a"
        )
        dispatches = (
            str(row["median_dispatch_count"])
            if row["median_dispatch_count"] is not None
            else "n/a"
        )
        lines.append(
            f"| {row['case_id']} | {row['variant']} | "
            f"{row['valid_runs']}/{row['runs']} | {row['passes']} | {pass_rate} | "
            f"{duration} | {cost} | {dispatches} |"
        )
    if payload["comparison_gates"]:
        lines.extend(["", "## Comparison gates", ""])
        for gate in payload["comparison_gates"]:
            marker = "PASS" if gate["passed"] else "FAIL"
            lines.append(f"- **{marker}** `{gate['case_id']}` — `{gate['detail']}`")
    infrastructure = [
        item
        for item in payload["results"]
        if item["provider_result"]["status"] == "infrastructure_failure"
    ]
    if infrastructure:
        lines.extend(["", "## Infrastructure failures", ""])
        for item in infrastructure:
            error = (item["provider_result"]["error"] or "").replace("\r", " ").replace(
                "\n", " "
            )
            lines.append(
                f"- `{item['case_id']}` / `{item['variant']}` / "
                f"run {item['repetition']}: {error[-800:]}"
            )
    failed = [
        item
        for item in payload["results"]
        if item["provider_result"]["status"] != "infrastructure_failure"
        and not item["grade"]["passed"]
    ]
    if failed:
        lines.extend(["", "## Failed runs", ""])
        for item in failed:
            failed_checks = [
                check["name"]
                for check in item["grade"]["checks"]
                if not check["passed"]
            ]
            lines.append(
                f"- `{item['case_id']}` / `{item['variant']}` / "
                f"run {item['repetition']}: {', '.join(failed_checks)}"
            )
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare legacy, current, and candidate toolkit behavior."
    )
    parser.add_argument(
        "--suite",
        choices=("smoke", "workflow", "orchestration", "all"),
        default="smoke",
    )
    parser.add_argument("--provider", choices=("codex", "claude"), required=True)
    parser.add_argument("--variant", action="append", choices=("legacy", "current", "candidate"))
    parser.add_argument("--case", action="append", help="Run only a named case.")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--release", action="store_true", help="Use five runs and enforce comparison gates.")
    parser.add_argument("--seed", type=int, default=20260724)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--model")
    parser.add_argument("--max-budget-usd", type=float)
    parser.add_argument("--current-ref", default=DEFAULT_CURRENT_REF)
    parser.add_argument(
        "--candidate-root", type=Path, default=ROOT
    )
    parser.add_argument(
        "--legacy-file",
        type=Path,
        default=ROOT / "AGENTS_WORKFLOW_LEGACY" / "AGENTS_v1.md",
    )
    parser.add_argument(
        "--artifacts",
        type=Path,
        default=ROOT / ".artifacts" / "evals",
    )
    parser.add_argument(
        "--retry-infrastructure",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Retry one infrastructure failure per run (disabled by default to keep the call bound exact).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Acknowledge the bounded provider run without an interactive prompt.",
    )
    parser.add_argument("--list", action="store_true", help="List selected cases without running.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.release:
        args.runs = 5
    if args.runs < 1:
        parser.error("--runs must be >= 1")
    args.candidate_root = args.candidate_root.resolve()
    args.legacy_file = args.legacy_file.resolve()
    cases = [case for case in _load_cases() if _case_selected(case, args)]
    if not cases:
        raise EvalError("no eval cases selected")
    if args.list:
        for case in cases:
            print(f"{case['id']}\t{case['suite']}\t{','.join(case['variants'])}")
        return 0

    variants = args.variant or ["legacy", "current", "candidate"]
    base_invocations = sum(
        1 for case in cases for variant in variants if variant in case["variants"]
    ) * args.runs
    invocations = base_invocations * (2 if args.retry_infrastructure else 1)
    print(
        f"Provider={args.provider}; model={args.model or 'default'}; "
        f"cases={len(cases)}; maximum invocations={invocations}; "
        f"per-Claude-call budget={args.max_budget_usd or 'not set'}"
    )
    if not args.yes:
        raise EvalError("rerun with --yes after approving this bounded provider run")

    version = _provider_version(args.provider)
    results: list[RunResult] = []
    for case in cases:
        for variant in variants:
            if variant not in case["variants"]:
                continue
            for repetition in range(1, args.runs + 1):
                print(f"[{case['id']}] {variant} run {repetition}/{args.runs}", flush=True)
                results.append(
                    _single_run(
                        case,
                        variant,
                        args.provider,
                        repetition,
                        args.seed + repetition,
                        args,
                    )
                )

    aggregate = _aggregate(results)
    gates = _comparison_gates(
        cases, aggregate, enforce_performance=args.release
    )
    generated_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "generated_at": generated_at,
        "provider": args.provider,
        "provider_version": version,
        "model": args.model,
        "runs_per_case": args.runs,
        "seed": args.seed,
        "current_ref": args.current_ref,
        "aggregate": aggregate,
        "comparison_gates": gates,
        "results": [asdict(result) for result in results],
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = args.artifacts / stamp
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output_dir / "report.md").write_text(
        _markdown_report(payload), encoding="utf-8"
    )
    print(f"Report: {output_dir / 'report.md'}")

    infrastructure_failures = any(
        result.provider_result.status == "infrastructure_failure"
        for result in results
    )
    hard_failures = any(
        result.provider_result.status != "infrastructure_failure"
        and not result.grade.passed
        for result in results
    )
    gate_failures = any(not gate["passed"] for gate in gates)
    if infrastructure_failures:
        return 2
    return 1 if hard_failures or gate_failures else 0
