#!/usr/bin/env python3
"""Hooks shared by Claude Code, Codex and Antigravity for projects that follow the studio
AGENTS.md.

Usage: studio_hooks.py session-start | guard | stop [--host codex|antigravity]
       (hook JSON on stdin; the host defaults to Claude Code)

session-start  Give the agent the `Now` section of docs/TASKS.md and reminders about the
               project state, so a new session, a compacted context or the other tool
               picks up where work stopped. In an empty folder, point to the idea skill.
guard          Deny reading secrets and commands that destroy work. Ask the owner before
               pushing, installing software globally, or touching files outside the
               project. Codex and Antigravity hooks cannot ask, so there those are denied.
stop           Before the agent stops, make sure work changed or committed in this session
               is recorded in TASKS.md and that documentation pages about the changed,
               deleted or renamed files are still true.

A failure inside a hook never blocks the agent: errors go to stderr and exit 0.
"""

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
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
# Options git takes before its subcommand (git -C dir, -c key=value, --no-pager, ...).
ARGUMENT = r"(?:\"[^\"]*\"|'[^']*'|[^\s;|&]+)"
GIT_OPTION = (rf"(?:-[Cc]\s+{ARGUMENT}|--(?:git-dir|work-tree|namespace)\s+{ARGUMENT}"
              rf"|-{{1,2}}[A-Za-z][\w-]*(?:={ARGUMENT}?)?)")
GIT_GLOBAL_OPTIONS = re.compile(rf"(?<![\w./\\-])git(?:\.exe)?(?:\s+{GIT_OPTION})+(?=\s)")
# Commands that change the folder the rest of a command line runs in.
CD_COMMANDS = {"cd", "chdir", "sl", "set-location", "pushd", "push-location"}
POP_COMMANDS = {"popd", "pop-location"}

SETUP_ONLY = {".git", ".claude", ".codex", ".agents", ".vscode", ".idea"}
# Per session: the commit it started from, so stop also sees work committed since then,
# and the reminders stop already gave, so it does not repeat them.
SESSIONS = Path(tempfile.gettempdir()) / "studio-hooks" / "sessions"
SESSION_DAYS = 30
# Pages that may name deleted files: the work log, finished stages and past decisions.
HISTORY_PAGES = [TASKS, Path("docs") / "history", Path("docs") / "decisions"]

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
HOST_NAMES = {"codex": "Codex", "antigravity": "Antigravity"}
ASK_PREFIX = ("Needs the owner's approval, and {} hooks cannot ask for it: tell the owner "
              "and let them run it themselves. ")
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


def uncommitted(top):
    """(changed, removed) absolute paths of uncommitted changes, untracked files included
    except those in hidden folders such as .artifacts/ or .cache/; removed holds deleted
    files and the old paths of renamed ones."""
    output = run_git(top, "status", "--porcelain", "-z", "-uall")
    entries = output.split("\0") if output else []
    changed, removed = [], []
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue
        if entry[0] in "RC":
            if entry[0] == "R" and index < len(entries):
                removed.append(top / entries[index])
            index += 1  # a rename or copy is followed by its original path
        hidden = any(part.startswith(".") for part in Path(entry[3:]).parts[:-1])
        if entry[:2] == "??" and hidden:
            continue  # generated output, caches and tool state, not the agent's work
        (removed if "D" in entry[:2] else changed).append(top / entry[3:])
    return changed, removed


def committed_since(top, commit):
    """(changed, removed) paths in commits made after `commit`, in the same shape."""
    output = run_git(top, "diff", "--name-status", "-z", "--no-renames", commit, "HEAD")
    fields = output.split("\0") if output else []
    changed, removed = [], []
    for status, path in zip(fields[::2], fields[1::2]):
        (removed if status.startswith("D") else changed).append(top / path)
    return changed, removed


def changed_files(root):
    """Absolute paths of files with uncommitted changes, untracked files included."""
    top = git_toplevel(root)
    return [path for paths in uncommitted(top) for path in paths] if top else []


def session_id(payload):
    return str(payload.get("session_id") or payload.get("conversationId") or "")


