#!/usr/bin/env python3
"""Hooks shared by Claude Code and Codex for projects that follow the studio AGENTS.md.

Usage: studio_hooks.py session-start | guard | stop   (hook JSON arrives on stdin)

session-start  Give the agent the `Now` section of docs/TASKS.md, so a new session,
               a compacted context or the other tool picks up where work stopped.
guard          Block reading secrets and commands that destroy work.
stop           Before the agent stops, make sure changed work is reflected in TASKS.md.

A failure inside a hook never blocks the agent: errors go to stderr and exit 0.
"""

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

TASKS = Path("docs") / "TASKS.md"
MAX_CONTEXT_CHARS = 4000

SECRET_NAME = re.compile(
    r"^(\.env(\..+)?|.+\.(pem|key|p12|pfx|jks|keystore)|id_(rsa|dsa|ecdsa|ed25519)"
    r"|credentials(\.json)?|\.netrc|\.pgpass)$",
    re.IGNORECASE,
)
SAFE_SUFFIX = re.compile(r"\.(example|sample|template|dist)$", re.IGNORECASE)
SECRET_DIRS = {".ssh", ".aws", ".azure", ".gnupg"}
FILE_TOOLS = {"Read", "Edit", "Write", "MultiEdit", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}
DELETE_COMMANDS = {"rm", "remove-item", "ri", "del", "erase", "rd", "rmdir"}
WHOLE_FOLDER_WILDCARDS = {"*", "*.*", ".*"}

SECRET_REASON = (
    "This file may contain secrets, and AGENTS.md forbids reading or printing them. "
    "Put placeholders in .env.example and ask the owner to fill in the real values. "
    "To keep the file out of git, edit .gitignore with the file editor."
)
OUTSIDE_REASON = (
    "This deletes files outside the project folder, or the whole project. Delete "
    "specific paths inside the project instead, or ask the owner."
)
DESTRUCTIVE_PATTERNS = [
    (re.compile(r"\bgit\s+push\b.*(\s--force(-with-lease)?\b|\s-f\b|\s\+\S)"),
     "Force-pushing rewrites shared history. Ask the owner first."),
    (re.compile(r"\bgit\s+reset\b.*\s--hard\b"),
     "git reset --hard throws away uncommitted work. Commit it first or ask the owner."),
    (re.compile(r"\bgit\s+clean\b.*(\s-[a-zA-Z]*f|\s--force\b)"),
     "git clean -f permanently deletes untracked files. Remove specific files instead, "
     "or ask the owner."),
    (re.compile(r"\bgit\s+(checkout|restore)\b(?!.*--staged).*\s\.(\s|$)"),
     "This discards every uncommitted change in the project. Restore specific files "
     "instead, or ask the owner."),
    (re.compile(r"\b(mkfs|diskpart)\b|\bformat\s+[a-zA-Z]:|\bdd\b.*\bof=/dev/"),
     "Disk-level commands are never needed for this project."),
]


def emit(payload):
    print(json.dumps(payload))


def read_payload():
    raw = sys.stdin.buffer.read().decode("utf-8-sig", errors="replace").strip()
    return json.loads(raw) if raw else {}


def run_git(cwd, *args):
    try:
        result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout if result.returncode == 0 else None


def git_toplevel(cwd):
    output = run_git(cwd, "rev-parse", "--show-toplevel")
    return Path(output.strip()).resolve() if output else None


def project_root(cwd):
    start = Path(cwd or os.getcwd()).resolve()
    for directory in (start, *start.parents):
        if (directory / TASKS).is_file() or (directory / ".git").exists():
            return directory
    return start


def changed_files(root):
    """Absolute paths with uncommitted changes (untracked folders count as one entry)."""
    top = git_toplevel(root)
    output = run_git(top, "status", "--porcelain", "-z") if top else None
    if not output:
        return []
    entries = output.split("\0")
    paths = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue
        if entry[0] in "RC":
            index += 1  # a rename or copy is followed by its original path
        paths.append(top / entry[3:])
    return paths


def section(text, title):
    lines = text.splitlines()
    for start, line in enumerate(lines):
        if re.match(rf"^##\s+{re.escape(title)}\s*$", line.strip()):
            body = []
            for following in lines[start + 1:]:
                if following.startswith("## "):
                    break
                body.append(following)
            return "\n".join(body).strip()
    return ""


# --- session-start -------------------------------------------------------------------

def session_start(payload):
    root = project_root(payload.get("cwd"))
    tasks = root / TASKS
    if not tasks.is_file():
        return
    now = section(tasks.read_text(encoding="utf-8", errors="replace"), "Now")
    parts = ["Where work stands, from docs/TASKS.md (section Now):",
             now or "(The Now section is missing; restore it before continuing.)"]
    changes = changed_files(root)
    if changes:
        parts.append(f"There are uncommitted changes in {len(changes)} file(s); check "
                     "whether they belong to the active task before starting new work.")
    emit({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                 "additionalContext": "\n".join(parts)[:MAX_CONTEXT_CHARS]}})


# --- guard ---------------------------------------------------------------------------

def is_secret_path(value):
    if not value:
        return False
    parts = [p for p in str(value).strip().strip("'\"").replace("\\", "/").split("/") if p]
    if not parts:
        return False
    if any(part.lower() in SECRET_DIRS for part in parts[:-1]):
        return True
    return bool(SECRET_NAME.match(parts[-1])) and not SAFE_SUFFIX.search(parts[-1])


