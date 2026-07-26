from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import tarfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable, Iterator
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CURRENT_REF = "59f7cbc"
IGNORED_SNAPSHOT_PARTS = {
    ".git",
    ".eval-last-message",
    "__pycache__",
    ".pytest_cache",
    "_eval_hidden",
}
CODEX_SESSION_ENV_KEYS = {
    "CODEX_INTERNAL_ORIGINATOR_OVERRIDE",
    "CODEX_PERMISSION_PROFILE",
    "CODEX_THREAD_ID",
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
    cached_input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    model: str | None = None
    dispatch_count: int = 0
    collaboration_wait_count: int = 0
    command_count: int = 0
    command_round_count: int = 0
    model_turn_count: int = 0
    skill_read_count: int = 0
    review_skill_read_count: int = 0
    docs_read_count: int = 0
    git_command_count: int = 0
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
        shutil.copytree(
            source,
            destination,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
        )
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


def _snapshot_after_provider(
    workspace: Path,
    before: dict[str, str],
    provider_result: ProviderResult,
) -> dict[str, str]:
    try:
        return _snapshot(workspace)
    except OSError as exc:
        provider_result.status = "infrastructure_failure"
        provider_result.error = f"workspace snapshot failed: {exc}"
        return before


def _eval_workspace_root(artifacts: Path) -> Path:
    root = (artifacts / "_workspaces").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


@contextmanager
def _temporary_eval_root(artifacts: Path) -> Iterator[Path]:
    temp_root = _eval_workspace_root(artifacts) / f"toolkit-eval-{uuid4().hex}"
    # tempfile.mkdtemp uses an owner-only ACL on Windows. A normal directory
    # inherits the project ACL required by Codex's restricted sandbox token.
    temp_root.mkdir()
    try:
        yield temp_root
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


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
            if not isinstance(value, str):
                continue
            normalized = value.lower()
            if (
                normalized in tool_names
                or normalized.endswith(".spawn_agent")
                or normalized.endswith("__spawn_agent")
            ):
                count += 1
                break
    return count


def _started_items(
    events: list[dict[str, Any]], item_type: str
) -> list[dict[str, Any]]:
    return [
        item
        for event in events
        if event.get("type") == "item.started"
        and isinstance((item := event.get("item")), dict)
        and item.get("type") == item_type
    ]


def _collaboration_wait_count(events: list[dict[str, Any]]) -> int:
    return sum(
        item.get("tool") == "wait"
        for item in _started_items(events, "collab_tool_call")
    )


def _trajectory_metrics(events: list[dict[str, Any]]) -> dict[str, int]:
    commands = _started_items(events, "command_execution")
    command_rounds = 0
    command_in_flight = False
    for event in events:
        item = event.get("item")
        if not isinstance(item, dict) or item.get("type") != "command_execution":
            continue
        if event.get("type") == "item.started":
            if not command_in_flight:
                command_rounds += 1
            command_in_flight = True
        elif event.get("type") == "item.completed":
            command_in_flight = False
    command_text = "\n".join(
        item["command"] for item in commands if isinstance(item.get("command"), str)
    )
    model_turns = sum(
        event.get("type") == "item.completed"
        and isinstance(event.get("item"), dict)
        and event["item"].get("type") == "agent_message"
        for event in events
    )
    skill_reads = len(
        re.findall(
            r"\.agents[\\/]+skills[\\/]+[^\"']*?SKILL\.md",
            command_text,
            flags=re.IGNORECASE,
        )
    )
    review_skill_reads = len(
        re.findall(
            r"\.agents[\\/]+skills[\\/]+code-review[\\/]+SKILL\.md",
            command_text,
            flags=re.IGNORECASE,
        )
    )
    docs_reads = len(
        re.findall(
            r"docs[\\/]+[A-Z0-9_-]+\.md",
            command_text,
            flags=re.IGNORECASE,
        )
    )
    git_commands = len(
        re.findall(r"(?<![\w-])git\s+[a-z-]+", command_text, flags=re.IGNORECASE)
    )
    return {
        "command_count": len(commands),
        "command_round_count": command_rounds,
        "model_turn_count": model_turns,
        "skill_read_count": skill_reads,
        "review_skill_read_count": review_skill_reads,
        "docs_read_count": docs_reads,
        "git_command_count": git_commands,
    }


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
    reasoning_effort: str | None,
    service_tier: str | None,
    windows_sandbox: str | None,
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
            "-c",
            'approval_policy="never"',
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
        if reasoning_effort:
            command.extend(
                ["-c", f'model_reasoning_effort="{reasoning_effort}"']
            )
        if service_tier:
            command.extend(["-c", f'service_tier="{service_tier}"'])
        if windows_sandbox:
            command.extend(["-c", f'windows.sandbox="{windows_sandbox}"'])
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


def _provider_env(provider: str) -> dict[str, str]:
    env = os.environ.copy()
    if provider == "codex":
        for key in CODEX_SESSION_ENV_KEYS:
            env.pop(key, None)
    return env


def _classify_infrastructure_failure(
    returncode: int | None,
    output: str,
    *,
    requires_write: bool = False,
) -> str | None:
    text = output.lower()
    model_cli_markers = (
        "model requires a newer version of codex",
        "please upgrade to the latest app or cli",
    )
    if any(marker in text for marker in model_cli_markers):
        return "provider model requires a newer Codex CLI"
    if requires_write:
        write_block_markers = (
            "writing is blocked by read-only sandbox",
            "workspace is currently read-only",
            "workspace is read-only",
            "read-only filesystem access",
            "patch rejected: writing is blocked",
        )
        workspace_access_denied = (
            "access is denied" in text and "workspace" in text
        )
        if workspace_access_denied or any(
            marker in text for marker in write_block_markers
        ):
            return "provider workspace is not writable"
    if returncode == 0:
        return None
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
    if any(marker in text for marker in markers):
        return "provider infrastructure failure"
    return None


def _run_provider(
    provider: str,
    *,
    cwd: Path,
    prompt: str,
    model: str | None,
    reasoning_effort: str | None,
    service_tier: str | None,
    windows_sandbox: str | None,
    orchestration: bool,
    requires_write: bool,
    timeout: int,
    max_budget_usd: float | None,
) -> ProviderResult:
    command, last_message_path = _provider_command(
        provider,
        cwd=cwd,
        prompt=prompt,
        model=model,
        reasoning_effort=reasoning_effort,
        service_tier=service_tier,
        windows_sandbox=windows_sandbox,
        orchestration=orchestration,
        max_budget_usd=max_budget_usd,
    )
    started = time.monotonic()
    try:
        completed = _run(
            command,
            cwd=cwd,
            timeout=timeout,
            env=_provider_env(provider),
        )
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

    infrastructure_reason = _classify_infrastructure_failure(
        completed.returncode,
        completed.stdout + "\n" + completed.stderr + "\n" + final_fallback,
        requires_write=requires_write,
    )
    status = (
        "infrastructure_failure"
        if infrastructure_reason
        else "success"
        if completed.returncode == 0
        else "behavior_failure"
    )

    provider_duration = _last_numeric(events, {"duration_ms", "duration_api_ms"})
    input_tokens = _last_numeric(
        events, {"input_tokens", "inputTokens", "prompt_tokens"}
    )
    cached_input_tokens = _last_numeric(
        events, {"cached_input_tokens", "cachedInputTokens", "cached_tokens"}
    )
    output_tokens = _last_numeric(
        events, {"output_tokens", "outputTokens", "completion_tokens"}
    )
    cost = _last_numeric(events, {"total_cost_usd", "cost_usd", "costUSD"})
    trajectory = _trajectory_metrics(events)

    return ProviderResult(
        status=status,
        exit_code=completed.returncode,
        duration_ms=duration_ms,
        stdout=completed.stdout,
        stderr=completed.stderr,
        final_message=_final_message(events, final_fallback),
        provider_duration_ms=int(provider_duration) if provider_duration is not None else None,
        input_tokens=int(input_tokens) if input_tokens is not None else None,
        cached_input_tokens=(
            int(cached_input_tokens) if cached_input_tokens is not None else None
        ),
        output_tokens=int(output_tokens) if output_tokens is not None else None,
        cost_usd=float(cost) if cost is not None else None,
        model=model,
        dispatch_count=_dispatch_count(events),
        collaboration_wait_count=_collaboration_wait_count(events),
        **trajectory,
        events=events,
        error=(
            infrastructure_reason
            or (completed.stderr.strip() if completed.returncode != 0 else None)
        ),
    )


def _check(
    checks: list[dict[str, Any]], name: str, passed: bool, detail: str
) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _grade(
    case: dict[str, Any],
    variant: str,
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
    required_final_any = grade.get("final_contains_any", [])
    if required_final_any:
        final_casefold = provider.final_message.casefold()
        _check(
            checks,
            "final response contains one expected marker",
            any(marker.casefold() in final_casefold for marker in required_final_any),
            f"expected one of={required_final_any!r}",
        )

    if "min_dispatches" in grade:
        minimum = int(grade["min_dispatches"])
        dispatch_observed = (
            provider.dispatch_count >= minimum
            or provider.collaboration_wait_count >= minimum
        )
        _check(
            checks,
            "minimum parallel collaboration evidence",
            dispatch_observed,
            "direct_dispatches="
            f"{provider.dispatch_count}, collaboration_waits="
            f"{provider.collaboration_wait_count}, expected>={minimum}",
        )
    if "max_dispatches" in grade:
        maximum = int(grade["max_dispatches"])
        dispatch_observed = max(
            provider.dispatch_count, provider.collaboration_wait_count
        )
        _check(
            checks,
            "maximum parallel collaboration evidence",
            dispatch_observed <= maximum,
            "direct_dispatches="
            f"{provider.dispatch_count}, collaboration_waits="
            f"{provider.collaboration_wait_count}, expected<={maximum}",
        )

    if variant == "candidate":
        candidate_limits = (
            ("candidate_max_commands", "candidate command budget", provider.command_count),
            (
                "candidate_max_command_rounds",
                "candidate command-round budget",
                provider.command_round_count,
            ),
            (
                "candidate_max_model_turns",
                "candidate model-turn budget",
                provider.model_turn_count,
            ),
            (
                "candidate_max_skill_reads",
                "candidate skill-read budget",
                provider.skill_read_count,
            ),
            (
                "candidate_max_git_commands",
                "candidate git-command budget",
                provider.git_command_count,
            ),
        )
        for key, name, actual in candidate_limits:
            if key not in grade:
                continue
            maximum = int(grade[key])
            _check(checks, name, actual <= maximum, f"actual={actual}, max={maximum}")
        if "candidate_min_review_skill_reads" in grade:
            minimum = int(grade["candidate_min_review_skill_reads"])
            _check(
                checks,
                "candidate required full review",
                provider.review_skill_read_count >= minimum,
                f"actual={provider.review_skill_read_count}, min={minimum}",
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
    with _temporary_eval_root(args.artifacts) as temp_root:
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
            reasoning_effort=args.reasoning_effort,
            service_tier=args.service_tier,
            windows_sandbox=args.windows_sandbox,
            orchestration=case.get(
                "enable_multi_agent", case["suite"] == "orchestration"
            ),
            requires_write=bool(case.get("requires_write", False)),
            timeout=args.timeout,
            max_budget_usd=args.max_budget_usd,
        )
        if provider_result.status == "infrastructure_failure" and args.retry_infrastructure:
            provider_result = _run_provider(
                provider,
                cwd=workspace,
                prompt=case["prompt"],
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                service_tier=args.service_tier,
                windows_sandbox=args.windows_sandbox,
                orchestration=case.get(
                    "enable_multi_agent", case["suite"] == "orchestration"
                ),
                requires_write=bool(case.get("requires_write", False)),
                timeout=args.timeout,
                max_budget_usd=args.max_budget_usd,
            )

        after = _snapshot_after_provider(workspace, before, provider_result)
        grade = _grade(
            case, variant, workspace, before, after, provider_result
        )
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


def _build_jobs(
    cases: list[dict[str, Any]],
    variants: list[str],
    runs: int,
    seed: int,
) -> tuple[
    list[tuple[dict[str, Any], str, int, int]],
    tuple[str, str, int] | None,
]:
    jobs: list[tuple[dict[str, Any], str, int, int]] = []
    next_seed = seed
    for case in cases:
        for variant in variants:
            if variant not in case["variants"]:
                continue
            for repetition in range(1, runs + 1):
                next_seed += 1
                jobs.append((case, variant, repetition, next_seed))

    canary_index: int | None = next(
        (
            index
            for index, (case, variant, repetition, _) in enumerate(jobs)
            if case["id"] == "trivial-fast-path"
            and variant == "candidate"
            and repetition == 1
        ),
        None,
    )
    if canary_index is None:
        canary_index = next(
            (
                index
                for index, (case, _, repetition, _) in enumerate(jobs)
                if case.get("requires_write") and repetition == 1
            ),
            None,
        )

    canary: tuple[dict[str, Any], str, int, int] | None = None
    if canary_index is not None:
        canary = jobs.pop(canary_index)
    random.Random(seed).shuffle(jobs)
    if canary is not None:
        jobs.insert(0, canary)
        canary_key = (canary[0]["id"], canary[1], canary[2])
    else:
        canary_key = None
    return jobs, canary_key


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
        input_tokens = [
            item.provider_result.input_tokens
            for item in valid
            if item.provider_result.input_tokens is not None
        ]
        cached_input_tokens = [
            item.provider_result.cached_input_tokens
            for item in valid
            if item.provider_result.cached_input_tokens is not None
        ]
        output_tokens = [
            item.provider_result.output_tokens
            for item in valid
            if item.provider_result.output_tokens is not None
        ]
        total_tokens = [
            item.provider_result.input_tokens + item.provider_result.output_tokens
            for item in valid
            if item.provider_result.input_tokens is not None
            and item.provider_result.output_tokens is not None
        ]
        uncached_input_tokens = [
            max(
                item.provider_result.input_tokens
                - (item.provider_result.cached_input_tokens or 0),
                0,
            )
            for item in valid
            if item.provider_result.input_tokens is not None
        ]
        uncached_plus_output_tokens = [
            max(
                item.provider_result.input_tokens
                - (item.provider_result.cached_input_tokens or 0),
                0,
            )
            + item.provider_result.output_tokens
            for item in valid
            if item.provider_result.input_tokens is not None
            and item.provider_result.output_tokens is not None
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
                "pass_all": (
                    len(valid) == len(items)
                    and bool(valid)
                    and all(item.grade.passed for item in valid)
                ),
                "median_duration_ms": (
                    round(statistics.median(durations)) if durations else None
                ),
                "median_cost_usd": statistics.median(costs) if costs else None,
                "median_input_tokens": (
                    round(statistics.median(input_tokens)) if input_tokens else None
                ),
                "median_cached_input_tokens": (
                    round(statistics.median(cached_input_tokens))
                    if cached_input_tokens
                    else None
                ),
                "median_output_tokens": (
                    round(statistics.median(output_tokens)) if output_tokens else None
                ),
                "median_total_tokens": (
                    round(statistics.median(total_tokens)) if total_tokens else None
                ),
                "median_uncached_input_tokens": (
                    round(statistics.median(uncached_input_tokens))
                    if uncached_input_tokens
                    else None
                ),
                "median_uncached_plus_output_tokens": (
                    round(statistics.median(uncached_plus_output_tokens))
                    if uncached_plus_output_tokens
                    else None
                ),
                "median_dispatch_count": (
                    statistics.median(
                        item.provider_result.dispatch_count for item in valid
                    )
                    if valid
                    else None
                ),
                "median_collaboration_wait_count": (
                    statistics.median(
                        item.provider_result.collaboration_wait_count
                        for item in valid
                    )
                    if valid
                    else None
                ),
                "median_command_count": (
                    statistics.median(
                        item.provider_result.command_count for item in valid
                    )
                    if valid
                    else None
                ),
                "median_command_round_count": (
                    statistics.median(
                        item.provider_result.command_round_count for item in valid
                    )
                    if valid
                    else None
                ),
                "median_model_turn_count": (
                    statistics.median(
                        item.provider_result.model_turn_count for item in valid
                    )
                    if valid
                    else None
                ),
                "median_skill_read_count": (
                    statistics.median(
                        item.provider_result.skill_read_count for item in valid
                    )
                    if valid
                    else None
                ),
                "median_review_skill_read_count": (
                    statistics.median(
                        item.provider_result.review_skill_read_count for item in valid
                    )
                    if valid
                    else None
                ),
                "median_docs_read_count": (
                    statistics.median(
                        item.provider_result.docs_read_count for item in valid
                    )
                    if valid
                    else None
                ),
                "median_git_command_count": (
                    statistics.median(
                        item.provider_result.git_command_count for item in valid
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

    if not enforce_performance:
        return gates

    def add_noninferiority_gate(
        *,
        name: str,
        case_ids: list[str],
        baseline_variant: str,
        candidate_variant: str = "candidate",
        speed_limit: float = 1.15,
        token_limit: float = 1.15,
        uncached_plus_output_limit: float | None = None,
        cost_limit: float | None = None,
        candidate_command_limit: int | None = None,
        candidate_command_round_limit: int | None = None,
    ) -> None:
        baseline_rows = [
            rows.get((case_id, baseline_variant)) for case_id in case_ids
        ]
        candidate_rows = [
            rows.get((case_id, candidate_variant)) for case_id in case_ids
        ]
        complete = all(baseline_rows) and all(candidate_rows)
        if not complete:
            gates.append(
                {
                    "case_id": name,
                    "passed": False,
                    "detail": "all baseline and candidate rows are required",
                }
            )
            return

        baseline_rows = [row for row in baseline_rows if row is not None]
        candidate_rows = [row for row in candidate_rows if row is not None]
        valid_complete = all(
            row["valid_runs"] == row["runs"]
            for row in baseline_rows + candidate_rows
        )
        candidate_pass_all = all(row["pass_all"] for row in candidate_rows)
        quality_not_worse = all(
            candidate["pass_rate"] is not None
            and baseline["pass_rate"] is not None
            and candidate["pass_rate"] >= baseline["pass_rate"]
            for baseline, candidate in zip(baseline_rows, candidate_rows)
        )

        def summed_ratio(metric: str) -> float | None:
            baseline_values = [row.get(metric) for row in baseline_rows]
            candidate_values = [row.get(metric) for row in candidate_rows]
            if any(value is None for value in baseline_values + candidate_values):
                return None
            baseline_total = sum(baseline_values)
            if not baseline_total:
                return None
            return sum(candidate_values) / baseline_total

        speed_ratio = summed_ratio("median_duration_ms")
        token_ratio = summed_ratio("median_total_tokens")
        uncached_plus_output_ratio = summed_ratio(
            "median_uncached_plus_output_tokens"
        )
        cost_ratio = summed_ratio("median_cost_usd")
        candidate_command_total = (
            sum(row.get("median_command_count") or 0 for row in candidate_rows)
            if all(row.get("median_command_count") is not None for row in candidate_rows)
            else None
        )
        candidate_command_round_total = (
            sum(row.get("median_command_round_count") or 0 for row in candidate_rows)
            if all(
                row.get("median_command_round_count") is not None
                for row in candidate_rows
            )
            else None
        )
        speed_ok = speed_ratio is not None and speed_ratio <= speed_limit
        token_ok = token_ratio is not None and token_ratio <= token_limit
        uncached_plus_output_ok = (
            True
            if uncached_plus_output_limit is None
            else uncached_plus_output_ratio is not None
            and uncached_plus_output_ratio <= uncached_plus_output_limit
        )
        cost_ok = (
            True
            if cost_limit is None or cost_ratio is None
            else cost_ratio <= cost_limit
        )
        command_ok = (
            True
            if candidate_command_limit is None
            else candidate_command_total is not None
            and candidate_command_total <= candidate_command_limit
        )
        command_round_ok = (
            True
            if candidate_command_round_limit is None
            else candidate_command_round_total is not None
            and candidate_command_round_total <= candidate_command_round_limit
        )
        gates.append(
            {
                "case_id": name,
                "passed": (
                    valid_complete
                    and candidate_pass_all
                    and quality_not_worse
                    and speed_ok
                    and token_ok
                    and uncached_plus_output_ok
                    and cost_ok
                    and command_ok
                    and command_round_ok
                ),
                "detail": {
                    "cases": case_ids,
                    "valid_complete": valid_complete,
                    "candidate_pass_all": candidate_pass_all,
                    "quality_not_worse": quality_not_worse,
                    "speed_ratio": speed_ratio,
                    f"speed_ok_at_{speed_limit:.2f}": speed_ok,
                    "token_ratio": token_ratio,
                    f"token_ok_at_{token_limit:.2f}": token_ok,
                    "uncached_plus_output_ratio": uncached_plus_output_ratio,
                    "uncached_plus_output_limit": uncached_plus_output_limit,
                    "uncached_plus_output_ok": uncached_plus_output_ok,
                    "cost_ratio": cost_ratio,
                    "cost_limit": cost_limit,
                    "cost_ok_when_reported": cost_ok,
                    "candidate_command_total": candidate_command_total,
                    "candidate_command_limit": candidate_command_limit,
                    "candidate_command_ok": command_ok,
                    "candidate_command_round_total": candidate_command_round_total,
                    "candidate_command_round_limit": candidate_command_round_limit,
                    "candidate_command_round_ok": command_round_ok,
                },
            }
        )

    workflow_cases = [
        case
        for case in cases
        if case["suite"] == "workflow"
        and "legacy" in case["variants"]
        and "candidate" in case["variants"]
    ]
    workflow_ids = [case["id"] for case in workflow_cases]
    if workflow_ids:
        add_noninferiority_gate(
            name="workflow-vs-legacy",
            case_ids=workflow_ids,
            baseline_variant="legacy",
            speed_limit=1.10,
            token_limit=1.10,
            uncached_plus_output_limit=1.00,
            cost_limit=1.00,
            candidate_command_limit=48,
            candidate_command_round_limit=25,
        )
        if all("current" in case["variants"] for case in workflow_cases):
            add_noninferiority_gate(
                name="workflow-vs-current",
                case_ids=workflow_ids,
                baseline_variant="current",
            )

    sequential_case = next(
        (
            case
            for case in cases
            if case["id"] == "parallel-three-modules-sequential"
            and "legacy" in case["variants"]
            and "candidate" in case["variants"]
        ),
        None,
    )
    if sequential_case is not None:
        add_noninferiority_gate(
            name="sequential-implementation-vs-legacy",
            case_ids=[sequential_case["id"]],
            baseline_variant="legacy",
            speed_limit=1.10,
            token_limit=1.10,
            uncached_plus_output_limit=1.00,
            cost_limit=1.00,
        )

    for case in cases:
        baseline_case = case.get("performance_baseline_case")
        if not case.get("performance_gate") or not baseline_case:
            continue
        orchestrated = rows.get((case["id"], "candidate"))
        sequential = rows.get((baseline_case, "candidate"))
        if not orchestrated or not sequential:
            gates.append(
                {
                    "case_id": case["id"],
                    "passed": False,
                    "detail": "candidate sequential and orchestrated rows are required",
                }
            )
            continue
        speed_ratio = (
            orchestrated["median_duration_ms"] / sequential["median_duration_ms"]
            if sequential["median_duration_ms"]
            and orchestrated["median_duration_ms"]
            else None
        )
        token_ratio = (
            orchestrated["median_total_tokens"] / sequential["median_total_tokens"]
            if sequential["median_total_tokens"]
            and orchestrated["median_total_tokens"]
            else None
        )
        quality_ok = (
            sequential["pass_all"]
            and orchestrated["pass_all"]
            and orchestrated["pass_rate"] >= sequential["pass_rate"]
        )
        speed_ok = speed_ratio is not None and speed_ratio <= 0.80
        token_ok = token_ratio is not None and token_ratio <= 1.50
        dispatch_ok = (
            (
                orchestrated["median_dispatch_count"] is not None
                and orchestrated["median_dispatch_count"] >= 2
            )
            or (
                orchestrated["median_collaboration_wait_count"] is not None
                and orchestrated["median_collaboration_wait_count"] >= 2
            )
        )
        gates.append(
            {
                "case_id": case["id"],
                "passed": quality_ok and speed_ok and token_ok and dispatch_ok,
                "detail": {
                    "quality_ok": quality_ok,
                    "speed_ratio": speed_ratio,
                    "speed_ok_at_0.80": speed_ok,
                    "token_ratio": token_ratio,
                    "token_ok_at_1.50": token_ok,
                    "dispatch_ok": dispatch_ok,
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
        f"- Reasoning effort: `{payload['reasoning_effort'] or 'provider default'}`",
        f"- Service tier: `{payload['service_tier'] or 'provider default'}`",
        f"- Windows sandbox: `{payload['windows_sandbox'] or 'not applicable'}`",
        f"- Repetitions: {payload['runs_per_case']}",
        f"- Write canary: `{payload['write_canary'] or 'not applicable'}`",
        "",
        "| Case | Variant | Valid/total | Passes | Pass rate | Median ms | Median tokens | Median cost |",
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
        tokens = (
            str(row["median_total_tokens"])
            if row["median_total_tokens"] is not None
            else "n/a"
        )
        lines.append(
            f"| {row['case_id']} | {row['variant']} | "
            f"{row['valid_runs']}/{row['runs']} | {row['passes']} | {pass_rate} | "
            f"{duration} | {tokens} | {cost} |"
        )
    lines.extend(
        [
            "",
            "## Efficiency trajectory",
            "",
            "| Case | Variant | Uncached+output | Commands/rounds | Turns | Skills/review | Docs | Git | Dispatch/waits |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload["aggregate"]["rows"]:
        def metric(name: str) -> str:
            value = row.get(name)
            return str(value) if value is not None else "n/a"

        lines.append(
            f"| {row['case_id']} | {row['variant']} | "
            f"{metric('median_uncached_plus_output_tokens')} | "
            f"{metric('median_command_count')}/"
            f"{metric('median_command_round_count')} | "
            f"{metric('median_model_turn_count')} | "
            f"{metric('median_skill_read_count')}/"
            f"{metric('median_review_skill_read_count')} | "
            f"{metric('median_docs_read_count')} | "
            f"{metric('median_git_command_count')} | "
            f"{metric('median_dispatch_count')}/"
            f"{metric('median_collaboration_wait_count')} |"
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


def _deserialize_run_result(raw: dict[str, Any]) -> RunResult:
    provider_data = dict(raw["provider_result"])
    provider_data.update(_trajectory_metrics(provider_data.get("events", [])))
    provider_fields = ProviderResult.__dataclass_fields__
    provider = ProviderResult(
        **{key: value for key, value in provider_data.items() if key in provider_fields}
    )
    return RunResult(
        case_id=raw["case_id"],
        suite=raw["suite"],
        variant=raw["variant"],
        provider=raw["provider"],
        repetition=int(raw["repetition"]),
        seed=int(raw["seed"]),
        source_identity=raw["source_identity"],
        provider_result=provider,
        grade=GradeResult(**raw["grade"]),
    )


def _load_baseline_results(
    paths: list[Path],
    *,
    args: argparse.Namespace,
    cases: list[dict[str, Any]],
) -> list[RunResult]:
    selected = {case["id"]: set(case["variants"]) for case in cases}
    catalog = {case["id"]: case for case in _load_cases()}
    for case in cases:
        baseline_id = case.get("performance_baseline_case")
        if baseline_id in catalog:
            selected[baseline_id] = set(catalog[baseline_id]["variants"])
    expected = {
        "provider": args.provider,
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "service_tier": args.service_tier,
        "runs_per_case": args.runs,
        "seed": args.seed,
        "current_ref": args.current_ref,
    }
    reused: dict[tuple[str, str, int], RunResult] = {}
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EvalError(f"cannot read baseline report {path}: {exc}") from exc
        mismatches = [
            f"{key}={payload.get(key)!r} (expected {value!r})"
            for key, value in expected.items()
            if payload.get(key) != value
        ]
        if mismatches:
            raise EvalError(
                f"incompatible baseline report {path}: " + "; ".join(mismatches)
            )
        for raw in payload.get("results", []):
            case_id = raw.get("case_id")
            variant = raw.get("variant")
            repetition = raw.get("repetition")
            if (
                case_id not in selected
                or variant not in selected[case_id]
                or not isinstance(repetition, int)
                or repetition > args.runs
            ):
                continue
            result = _deserialize_run_result(raw)
            reused.setdefault((case_id, variant, repetition), result)
    return list(reused.values())


def _merge_results(
    reused: list[RunResult], fresh: list[RunResult]
) -> list[RunResult]:
    merged = {
        (result.case_id, result.variant, result.repetition): result
        for result in reused
    }
    for result in fresh:
        merged[(result.case_id, result.variant, result.repetition)] = result
    return list(merged.values())


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
    parser.add_argument(
        "--enforce-gates",
        action="store_true",
        help="Enforce non-inferiority and orchestration gates with the selected run count.",
    )
    parser.add_argument("--seed", type=int, default=20260724)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--model")
    parser.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high", "xhigh", "max", "ultra"),
    )
    parser.add_argument("--service-tier")
    parser.add_argument(
        "--windows-sandbox",
        choices=("elevated", "unelevated"),
        help="Native Windows sandbox backend for Codex (defaults to unelevated on Windows).",
    )
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
        "--baseline-report",
        action="append",
        type=Path,
        default=[],
        help=(
            "Reuse compatible results from report.json; repeat for multiple reports. "
            "Fresh runs replace matching case/variant/repetition rows."
        ),
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
    args.baseline_report = [path.resolve() for path in args.baseline_report]
    cases = [case for case in _load_cases() if _case_selected(case, args)]
    if not cases:
        raise EvalError("no eval cases selected")
    if args.list:
        for case in cases:
            print(f"{case['id']}\t{case['suite']}\t{','.join(case['variants'])}")
        return 0
    if args.provider != "codex" and (
        args.reasoning_effort is not None
        or args.service_tier is not None
        or args.windows_sandbox is not None
    ):
        parser.error(
            "--reasoning-effort, --service-tier, and --windows-sandbox "
            "are Codex-only"
        )
    if args.provider == "codex" and os.name == "nt" and args.windows_sandbox is None:
        # The elevated backend can leave newly-created files readable only by the
        # sandbox account. The eval parent must read every artifact for grading.
        args.windows_sandbox = "unelevated"
    enforce_gates = args.release or args.enforce_gates
    if enforce_gates and args.provider == "codex" and not args.model:
        parser.error("--model is required when comparison gates are enforced")

    variants = args.variant or ["legacy", "current", "candidate"]
    jobs, canary_key = _build_jobs(cases, variants, args.runs, args.seed)
    reused_results = _load_baseline_results(
        args.baseline_report, args=args, cases=cases
    )
    base_invocations = len(jobs)
    invocations = base_invocations * (2 if args.retry_infrastructure else 1)
    print(
        f"Provider={args.provider}; model={args.model or 'default'}; "
        f"reasoning={args.reasoning_effort or 'default'}; "
        f"tier={args.service_tier or 'default'}; "
        f"windows-sandbox={args.windows_sandbox or 'n/a'}; "
        f"cases={len(cases)}; maximum invocations={invocations}; "
        f"reused baseline runs={len(reused_results)}; "
        f"per-Claude-call budget={args.max_budget_usd or 'not set'}"
    )
    if not args.yes:
        raise EvalError("rerun with --yes after approving this bounded provider run")

    version = _provider_version(args.provider)
    results: list[RunResult] = []
    for case, variant, repetition, run_seed in jobs:
        job_key = (case["id"], variant, repetition)
        prefix = "[write-canary] " if job_key == canary_key else ""
        print(
            f"{prefix}[{case['id']}] {variant} "
            f"run {repetition}/{args.runs}",
            flush=True,
        )
        result = _single_run(
            case,
            variant,
            args.provider,
            repetition,
            run_seed,
            args,
        )
        results.append(result)
        if job_key == canary_key:
            infrastructure_blocked = (
                result.provider_result.status == "infrastructure_failure"
            )
            candidate_behavior_failed = (
                variant == "candidate" and not result.grade.passed
            )
            if infrastructure_blocked or candidate_behavior_failed:
                reason = (
                    "provider infrastructure"
                    if infrastructure_blocked
                    else "candidate failed the canary task"
                )
                print(
                    f"Write canary failed ({reason}); stopping before the "
                    "remaining provider calls.",
                    flush=True,
                )
                break

    fresh_results = results
    results = _merge_results(reused_results, fresh_results)
    aggregate = _aggregate(results)
    gates = _comparison_gates(
        cases, aggregate, enforce_performance=enforce_gates
    )
    canary_label: str | None = None
    if canary_key is not None:
        canary_result = next(
            (
                result
                for result in results
                if (
                    result.case_id,
                    result.variant,
                    result.repetition,
                )
                == canary_key
            ),
            None,
        )
        if canary_result is not None:
            canary_label = (
                f"{canary_key[0]}/{canary_key[1]}/run-{canary_key[2]}: "
                f"{canary_result.provider_result.status}, "
                f"grade={'pass' if canary_result.grade.passed else 'fail'}"
            )
    generated_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "generated_at": generated_at,
        "provider": args.provider,
        "provider_version": version,
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "service_tier": args.service_tier,
        "windows_sandbox": args.windows_sandbox,
        "runs_per_case": args.runs,
        "seed": args.seed,
        "current_ref": args.current_ref,
        "write_canary": canary_label,
        "baseline_reports": [str(path) for path in args.baseline_report],
        "fresh_results": len(fresh_results),
        "reused_results": len(results) - len(fresh_results),
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
        and result.variant == "candidate"
        and not result.grade.passed
        for result in results
    )
    gate_failures = any(not gate["passed"] for gate in gates)
    if infrastructure_failures:
        return 2
    return 1 if hard_failures or gate_failures else 0