def session_file(session, top):
    digest = hashlib.sha1(f"{session}|{top}".encode("utf-8")).hexdigest()[:20]
    return SESSIONS / f"{digest}.json"


def load_session(session, top):
    try:
        notes = json.loads(session_file(session, top).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return notes if isinstance(notes, dict) else {}


def save_session(session, top, notes):
    try:
        SESSIONS.mkdir(parents=True, exist_ok=True)
        for old in SESSIONS.glob("*.json"):
            if old.stat().st_mtime < time.time() - SESSION_DAYS * 86400:
                old.unlink()
        session_file(session, top).write_text(json.dumps(notes), encoding="utf-8")
    except OSError:
        pass  # without notes, stop checks uncommitted work only and may repeat itself


def remember_start(payload):
    """Note the commit this session starts from; a resumed session keeps its first one."""
    session, top = session_id(payload), git_toplevel(payload.get("cwd") or os.getcwd())
    head = run_git(top, "rev-parse", "--verify", "HEAD") if session and top else None
    if not head:
        return
    notes = load_session(session, top)
    if "head" not in notes:
        save_session(session, top, {**notes, "head": head.strip()})


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


def session_context(cwd):
    """What a new session should know before it starts, or None."""
    root = project_root(cwd)
    tasks = root / TASKS
    if not tasks.is_file():
        return NEW_FOLDER_CONTEXT if is_new_folder(cwd) else None
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
    return "\n".join(parts)[:MAX_CONTEXT_CHARS]


def session_start(payload, host="claude"):
    remember_start(payload)
    context = session_context(Path(payload.get("cwd") or os.getcwd()).resolve())
    if host == "antigravity":
        emit({"injectSteps": [{"systemMessage": {"systemMessage": context}}]} if context else {})
    elif context:
        emit({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                     "additionalContext": context}})


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
    """Folders besides the project where the agent may write and delete files."""
    dirs = [Path(tempfile.gettempdir()).resolve()]
    for folder in [payload.get("scratchpad_dir"), *payload.get("workspace_dirs", [])]:
        if folder:
            dirs.append(Path(folder).resolve())
    return dirs


def agent_dirs(writing, payload):
    home = Path.home()
    dirs = [home / d for d in (AGENT_NOTE_DIRS if writing else AGENT_DIRS)]
    if not writing:
        dirs += [Path(os.environ[v]) for v in ("CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT")
                 if os.environ.get(v)]
        dirs += [Path(d) for d in payload.get("readable_dirs", [])]
    return [d.resolve() for d in dirs]


def outside_project(path, root, payload, writing):
    """The reason to ask when a file tool reaches outside the project, else None."""
    allowed = [root, *scratch_dirs(payload), *agent_dirs(writing, payload)]
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


def located_segments(command, cwd):
    """(segment, folder it runs in) for each segment, following cd, Set-Location, pushd
    and popd to literal paths. A folder held in a variable is not followed."""
    located, stack = [], []
    for segment in command_segments(command):
        located.append((segment, cwd))
        words = command_words(segment)
        name = words[0].lstrip("(").lower() if words else ""
        if name in POP_COMMANDS:
            cwd = stack.pop() if stack else cwd
        elif name in CD_COMMANDS:
            targets = [w for w in words[1:]
                       if not w.startswith("-") and not re.fullmatch(r"/[a-zA-Z]", w)]
            if name in {"pushd", "push-location"}:
                stack.append(cwd)
            if targets and not targets[0].startswith(("$", "%")):
                cwd = str(resolve_path(targets[0], cwd))
    return located


def strip_prose(segment):
    """Drop quoted text with spaces: it is prose (a commit message, an echo), not a path.
    Quotes pair from left to right, so "dir" "a prompt" keeps "dir" and drops the prompt."""
    return QUOTED.sub(lambda match: " " if re.search(r"\s", match.group()) else match.group(),
                      segment)


def exists(path):
    try:
        return path.exists()
    except (OSError, ValueError):
        return False


