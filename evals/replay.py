#!/usr/bin/env python3
"""Replay finished tasks of a real project against a copy of the studio plugin.

Usage: python evals/replay.py --label NAME --project DIR [--plugin DIR] [--task T6.2]
                              [--model opus] [--effort medium] [--mode-note TEXT] [--keep]

For each task the project is cloned at the commit before the task was done, into a
temporary folder with no remote, so the real project is never touched. Its AGENTS.md is
replaced by the plugin's template with the project's own Project commands. The agent gets
the task and the interface the real implementation used; afterwards the real tests of
that implementation, which the agent never saw, are run against its work.

Every run is a long real session on the owner's account.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run as runner  # noqa: E402

# task -> commit before it, commit that did it, hidden tests, the files whose public
# interface the agent is given, and the request in the owner's language.
TASKS = {
    "T6.2": {
        "base": "1bd25bd", "done": "8836045",
        "hidden": ["tests/test_slab_mesh.py"],
        "interface": ["src/lira_sapr_mcp/postprocessing/mesh.py"],
        "prompt": "Сделай задачу T6.2 из docs/TASKS.md и остановись после неё: T6.3 не "
                  "начинай.",
    },
    "T6.3": {
        "base": "8836045", "done": "dcaae57",
        "hidden": ["tests/test_slab_deflection.py"],
        "interface": ["src/lira_sapr_mcp/postprocessing/deflection.py"],
        "prompt": "Сделай задачу T6.3 из docs/TASKS.md и остановись после неё: T6.4 не "
                  "начинай.",
    },
}
INTERFACE_NOTE = (
    "\n\nИнтерфейс модуля согласован заранее, держись его точно (имена, параметры, поля, "
    "единицы, правила из описания модуля). Тела функций и закрытые помощники — твои.\n\n")


def git(root, *args):
    done = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return done.stdout


def interface_of(source):
    """The public face of a module: its docstring, imports, constants, dataclasses and
    the signatures and docstrings of public functions, without their bodies."""
    lines, out, index = source.splitlines(), [], 0
    while index < len(lines):
        line = lines[index]
        if re.match(r"(async )?def _", line):  # a private helper: skip it whole
            index += 1
            while index < len(lines) and (not lines[index].strip()
                                          or lines[index].startswith((" ", ")"))):
                index += 1
            continue
        if re.match(r"(async )?def ", line):
            while not lines[index].rstrip().endswith(":"):  # a signature over several lines
                out.append(lines[index])
                index += 1
            out.append(lines[index])
            index += 1
            if index < len(lines) and lines[index].lstrip().startswith('"""'):
                closed = lines[index].count('"""') == 2
                out.append(lines[index])
                index += 1
                while not closed:  # the rest of a docstring over several lines
                    closed = '"""' in lines[index]
                    out.append(lines[index])
                    index += 1
            out.append("    ...")
            while index < len(lines) and (not lines[index].strip()
                                          or lines[index].startswith(" ")):
                index += 1
            out.append("")
            continue
        out.append(line)
        index += 1
    return "\n".join(out).rstrip() + "\n"


def prepare(project, task, plugin, workspace):
    """Clone the project at the task's base commit and give it the plugin's AGENTS.md."""
    subprocess.run(["git", "clone", "-q", "--no-hardlinks", str(project), str(workspace)],
                   check=True, capture_output=True)
    git(workspace, "remote", "remove", "origin")  # the real project cannot be pushed to
    git(workspace, "checkout", "-q", "-B", "replay", task["base"])
    git(workspace, "config", "user.email", "eval@example.com")
    git(workspace, "config", "user.name", "Eval")
    own = (workspace / "AGENTS.md").read_text(encoding="utf-8")
    template = (plugin / "skills" / "idea" / "project" / "AGENTS.md").read_text(encoding="utf-8")
    keep = "".join(re.findall(r"^## Project rules\n.*?(?=^## )|^## Project commands\n.*",
                              own, re.DOTALL | re.MULTILINE))
    head = re.split(r"^## Project commands\n", template, flags=re.MULTILINE)[0]
    (workspace / "AGENTS.md").write_text(head + keep, encoding="utf-8", newline="\n")
    git(workspace, "commit", "-q", "-am", "Use the AGENTS.md of the plugin under test")
    synced = subprocess.run(["uv", "sync", "-q"], cwd=workspace, capture_output=True, text=True)
    if synced.returncode:
        raise RuntimeError(f"uv sync failed: {synced.stderr[-500:]}")
    return git(workspace, "rev-parse", "HEAD").strip()


def pytest_counts(workspace, *paths):
    """(passed, failed or errored) from a quiet pytest run of the given paths."""
    done = subprocess.run(["uv", "run", "pytest", "-q", "-p", "no:cacheprovider", *paths],
                          cwd=workspace, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=1800)
    tail = (done.stdout + done.stderr)[-600:]
    count = lambda word: sum(int(n) for n in re.findall(rf"(\d+) {word}", tail))  # noqa: E731
    return count("passed"), count("failed") + count("error"), tail