def command_segments(command):
    return [part.strip() for part in re.split(r"&&|\|\||[;|\n]", command) if part.strip()]


def command_words(segment):
    try:
        words = shlex.split(segment, posix=False)
    except ValueError:
        words = segment.split()
    return [word.strip("'\"") for word in words]


def secret_in_command(command):
    for segment in command_segments(command):
        words = command_words(segment)
        if (len(words) == 3 and words[0].lower() in {"cp", "copy", "copy-item"}
                and SAFE_SUFFIX.search(words[1]) and is_secret_path(words[2])):
            continue  # copying .env.example into place creates a file without reading one
        # Quoted text with spaces is prose (a commit message, an echo), not a path.
        unquoted = re.sub(r"\"[^\"]*\s[^\"]*\"|'[^']*\s[^']*'", " ", segment)
        if any(is_secret_path(t) for t in re.findall(r"[^\s'\"`;|&<>()=,]+", unquoted)):
            return True
    return False


def deletion_targets(segment):
    """Targets of a recursive delete in this segment, or None if it is not one."""
    words = command_words(segment)
    if words and words[0] == "sudo":
        words = words[1:]
    if not words or Path(words[0]).stem.lower() not in DELETE_COMMANDS:
        return None
    name = Path(words[0]).stem.lower()
    flags = [w for w in words[1:] if w.startswith("-") or (w.startswith("/") and len(w) == 2)]
    targets = [w for w in words[1:] if w not in flags]
    lowered = [f.lower() for f in flags]
    if name == "rm":
        short = "".join(f[1:] for f in lowered if not f.startswith("--"))
        recursive = "r" in short or "--recursive" in lowered
    else:
        recursive = any(f.startswith("-r") for f in lowered) or "/s" in lowered
    return targets if recursive else None


def is_inside(path, folder):
    try:
        path.relative_to(folder)
        return True
    except ValueError:
        return False


def unsafe_deletion(segment, cwd, payload):
    targets = deletion_targets(segment)
    if targets is None:
        return False
    if not targets:
        return True
    root = git_toplevel(cwd) or Path(cwd).resolve()
    scratch = [Path(tempfile.gettempdir()).resolve()]
    if payload.get("scratchpad_dir"):
        scratch.append(Path(payload["scratchpad_dir"]).resolve())
    for target in targets:
        if target.startswith(("~", "$", "%")):
            return True
        candidate = Path(target) if Path(target).is_absolute() else Path(cwd) / target
        wildcard = any(ch in candidate.name for ch in "*?[")
        resolved = (candidate.parent if wildcard else candidate).resolve()
        if is_inside(root, resolved) and (resolved != root or not wildcard
                                          or candidate.name in WHOLE_FOLDER_WILDCARDS):
            return True  # the project itself, or a folder that contains it
        if any(is_inside(resolved, folder) and resolved != folder for folder in scratch):
            continue
        if not is_inside(resolved, root):
            return True
    return False


def guard_reason(payload):
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    cwd = payload.get("cwd") or os.getcwd()

    if tool in FILE_TOOLS:
        path = tool_input.get("file_path") or tool_input.get("notebook_path")
        if not is_secret_path(path):
            return None
        creating = tool == "Write" and not Path(cwd, path).exists()
        return None if creating else SECRET_REASON
    if tool == "Grep":
        secret = is_secret_path(tool_input.get("path")) or is_secret_path(tool_input.get("glob"))
        return SECRET_REASON if secret else None

    command = tool_input.get("command")
    if isinstance(command, list):
        command = " ".join(str(part) for part in command)
    if not isinstance(command, str):
        return None
    if tool == "apply_patch":
        files = re.findall(r"^\*\*\* (?:Update|Delete) File: (.+)$", command, re.MULTILINE)
        return SECRET_REASON if any(is_secret_path(f) for f in files) else None
    if tool not in SHELL_TOOLS:
        return None
    if secret_in_command(command):
        return SECRET_REASON
    for segment in command_segments(command):
        for pattern, reason in DESTRUCTIVE_PATTERNS:
            if pattern.search(segment):
                return reason
        if unsafe_deletion(segment, cwd, payload):
            return OUTSIDE_REASON
    return None


def guard(payload):
    reason = guard_reason(payload)
    if reason:
        emit({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                     "permissionDecision": "deny",
                                     "permissionDecisionReason": reason}})


# --- stop ----------------------------------------------------------------------------

def stop(payload):
    if payload.get("stop_hook_active"):
        return
    root = project_root(payload.get("cwd"))
    tasks = root / TASKS
    if not tasks.is_file():
        return
    changed = [p for p in changed_files(root) if p.resolve() != tasks.resolve()]
    times = [p.stat().st_mtime for p in changed if p.exists()]
    if not times or tasks.stat().st_mtime >= max(times):
        return
    emit({"decision": "block", "reason": (
        f"Before you stop: {len(changed)} changed file(s) are newer than docs/TASKS.md. "
        "If the work is verified, record the evidence there and commit it. If it is "
        "unfinished or you are waiting for the owner, update the Now section with the "
        "next step. If the changes are generated files, add them to .gitignore.")})


HANDLERS = {"session-start": session_start, "guard": guard, "stop": stop}


def main(argv):
    handler = HANDLERS.get(argv[1] if len(argv) > 1 else "")
    if handler is None:
        print(__doc__, file=sys.stderr)
        return 0
    try:
        handler(read_payload())
    except Exception as error:  # a broken hook must never stop the agent
        print(f"studio hook error: {error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