def secret_in_segment(segment, cwd):
    words = command_words(segment)
    if (len(words) == 3 and words[0].lower() in {"cp", "copy", "copy-item"}
            and SAFE_SUFFIX.search(words[1]) and is_secret_path(words[2])):
        return False  # copying .env.example into place creates a file without reading one
    tokens = re.findall(r"[^\s'\"`;|&<>()=,]+", strip_prose(segment))
    if any(is_secret_path(token) for token in tokens):
        return True
    # Quoted text with spaces is a path, not prose, when it names a secret file that exists.
    return any(re.search(r"\s", value) and is_secret_path(value)
               and exists(resolve_path(value, cwd))
               for value in (quoted[1:-1] for quoted in QUOTED.findall(segment)))


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


def segment_decision(segment, cwd, root, payload, venv_active):
    prose_free = strip_prose(GIT_GLOBAL_OPTIONS.sub("git", segment))
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
    return None


def shell_decision(command, cwd, root, payload):
    located = located_segments(command, cwd)
    if any(secret_in_segment(segment, where) for segment, where in located):
        return DENY, SECRET_REASON
    results, venv_active = [], False
    for segment, where in located:
        results.append(segment_decision(segment, where, root, payload, venv_active))
        venv_active = venv_active or "activate" in strip_prose(segment).lower()
    return strongest(results)


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


def strongest(results):
    """The deny among these (decision, reason) results, else the first ask, else None."""
    found = [result for result in results if result]
    return next((result for result in found if result[0] == DENY), found[0] if found else None)


def guard(payload, host="claude"):
    if host == "antigravity":
        result = strongest(guard_decision(call) for call in antigravity_calls(payload))
    else:
        result = guard_decision(payload)
    if result and result[0] == ASK and host in HOST_NAMES:
        result = DENY, ASK_PREFIX.format(HOST_NAMES[host]) + result[1]
    if host == "antigravity":
        emit({"decision": result[0], "reason": result[1]} if result else {"decision": "allow"})
    elif result:
        emit({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                     "permissionDecision": result[0],
                                     "permissionDecisionReason": result[1]}})


# --- stop ----------------------------------------------------------------------------

def project_files(root, paths, kept):
    """{path relative to the project: path} for files outside docs/ that exist (kept) or
    no longer exist (not kept)."""
    root = root.resolve()
    docs = root / "docs"
    found = {}
    for path in paths:
        path = path.resolve()
        if path.is_file() == kept and is_inside(path, root) and not is_inside(path, docs):
            found[path.relative_to(root).as_posix()] = path
    return found


def doc_pages(root, skip):
    docs = (root / "docs").resolve()
    skip = [(root / s).resolve() for s in skip]
    pages = sorted(docs.rglob("*.md")) if docs.is_dir() else []
    return [page.resolve() for page in pages
            if not any(page.resolve() == s or is_inside(page.resolve(), s) for s in skip)]


def page_hits(root, pages, mentioned):
    """(page, files) for each page that mentions one of the files `mentioned` picks."""
    found = []
    for page in pages:
        hits = mentioned(page, read_text(page))
        if hits:
            found.append((page.relative_to(root.resolve()).as_posix(), hits))
    return found


def untold(hits, told):
    """'page (file, ...)' for the page and file pairs not mentioned yet; notes them."""
    found = []
    for page, files in hits:
        new = [name for name in files if f"{page}|{name}" not in told]
        told.update(f"{page}|{name}" for name in new)
        if new:
            found.append(f"{page} ({', '.join(new[:3])})")
    return found


def stale_pages(root, changed):
    """Documentation pages that mention changed files and are older than them."""
    sources = {rel: path.stat().st_mtime
               for rel, path in project_files(root, changed, True).items()}
    if not sources:
        return []
    return page_hits(root, doc_pages(root, [TASKS, Path("docs") / "history"]),
                     lambda page, text: [rel for rel, changed_at in sources.items()
                                         if changed_at > page.stat().st_mtime and rel in text])


def pages_about_removed(root, removed):
    """Documentation pages that still mention deleted or renamed files."""
    gone = project_files(root, removed, False)
    if not gone:
        return []
    return page_hits(root, doc_pages(root, HISTORY_PAGES),
                     lambda page, text: [rel for rel in gone if rel in text])