def accept(project, task, workspace):
    """Run the real implementation's tests against the agent's work."""
    hidden = []
    for index, path in enumerate(task["hidden"]):
        target = workspace / "tests" / f"hidden_accept_{index}.py"
        target.write_text(git(project, "show", f"{task['done']}:{path}"), encoding="utf-8")
        hidden.append(str(target.relative_to(workspace)).replace("\\", "/"))
    total = sum(len(re.findall(r"^def test_", (workspace / path).read_text(encoding="utf-8"),
                               re.MULTILINE)) for path in hidden)
    passed, failed, tail = pytest_counts(workspace, *hidden)
    for path in hidden:
        (workspace / path).unlink()
    return {"hidden_passed": passed, "hidden_failed": failed, "hidden_functions": total,
            "hidden_tail": tail}


def replay(name, args, plugin, project, out):
    task = TASKS[name]
    work = Path(tempfile.gettempdir()) / "studio-replay" / args.label / name.replace(".", "-")
    if work.exists():
        subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", str(work)], capture_output=True)
    work.mkdir(parents=True)
    workspace = work / "ws"
    base = prepare(project, task, plugin, workspace)
    contract = "".join(
        f"`{path}`:\n\n```python\n{interface_of(git(project, 'show', task['done'] + ':' + path))}"
        "```\n\n" for path in task["interface"])
    prompt = task["prompt"] + INTERFACE_NOTE + contract + (args.mode_note or "")
    started = time.time()
    session, lines, stderr = runner.session(workspace, prompt, plugin, args.model, args.effort,
                                            max_turns=300, timeout=5400)
    own_passed, own_failed, own_tail = pytest_counts(workspace)
    record = {
        "task": name, "label": args.label, "metrics": session.metrics(),
        "wall_seconds": round(time.time() - started),
        **accept(project, task, workspace),
        "own_tests_passed": own_passed, "own_tests_failed": own_failed,
        "commits": int(git(workspace, "rev-list", "--count", f"{base}..HEAD") or 0),
        "clean_tree": git(workspace, "status", "--porcelain").strip() == "",
        "ruff_ok": subprocess.run(["uv", "run", "ruff", "check", "-q"], cwd=workspace,
                                  capture_output=True).returncode == 0,
        "lines_changed": git(workspace, "diff", "--shortstat", base, "HEAD").strip(),
        "final": session.final[-2500:], "stderr": "" if session.result else stderr,
    }
    stem = f"{name.replace('.', '-')}"
    (out / f"{stem}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    (out / f"{stem}.stream.jsonl").write_text("\n".join(lines), encoding="utf-8")
    (out / f"{stem}.diff").write_text(git(workspace, "diff", base, "HEAD"), encoding="utf-8")
    if not args.keep:
        subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", str(work)], capture_output=True)
    return record


def summarise(records, args):
    lines = [f"# Replay: {args.label}", "",
             f"Model {args.model}, effort {args.effort}; {time.strftime('%Y-%m-%d %H:%M')}", "",
             "| Task | Hidden tests | Own tests | Ruff | Commits | Clean | Turns | Agents | "
             "Output | Cache read | Cost $ | Minutes |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for record in records:
        metrics = record["metrics"]
        lines.append(
            f"| {record['task']} | {record['hidden_passed']} passed, "
            f"{record['hidden_failed']} failed | {record['own_tests_passed']} passed, "
            f"{record['own_tests_failed']} failed | {'ok' if record['ruff_ok'] else 'fails'} | "
            f"{record['commits']} | {'yes' if record['clean_tree'] else 'no'} | "
            f"{metrics['turns']} | {metrics['agents']} ({', '.join(metrics['agent_types'])}) | "
            f"{metrics['output']} | {metrics['cache_read']} | {metrics['cost_usd']} | "
            f"{round(record['wall_seconds'] / 60)} |")
    lines.append("")
    for record in records:
        models = "; ".join(f"{name}: {used['output']} out, ${used['cost_usd']}"
                           for name, used in record["metrics"]["models"].items())
        lines.append(f"- {record['task']} by model: {models}")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--plugin", default=str(HERE.parent / "plugins" / "studio"))
    parser.add_argument("--task", action="append", choices=sorted(TASKS))
    parser.add_argument("--model", default="opus")
    parser.add_argument("--effort", default="medium")
    parser.add_argument("--mode-note", help="text added to the request, for comparing modes")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()
    plugin, project = Path(args.plugin).resolve(), Path(args.project).resolve()
    out = HERE / "results" / f"replay-{args.label}"
    out.mkdir(parents=True, exist_ok=True)
    records = [replay(name, args, plugin, project, out) for name in args.task or sorted(TASKS)]
    (out / "summary.md").write_text(summarise(records, args), encoding="utf-8")
    print((out / "summary.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
