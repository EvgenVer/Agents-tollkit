#!/usr/bin/env python3
"""Set up a project for the studio workflow. Never overwrites an existing file.

Usage: setup_project.py [--root DIR] [--language CODE] [--name NAME]

Creates AGENTS.md, CLAUDE.md, .gitignore, .claude/settings.json, .codex/config.toml and
the documentation site skeleton (zensical.toml, requirements-docs.txt, docs/), creates a
git repository if there is none, and commits the files it created. An existing
.gitignore only gets the missing lines appended. Prints one line per file. Inside the
Codex sandbox it leaves git to the agent, which must run it outside the sandbox.
"""

import argparse
import getpass
import os
import re
import subprocess
import sys
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "project"

# template file -> path in the project
FILES = {
    "AGENTS.md": "AGENTS.md",
    "CLAUDE.md": "CLAUDE.md",
    "gitignore": ".gitignore",
    "claude-settings.json": ".claude/settings.json",
    "codex-config.toml": ".codex/config.toml",
    "zensical.toml": "zensical.toml",
    "requirements-docs.txt": "requirements-docs.txt",
    "docs/index.md": "docs/index.md",
    "docs/.terms.md": "docs/.terms.md",
}
COMMIT_MESSAGE = "chore: set up project for the studio workflow"
SANDBOX_NOTE = (
    "skipped  git: inside the Codex sandbox a new repository would belong to the sandbox "
    "user and git cannot write to it. Run `git init` (if needed), `git add -A` and "
    "`git commit` outside the sandbox, with escalated permissions."
)


def in_codex_sandbox():
    """Codex runs sandboxed commands as a separate CodexSandbox user on Windows."""
    try:
        user = getpass.getuser()
    except (KeyError, OSError):
        user = ""
    return bool(os.environ.get("CODEX_SANDBOX")) or user.lower().startswith("codexsandbox")


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def merge_gitignore(path, template):
    """Append the template rules an existing .gitignore lacks; return True if it changed."""
    text = path.read_text(encoding="utf-8", errors="replace")
    existing = {line.strip() for line in text.splitlines()}
    missing = [line for line in template.splitlines()
               if line.strip() and not line.startswith("#") and line.strip() not in existing]
    if not missing:
        return False
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text + "\n# Added by studio setup\n" + "\n".join(missing) + "\n",
                    encoding="utf-8", newline="\n")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description="Set up a project for the studio workflow.")
    parser.add_argument("--root", default=".", help="project folder (default: current folder)")
    parser.add_argument("--language", default="en", help="documentation language, e.g. ru or en")
    parser.add_argument("--name", help="product name for the docs site (default: folder name)")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    language = args.language if re.fullmatch(r"[a-z]{2}(-[A-Za-z]{2,4})?", args.language) else "en"
    name = (args.name or root.name).replace("\\", "/").replace('"', "'")
    values = {"{{site_name}}": name, "{{language}}": language}

    touched = []
    for source, target in FILES.items():
        text = (TEMPLATES / source).read_text(encoding="utf-8")
        for key, value in values.items():
            text = text.replace(key, value)
        destination = root / target
        if destination.exists():
            if target == ".gitignore" and merge_gitignore(destination, text):
                print(f"updated  {target}")
                touched.append(target)
            else:
                print(f"kept     {target}")
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8", newline="\n")
        print(f"created  {target}")
        touched.append(target)

    if in_codex_sandbox():
        print(SANDBOX_NOTE)
        return 0
    if git(root, "rev-parse", "--is-inside-work-tree").returncode != 0:
        git(root, "init", "-q")
        print("created  git repository")
    if touched:
        git(root, "add", "--", *touched)
        result = git(root, "commit", "-q", "-m", COMMIT_MESSAGE, "--", *touched)
        if result.returncode == 0:
            print("committed the created and updated files")
        else:
            print(f"not committed: {(result.stderr or result.stdout).strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