def stop_reason(cwd, session=""):
    """Why the agent should not stop yet, or None. With a session id each reminder is
    given once: a later stop mentions only what changed since."""
    root = project_root(cwd)
    tasks = root / TASKS
    top = git_toplevel(root)
    if not tasks.is_file() or not top:
        return None
    tasks = tasks.resolve()
    notes = load_session(session, top) if session else {}
    told = set(notes.get("told", []))
    changed, removed = uncommitted(top)
    since = notes.get("head")
    committed, committed_removed = committed_since(top, since) if since else ([], [])
    reasons = []
    pending = [p for p in changed + removed if p.resolve() != tasks]
    newest = max((p.stat().st_mtime for p in pending if p.exists()), default=0)
    head = (run_git(top, "rev-parse", "HEAD") or "").strip()
    if newest > tasks.stat().st_mtime:
        if newest > notes.get("tasks_told", 0):
            notes["tasks_told"] = newest
            reasons.append(
                f"{len(pending)} changed file(s) are newer than docs/TASKS.md. If the work "
                "is verified, record the evidence there and commit it. If it is unfinished "
                "or you are waiting for the owner, update the Now section with the next "
                "step. If the changes are generated files, add them to .gitignore.")
    elif (committed or committed_removed) and tasks not in {
            p.resolve() for p in committed + changed}:
        if notes.get("commits_told") != head:
            notes["commits_told"] = head
            reasons.append(
                f"{len(committed + committed_removed)} file(s) were committed in this "
                "session, but docs/TASKS.md was not updated. Record the evidence of the "
                "finished work there, or update the Now section with the next step, and "
                "commit it.")
    pages = untold(stale_pages(root, changed + committed), told)
    if pages:
        reasons.append(
            "These documentation pages mention files you changed after the page was last "
            f"edited: {'; '.join(pages[:5])}. Check that they still describe the code, and "
            "update them if they do not.")
    gone = untold(pages_about_removed(root, removed + committed_removed), told)
    if gone:
        reasons.append(
            "These documentation pages mention files that were deleted or renamed: "
            f"{'; '.join(gone[:5])}. Point them to the current files, or remove what no "
            "longer exists.")
    if session and reasons:
        save_session(session, top, {**notes, "told": sorted(told)})
    return "Before you stop: " + " ".join(reasons) if reasons else None


def is_subagent(payload):
    """True when a Codex subagent stops. Codex runs Stop in subagent threads too; their
    transcript starts with a session_meta record that names a subagent as the source.
    Claude Code runs Stop for the main agent only."""
    if payload.get("agent_id"):
        return True
    try:
        with open(payload.get("transcript_path") or "", encoding="utf-8") as transcript:
            first = json.loads(transcript.readline() or "{}")
    except (OSError, ValueError):
        return False
    meta = first.get("payload") if isinstance(first, dict) else None
    if first.get("type") != "session_meta" or not isinstance(meta, dict):
        return False
    source = meta.get("source")
    return meta.get("thread_source") == "subagent" or (
        isinstance(source, dict) and "subagent" in source)


def stop(payload, host="claude"):
    if host == "antigravity":
        antigravity_stop(payload)
        return
    if payload.get("stop_hook_active") or is_subagent(payload):
        return  # the main agent keeps the records; a subagent only does its brief
    reason = stop_reason(payload.get("cwd"), session_id(payload))
    if reason:
        emit({"decision": "block", "reason": reason})


# --- Antigravity ---------------------------------------------------------------------
# Antigravity sends camelCase payloads, and its tool names differ between the app
# (read_file, write_file, edit_file) and the IDE (view_file, list_dir, grep_search,
# write_to_file, replace_file_content, ...). Each call is translated into the Claude Code
# calls that guard_decision checks; tools without paths or commands pass.

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
# Antigravity's own folders: settings, plugins, skills and conversation artifacts.
GEMINI_DIRS = [os.path.join(".gemini", d)
               for d in ("config", "antigravity", "antigravity-ide", "antigravity-cli")]
FILE_ARGS = ("AbsolutePath", "Path", "TargetFile", "FilePath", "File")
FOLDER_ARGS = ("DirectoryPath", "SearchPath", "SearchDirectory", "Directory",
               "TargetDirectories")
