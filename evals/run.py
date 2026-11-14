#!/usr/bin/env python3
"""Run behaviour scenarios against a copy of the studio plugin with headless Claude Code.

Usage: python evals/run.py --label NAME [--plugin DIR] [--runs N] [--case GLOB]
                           [--model sonnet] [--effort medium] [--jobs N] [--keep]

Each case builds a small project in a temporary folder with the plugin's own setup script,
runs `claude -p` there with only that plugin loaded, and checks the result with code the
agent never sees. `claude plugin eval` is not used: it does not load a project's
CLAUDE.md, and on native Windows it refuses every run that needs a shell.

Every run is a real model call on the owner's account. Results go to
evals/results/<label>/: one JSON per run and summary.md.
"""

import argparse
import fnmatch
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))  # cases import fixture.py
TOOLS = ["Bash", "PowerShell", "Read", "Edit", "Write", "Glob", "Grep", "Agent", "Skill",
         "TodoWrite"]
# The installed copy of the plugin stays off, so only --plugin-dir is under test.
SETTINGS = json.dumps({"enabledPlugins": {"studio@agents-toolkit": False}})


def load_case(folder):
    spec = importlib.util.spec_from_file_location(f"case_{folder.name}", folder / "case.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Run:
    """What one headless session did, read from its stream-json output."""

    def __init__(self, lines):
        self.events = []
        for line in lines:
            try:
                self.events.append(json.loads(line))
            except ValueError:
                continue
        self.result = next((e for e in reversed(self.events) if e.get("type") == "result"), {})
        self.final = self.result.get("result") or ""
        self.calls = []  # (tool, input, is_subagent) in order
        self.texts = []
        for event in self.events:
            if event.get("type") != "assistant":
                continue
            inner = bool(event.get("parent_tool_use_id"))
            for block in (event.get("message") or {}).get("content") or []:
                if block.get("type") == "tool_use":
                    self.calls.append((block.get("name"), block.get("input") or {}, inner))
                elif block.get("type") == "text":
                    self.texts.append(block.get("text") or "")

    def agents(self):
        return [call for call in self.calls if call[0] in ("Agent", "Task") and not call[2]]

    def first_edit(self, part):
        """Index of the first file edit whose path contains `part`, or None."""
        for index, (tool, tool_input, _) in enumerate(self.calls):
            path = str(tool_input.get("file_path", "")).replace("\\", "/")
            if tool in ("Edit", "Write", "MultiEdit") and part in path:
                return index
        return None

    def everything(self):
        """All text the session saw or wrote, for checking that a secret never appeared."""
        return "\n".join(json.dumps(event, ensure_ascii=False) for event in self.events)

    def metrics(self):
        usage = self.result.get("usage") or {}
        models = {}
        for name, used in (self.result.get("modelUsage") or {}).items():
            models[name] = {
                "input": used.get("inputTokens", 0),
                "cache_read": used.get("cacheReadInputTokens", 0),
                "cache_write": used.get("cacheCreationInputTokens", 0),
                "output": used.get("outputTokens", 0),
                "cost_usd": round(used.get("costUSD", 0), 4),
            }
        return {
            "turns": self.result.get("num_turns"),
            "seconds": round((self.result.get("duration_ms") or 0) / 1000),
            "cost_usd": round(self.result.get("total_cost_usd") or 0, 4),
            "input": usage.get("input_tokens", 0),
            "cache_read": usage.get("cache_read_input_tokens", 0),
            "cache_write": usage.get("cache_creation_input_tokens", 0),
            "output": usage.get("output_tokens", 0),
            "agents": len(self.agents()),
            "agent_types": [call[1].get("subagent_type") or "default" for call in self.agents()],
            "models": models,
            "error": None if self.result.get("subtype") == "success"
            else (self.result.get("subtype") or "no result"),
        }


def run_one(case, folder, plugin, args, number, out):
    work = Path(tempfile.gettempdir()) / "studio-evals" / args.label / f"{folder.name}-{number}"
    shutil.rmtree(work, ignore_errors=True)
    workspace = work / "ws"
    workspace.mkdir(parents=True)
    case.setup(workspace, plugin)
    command = [shutil.which("claude") or "claude", "-p",
               "--model", getattr(case, "MODEL", None) or args.model,
               "--effort", args.effort,
               "--plugin-dir", str(plugin),
               "--settings", SETTINGS,
               "--setting-sources", "project,local",
               "--output-format", "stream-json", "--verbose",
               "--max-turns", str(getattr(case, "MAX_TURNS", 80)),
               "--allowedTools", *TOOLS]
    started = time.time()
    try:
        done = subprocess.run(command, cwd=workspace, input=case.PROMPT, capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=getattr(case, "TIMEOUT", 1800))
        lines, stderr = done.stdout.splitlines(), done.stderr[-2000:]
    except subprocess.TimeoutExpired as expired:
        output = expired.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        lines, stderr = output.splitlines(), "timed out"
    run = Run(lines)
    try:
        checks = case.check(workspace, run)
    except Exception as error:  # a broken check is a failed run, not a crashed suite
        checks = {f"check crashed: {error}": False}
    record = {"case": folder.name, "run": number, "checks": checks,
              "score": round(sum(checks.values()) / max(len(checks), 1), 3),
              "metrics": run.metrics(), "wall_seconds": round(time.time() - started),
              "final": run.final[-1500:], "stderr": stderr if not run.result else ""}
    (out / f"{folder.name}-{number}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / f"{folder.name}-{number}.stream.jsonl").write_text("\n".join(lines), encoding="utf-8")
    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)
    print(f"{folder.name}-{number}: score {record['score']}, "
          f"{record['metrics']['turns']} turns, ${record['metrics']['cost_usd']}", flush=True)
    return record


def summarise(records, args, plugin):
    lines = [f"# {args.label}", "",
             f"Plugin: `{plugin}`; model {args.model}, effort {args.effort}; "
             f"{time.strftime('%Y-%m-%d %H:%M')}", "",
             "| Case | Runs | Score | Failed checks | Turns | Agents | Input | Cache read | "
             "Output | Cost $ | Seconds |", "|---|---|---|---|---|---|---|---|---|---|---|"]

    def mean(values):
        values = [value or 0 for value in values]
        return round(sum(values) / max(len(values), 1), 1)

    for name in sorted({record["case"] for record in records}):
        rows = [record for record in records if record["case"] == name]
        failed = sorted({check for record in rows
                         for check, passed in record["checks"].items() if not passed})
        metric = lambda key: mean([row["metrics"][key] for row in rows])  # noqa: E731
        lines.append(
            f"| {name} | {len(rows)} | {mean([row['score'] for row in rows])} | "
            f"{'; '.join(failed) or '-'} | {metric('turns')} | {metric('agents')} | "
            f"{metric('input'):.0f} | {metric('cache_read'):.0f} | {metric('output'):.0f} | "
            f"{metric('cost_usd')} | {metric('seconds'):.0f} |")
    total = round(sum(record["metrics"]["cost_usd"] for record in records), 2)
    lines += ["", f"Mean score {mean([record['score'] for record in records])}; "
                  f"list-price cost of the suite ${total}."]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", required=True)
    parser.add_argument("--plugin", default=str(REPO / "plugins" / "studio"))
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--case", default="*")
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--effort", default="medium")
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--keep", action="store_true", help="keep the temporary projects")
    args = parser.parse_args()
    plugin = Path(args.plugin).resolve()
    folders = [folder for folder in sorted((HERE / "cases").iterdir())
               if (folder / "case.py").is_file() and fnmatch.fnmatch(folder.name, args.case)]
    out = HERE / "results" / args.label
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(load_case(folder), folder, number)
            for folder in folders for number in range(1, args.runs + 1)]
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        records = list(pool.map(
            lambda job: run_one(job[0], job[1], plugin, args, job[2], out), jobs))
    (out / "summary.md").write_text(summarise(records, args, plugin), encoding="utf-8")
    print((out / "summary.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
