#!/usr/bin/env python3
"""Hooks shared by Claude Code and Codex for projects that follow the studio AGENTS.md.

Usage: studio_hooks.py session-start | guard [--host codex] | stop   (hook JSON on stdin)

session-start  Give the agent the `Now` section of docs/TASKS.md and reminders about the
               project state, so a new session, a compacted context or the other tool
               picks up where work stopped. In an empty folder, point to the idea skill.
guard          Deny reading secrets and commands that destroy work. Ask the owner before
               pushing, installing software globally, or touching files outside the
               project. Codex hooks cannot ask yet, so with --host codex those are denied.
stop           Before the agent stops, make sure changed work is recorded in TASKS.md and
               that documentation pages about the changed files are still true.

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
ARCHITECTURE = Path("docs") / "ARCHITECTURE.md"
MAX_CONTEXT_CHARS = 4000
MAX_TASKS_LINES = 150

SECRET_NAME = re.compile(
    r"^(\.env(\..+)?|.+\.(pem|key|p12|pfx|jks|keystore)|id_(rsa|dsa|ecdsa|ed25519)"
    r"|credentials(\.json)?|\.netrc|\.pgpass)$",
    re.IGNORECASE,
)
SAFE_SUFFIX = re.compile(r"\.(example|sample|template|dist)$", re.IGNORECASE)
SECRET_DIRS = {".ssh", ".aws", ".azure", ".gnupg"}
FILE_TOOLS = {"Read", "Edit", "Write", "MultiEdit", "NotebookEdit"}
WRITE_TOOLS = FILE_TOOLS - {"Read"}
SEARCH_TOOLS = {"Grep", "Glob"}
SHELL_TOOLS = {"Bash", "PowerShell"}
DELETE_COMMANDS = {"rm", "remove-item", "ri", "del", "erase", "rd", "rmdir"}
POWERSHELL_FLAGS = {"-force", "-path", "-literalpath", "-include", "-exclude", "-filter",
                    "-whatif", "-confirm"}
WHOLE_FOLDER_WILDCARDS = {"*", "*.*", ".*"}
# Folders of the agents themselves: readable, and writable only where they keep notes.
AGENT_DIRS = [".claude", ".codex", ".agents"]
AGENT_NOTE_DIRS = [os.path.join(".claude", "projects"), os.path.join(".claude", "plans")]
SYSTEM_INSTALLERS = {"winget", "choco", "scoop", "brew", "apt", "apt-get", "dnf", "yum",
                     "pacman", "snap", "cargo", "go", "gem", "pipx"}
# Shell commands that write files, and which argument names the destination.
COPY_COMMANDS = {"cp", "copy", "copy-item", "cpi", "mv", "move", "move-item", "mi"}
WRITE_COMMANDS = {"set-content", "sc", "add-content", "ac", "out-file", "new-item", "ni",
                  "tee", "tee-object"}
PATH_PARAMETERS = {"-path", "-literalpath", "-filepath", "-destination"}
SWITCHES = POWERSHELL_FLAGS | {"-append", "-nonewline", "-noclobber", "-passthru"}
NULL_TARGETS = {"/dev/null", "$null", "nul", "&1", "&2"}
REDIRECT = re.compile(r"(?<![0-9&>])>>?\s*(\"[^\"]+\"|'[^']+'|[^\s;|&<>]+)")
QUOTED = re.compile(r"\"[^\"]*\"|'[^']*'")

SETUP_ONLY = {".git", ".claude", ".codex", ".agents", ".vscode", ".idea"}

DENY, ASK = "deny", "ask"

NEW_FOLDER_CONTEXT = (
    "This folder holds no project yet. When the owner describes something they want to "
    "build, use the studio `idea` skill first: it sets up the project and brainstorms the "
    "idea with the owner before any technical choices."
)

SECRET_REASON = (
    "This file may contain secrets, and AGENTS.md forbids reading or printing them. "
    "Put placeholders in .env.example and ask the owner to fill in the real values. "
    "To keep the file out of git, edit .gitignore with the file editor."
)
DELETE_OUTSIDE_REASON = (
    "This deletes folders outside the project, or the whole project. Delete specific "
    "paths inside the project instead, or ask the owner."
)
DELETE_FILE_REASON = "This deletes files outside the project folder; the owner decides."
WRITE_OUTSIDE_REASON = (
    "This file is outside the project folder; changing it needs the owner's approval. "
    "Work inside the project when you can."
)
READ_OUTSIDE_REASON = (
    "This path is outside the project folder; reading it needs the owner's approval. "
    "Stay inside the project when you can."
)
PUSH_REASON = "Pushing publishes commits to a remote repository; the owner decides."
INSTALL_REASON = (
    "This installs software globally, outside the project. Install dependencies inside "
    "the project instead: Python into .venv (.venv\\Scripts\\python -m pip install ... on "
    "Windows, .venv/bin/python -m pip install ... elsewhere), JavaScript without -g. "
    "If a global tool is really needed, the owner decides."
)
CODEX_ASK_PREFIX = ("Needs the owner's approval, and Codex hooks cannot ask for it: tell "
                    "the owner and let them run it themselves. ")
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
PUSH_PATTERN = re.compile(r"\bgit\s+push\b")


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
    """Absolute paths of files with uncommitted changes, untracked files included."""
    top = git_toplevel(root)
    output = run_git(top, "status", "--porcelain", "-z", "-uall") if top else None
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


def read_text(path):
    return path.read_text(encoding="utf-8", errors="replace")


def is_inside(path, folder):
    try:
        path.relative_to(folder)
        return True
    except ValueError:
        return False


# --- session-start -------------------------------------------------------------------

def project_commands_missing(root):
    """True when the architecture is approved but AGENTS.md has no project commands."""
    architecture, agents = root / ARCHITECTURE, root / "AGENTS.md"
    if not architecture.is_file() or not agents.is_file():
        return False
    if not re.search(r"^Status:\s*approved", read_text(architecture), re.MULTILINE):
        return False
    commands = re.sub(r"<!--.*?-->", "", section(read_text(agents), "Project commands"),
                      flags=re.DOTALL)
    return not commands.strip()


def is_new_folder(folder):
    """True for a folder with nothing in it but version control and agent settings."""
    try:
        return all(entry.name in SETUP_ONLY for entry in folder.iterdir())
    except OSError:
        return False


def session_start(payload):
    cwd = Path(payload.get("cwd") or os.getcwd()).resolve()
    root = project_root(cwd)
    tasks = root / TASKS
    if not tasks.is_file():
        if is_new_folder(cwd):
            emit({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                         "additionalContext": NEW_FOLDER_CONTEXT}})
        return
    text = read_text(tasks)
    now = section(text, "Now")
    parts = ["Where work stands, from docs/TASKS.md (section Now):",
             now or "(The Now section is missing; restore it before continuing.)"]
    changes = changed_files(root)
    if changes:
        parts.append(f"There are uncommitted changes in {len(changes)} file(s); check "
                     "whether they belong to the active task before starting new work.")
    lines = len(text.splitlines())
    if lines > MAX_TASKS_LINES:
        parts.append(f"docs/TASKS.md has {lines} lines. Move finished stages to "
                     "docs/history/stage-<N>.md and leave one line each, as AGENTS.md says.")
    if project_commands_missing(root):
        parts.append("The architecture is approved but Project commands in AGENTS.md is "
                     "empty. Filling it is part of task T1 \"Project skeleton\".")
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


def native_path(value):
    """Turn a Git Bash path such as /d/project into D:/project on Windows."""
    value = str(value).strip().strip("'\"")
    if os.name == "nt" and re.match(r"^/[a-zA-Z](/|$)", value):
        value = f"{value[1].upper()}:/{value[3:]}"
    return value


def resolve_path(value, cwd):
    path = Path(native_path(value)).expanduser()
    if not path.is_absolute():
        path = Path(cwd) / path
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def guard_root(cwd):
    top = git_toplevel(cwd)
    if top:
        return top
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        return Path(os.environ["CLAUDE_PROJECT_DIR"]).resolve()
    return Path(cwd).resolve()


def scratch_dirs(payload):
    dirs = [Path(tempfile.gettempdir()).resolve()]
    if payload.get("scratchpad_dir"):
        dirs.append(Path(payload["scratchpad_dir"]).resolve())
    return dirs


def agent_dirs(writing):
    home = Path.home()
    dirs = [home / d for d in (AGENT_NOTE_DIRS if writing else AGENT_DIRS)]
    if not writing:
        dirs += [Path(os.environ[v]) for v in ("CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT")
                 if os.environ.get(v)]
    return [d.resolve() for d in dirs]


def outside_project(path, root, payload, writing):
    """The reason to ask when a file tool reaches outside the project, else None."""
    allowed = [root, *scratch_dirs(payload), *agent_dirs(writing)]
    if any(is_inside(path, folder) for folder in allowed):
        return None
    return WRITE_OUTSIDE_REASON if writing else READ_OUTSIDE_REASON


def command_segments(command):
    return [part.strip() for part in re.split(r"&&|\|\||[;|\n]", command) if part.strip()]


def command_words(segment):
    try:
        words = shlex.split(segment, posix=False)
    except ValueError:
        words = segment.split()
    return [word.strip("'\"") for word in words]


def strip_prose(segment):
    """Drop quoted text with spaces: it is prose (a commit message, an echo), not a path.
    Quotes pair from left to right, so "dir" "a prompt" keeps "dir" and drops the prompt."""
    return QUOTED.sub(lambda match: " " if re.search(r"\s", match.group()) else match.group(),
                      segment)


def secret_in_command(command):
    for segment in command_segments(command):
        words = command_words(segment)
        if (len(words) == 3 and words[0].lower() in {"cp", "copy", "copy-item"}
                and SAFE_SUFFIX.search(words[1]) and is_secret_path(words[2])):
            continue  # copying .env.example into place creates a file without reading one
        tokens = re.findall(r"[^\s'\"`;|&<>()=,]+", strip_prose(segment))
        if any(is_secret_path(token) for token in tokens):
            return True
    return False


def deletion(segment):
    """(targets, recursive) when this segment deletes files, else None."""
    words = command_words(segment)
    if words and words[0] == "sudo":
        words = words[1:]
    if not words or Path(words[0]).stem.lower() not in DELETE_COMMANDS:
        return None
    name = Path(words[0]).stem.lower()
    flags = [w for w in words[1:] if w.startswith("-") or (w.startswith("/") and len(w) == 2)]
    targets = [w for w in words[1:] if w not in flags]
    recursive = False
    for flag in (f.lower() for f in flags):
        if flag in ("/s", "--recursive") or flag.startswith("-rec"):
            recursive = True
        elif flag in POWERSHELL_FLAGS or flag.startswith("--"):
            continue
        elif name == "rm" and "r" in flag[1:]:
            recursive = True  # rm -r, -rf, -fr, -R
        elif name != "rm" and flag.startswith("-r"):
            recursive = True  # Remove-Item -r
    return targets, recursive


def deletion_risk(segment, cwd, root, payload):
    parsed = deletion(segment)
    if parsed is None:
        return None
    targets, recursive = parsed
    outside = (DENY, DELETE_OUTSIDE_REASON) if recursive else (ASK, DELETE_FILE_REASON)
    if not targets:
        return outside if recursive else None
    scratch = scratch_dirs(payload)
    for target in targets:
        if target.startswith(("~", "$", "%")):
            return outside  # where a variable points is unknown
        candidate = Path(native_path(target))
        if not candidate.is_absolute():
            candidate = Path(cwd) / candidate
        wildcard = any(ch in candidate.name for ch in "*?[")
        resolved = (candidate.parent if wildcard else candidate).resolve()
        if recursive and is_inside(root, resolved) and (
                resolved != root or not wildcard or candidate.name in WHOLE_FOLDER_WILDCARDS):
            return outside  # the project itself, or a folder that contains it
        if any(is_inside(resolved, folder) and resolved != folder for folder in scratch):
            continue
        if not is_inside(resolved, root):
            return outside
    return None


def write_targets(segment):
    """Destinations a shell segment writes to: copies, moves, file writers, redirects."""
    targets = [match.strip("'\"") for match in REDIRECT.findall(segment)]
    words = command_words(segment)
    name = Path(words[0]).stem.lower() if words else ""
    if name in COPY_COMMANDS or name in WRITE_COMMANDS:
        args, positional, named = words[1:], [], []
        index = 0
        while index < len(args):
            word, lowered = args[index], args[index].lower()
            index += 1
            if lowered in PATH_PARAMETERS and index < len(args):
                named.append(args[index])
                index += 1
            elif word.startswith("-"):
                # A PowerShell parameter such as -Value or -Encoding takes the next word.
                if name in WRITE_COMMANDS and name != "tee" and lowered not in SWITCHES:
                    index += 1
            else:
                positional.append(word)
        if named:
            targets.append(named[-1])
        elif positional:
            targets += positional if name == "tee" else (
                [positional[-1]] if name in COPY_COMMANDS else [positional[0]])
    return [t for t in targets if t.lower() not in NULL_TARGETS and not t.startswith(("$", "%"))]


def global_install(segment, venv_active):
    words = [w.lower() for w in command_words(strip_prose(segment))]
    if words and words[0] == "sudo":
        words = words[1:]
    if not words:
        return False
    tool, rest = Path(words[0]).stem, words[1:]
    options = set(rest)
    if tool in {"npm", "pnpm", "bun"}:
        return bool(options & {"install", "i", "add", "link"}) and bool(options & {"-g", "--global"})
    if tool == "yarn":
        return rest[:2] == ["global", "add"]
    if tool in SYSTEM_INSTALLERS:
        return "install" in rest
    if tool == "uv":
        return rest[:2] == ["tool", "install"] or (rest[:2] == ["pip", "install"]
                                                    and "--system" in options)
    if tool == "dotnet":
        return rest[:2] == ["tool", "install"] and bool(options & {"-g", "--global"})
    if tool == "install-module":
        return True
    uses_pip = tool in {"pip", "pip3"} or (
        (tool.startswith("python") or tool == "py") and "-m" in rest and "pip" in rest)
    if not uses_pip or "install" not in rest:
        return False
    if "--user" in options:
        return True
    in_venv = venv_active or re.search(r"(^|[\\/])\.?venv[\\/]", words[0])
    explicit_target = bool(options & {"--target", "-t", "--prefix"})
    return not (in_venv or explicit_target)


def shell_decision(command, cwd, root, payload):
    if secret_in_command(command):
        return DENY, SECRET_REASON
    venv_active = False
    for segment in command_segments(command):
        prose_free = strip_prose(segment)
        for pattern, reason in DESTRUCTIVE_PATTERNS:
            if pattern.search(prose_free):
                return DENY, reason
        risk = deletion_risk(segment, cwd, root, payload)
        if risk:
            return risk
        for target in write_targets(segment):
            reason = outside_project(resolve_path(target, cwd), root, payload, True)
            if reason:
                return ASK, reason
        if PUSH_PATTERN.search(prose_free):
            return ASK, PUSH_REASON
        if global_install(segment, venv_active):
            return ASK, INSTALL_REASON
        venv_active = venv_active or "activate" in prose_free.lower()
    return None


def guard_decision(payload):
    """(decision, reason) for this tool call, or None to let it through."""
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    cwd = payload.get("cwd") or os.getcwd()

    if tool in FILE_TOOLS:
        value = tool_input.get("file_path") or tool_input.get("notebook_path")
        if not value:
            return None
        path = resolve_path(value, cwd)
        if is_secret_path(value) and not (tool == "Write" and not path.exists()):
            return DENY, SECRET_REASON  # creating a new file reveals nothing
        reason = outside_project(path, guard_root(cwd), payload, tool in WRITE_TOOLS)
        return (ASK, reason) if reason else None
    if tool in SEARCH_TOOLS:
        value = tool_input.get("path")
        pattern = tool_input.get("glob") if tool == "Grep" else tool_input.get("pattern")
        if is_secret_path(value) or is_secret_path(pattern):
            return DENY, SECRET_REASON
        base = value
        if not base and tool == "Glob" and pattern and Path(native_path(pattern)).is_absolute():
            base = re.split(r"[*?\[{]", native_path(pattern))[0] or None
        if not base:
            return None
        reason = outside_project(resolve_path(base, cwd), guard_root(cwd), payload, False)
        return (ASK, reason) if reason else None

    command = tool_input.get("command")
    if isinstance(command, list):
        command = " ".join(str(part) for part in command)
    if not isinstance(command, str):
        return None
    if tool == "apply_patch":
        files = re.findall(r"^\*\*\* (Add File|Update File|Delete File|Move to): (.+)$",
                           command, re.MULTILINE)
        if any(kind in ("Update File", "Delete File") and is_secret_path(f) for kind, f in files):
            return DENY, SECRET_REASON
        root = guard_root(cwd)
        for _, value in files:
            reason = outside_project(resolve_path(value.strip(), cwd), root, payload, True)
            if reason:
                return ASK, reason
        return None
    if tool not in SHELL_TOOLS:
        return None
    return shell_decision(command, cwd, guard_root(cwd), payload)


def guard(payload, host="claude"):
    result = guard_decision(payload)
    if not result:
        return
    decision, reason = result
    if decision == ASK and host == "codex":
        decision, reason = DENY, CODEX_ASK_PREFIX + reason
    emit({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                 "permissionDecision": decision,
                                 "permissionDecisionReason": reason}})


# --- stop ----------------------------------------------------------------------------

def stale_pages(root, changed):
    """Documentation pages that mention changed files and are older than them."""
    docs = (root / "docs").resolve()
    if not docs.is_dir():
        return []
    sources = {}
    for path in changed:
        path = path.resolve()
        if path.is_file() and not is_inside(path, docs) and is_inside(path, root.resolve()):
            sources[path.relative_to(root.resolve()).as_posix()] = path.stat().st_mtime
    if not sources:
        return []
    skip = [(root / TASKS).resolve(), docs / "history"]
    pages = []
    for page in sorted(docs.rglob("*.md")):
        page = page.resolve()
        if any(page == s or is_inside(page, s) for s in skip):
            continue
        text, edited = read_text(page), page.stat().st_mtime
        hits = [rel for rel, changed_at in sources.items() if changed_at > edited and rel in text]
        if hits:
            pages.append(f"{page.relative_to(root.resolve()).as_posix()} ({', '.join(hits[:3])})")
    return pages


def stop(payload):
    if payload.get("stop_hook_active"):
        return
    root = project_root(payload.get("cwd"))
    tasks = root / TASKS
    if not tasks.is_file():
        return
    changed = [p for p in changed_files(root) if p.resolve() != tasks.resolve()]
    reasons = []
    times = [p.stat().st_mtime for p in changed if p.exists()]
    if times and tasks.stat().st_mtime < max(times):
        reasons.append(
            f"{len(changed)} changed file(s) are newer than docs/TASKS.md. If the work is "
            "verified, record the evidence there and commit it. If it is unfinished or you "
            "are waiting for the owner, update the Now section with the next step. If the "
            "changes are generated files, add them to .gitignore.")
    pages = stale_pages(root, changed)
    if pages:
        reasons.append(
            "These documentation pages mention files you changed after the page was last "
            f"edited: {'; '.join(pages[:5])}. Check that they still describe the code, and "
            "update them if they do not.")
    if reasons:
        emit({"decision": "block", "reason": "Before you stop: " + " ".join(reasons)})


def main(argv):
    command = argv[1] if len(argv) > 1 else ""
    host = argv[3] if len(argv) > 3 and argv[2] == "--host" else "claude"
    handlers = {"session-start": session_start, "guard": lambda p: guard(p, host), "stop": stop}
    handler = handlers.get(command)
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