PATTERN_ARGS = ("Pattern", "Includes")
NEW_FILE_TOOLS = {"write_file", "write_to_file", "create_file"}
WRITING_TOOL = re.compile(r"write|edit|replace|create|delete|move|patch", re.IGNORECASE)
STOP_STATE = Path(tempfile.gettempdir()) / "studio-hooks" / "antigravity-stop.json"
# What Antigravity reads as "carry on" when a hook fails: {} would deny a tool call.
NEUTRAL = {"session-start": {}, "guard": {"decision": "allow"}, "stop": {"decision": "stop"}}


def strings(value):
    """A string argument, or the strings in a list argument."""
    items = value if isinstance(value, list) else [value]
    return [item for item in items if isinstance(item, str) and item.strip()]


def antigravity_cwd(payload):
    workspaces = strings(payload.get("workspacePaths"))
    return workspaces[0] if workspaces else payload.get("artifactDirectoryPath")


def antigravity_calls(payload):
    """The Claude Code tool calls that do what this Antigravity tool call does."""
    call = payload.get("toolCall") or {}
    name, args = str(call.get("name", "")), call.get("args") or {}
    context = {"cwd": args.get("Cwd") or antigravity_cwd(payload),
               "scratchpad_dir": payload.get("artifactDirectoryPath"),
               "workspace_dirs": strings(payload.get("workspacePaths")),
               "readable_dirs": [PLUGIN_ROOT, *(Path.home() / d for d in GEMINI_DIRS)]}

    def claude(tool, **tool_input):
        return {**context, "tool_name": tool, "tool_input": tool_input}

    if name == "run_command":
        return [claude("PowerShell", command=str(args.get("CommandLine", "")))]
    calls = [claude("apply_patch", command=value) for value in args.values()
             if isinstance(value, str) and "*** Begin Patch" in value]
    writing = bool(WRITING_TOOL.search(name))
    file_tool = ("Write" if name in NEW_FILE_TOOLS else "Edit") if writing else "Read"
    folders = [folder for key in FOLDER_ARGS for folder in strings(args.get(key))]
    for key in FILE_ARGS:
        calls += [claude(file_tool, file_path=path) for path in strings(args.get(key))]
    if writing:
        calls += [claude("Edit", file_path=folder) for folder in folders]
    else:
        calls += [claude("Grep", path=folder) for folder in folders]
        calls += [claude("Glob", pattern=pattern)
                  for key in PATTERN_ARGS for pattern in strings(args.get(key))]
    return calls


def antigravity_stop(payload):
    """Antigravity has no stop_hook_active: remember the run that was sent back to work,
    and let the run right after it stop."""
    conversation = str(payload.get("conversationId", ""))
    run = int(payload.get("executionNum") or 0)
    try:
        sent_back = json.loads(STOP_STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        sent_back = {}
    reason = None
    if (payload.get("terminationReason", "NO_TOOL_CALL") == "NO_TOOL_CALL"
            and sent_back.get(conversation) != run - 1):
        reason = stop_reason(payload.get("cwd"), conversation)
    if not reason:
        emit({"decision": "stop"})
        return
    sent_back = dict(list(sent_back.items())[-50:])
    sent_back[conversation] = run
    STOP_STATE.parent.mkdir(parents=True, exist_ok=True)
    STOP_STATE.write_text(json.dumps(sent_back), encoding="utf-8")
    emit({"decision": "continue", "reason": reason})


def main(argv):
    command = argv[1] if len(argv) > 1 else ""
    host = argv[3] if len(argv) > 3 and argv[2] == "--host" else "claude"
    handlers = {"session-start": session_start, "guard": guard, "stop": stop}
    handler = handlers.get(command)
    if handler is None:
        print(__doc__, file=sys.stderr)
        return 0
    try:
        payload = read_payload()
        if host == "antigravity":
            payload = {**payload, "cwd": antigravity_cwd(payload)}
        handler(payload, host)
    except Exception as error:  # a broken hook must never stop the agent
        print(f"studio hook error: {error}", file=sys.stderr)
        if host == "antigravity":
            emit(NEUTRAL[command])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
