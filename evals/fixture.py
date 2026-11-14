"""The small project every behaviour scenario starts from: an in-memory notebook library
set up by the plugin's own script, with approved documents and a filled task log."""

import re
import subprocess
import sys
from pathlib import Path

CORE = '''"""An in-memory notebook."""

from dataclasses import dataclass, field


@dataclass
class Note:
    title: str
    body: str = ""
    tags: list[str] = field(default_factory=list)


class Notebook:
    def __init__(self):
        self._notes = []

    def add(self, title, body="", tags=None):
        if not title.strip():
            raise ValueError("a note needs a title")
        note = Note(title.strip(), body, list(tags or []))
        self._notes.append(note)
        return note

    def all(self):
        return list(self._notes)
'''

SEARCH = '''
    def search(self, text):
        """Notes whose title or body contains the text, ignoring case."""
        wanted = text.lower()
        return [note for note in self._notes
                if wanted in note.title.lower() or wanted in note.body.lower()]
'''

TESTS = '''import unittest

from notes.core import Notebook


class NotebookTest(unittest.TestCase):
    def test_add_keeps_the_note(self):
        book = Notebook()
        note = book.add(" Milk ", "two litres", ["shop"])
        self.assertEqual(note.title, "Milk")
        self.assertEqual(book.all(), [note])

    def test_a_blank_title_is_refused(self):
        with self.assertRaises(ValueError):
            Notebook().add("   ")


if __name__ == "__main__":
    unittest.main()
'''

SEARCH_TESTS = '''

class SearchTest(unittest.TestCase):
    def test_search_ignores_case_and_reads_the_body(self):
        book = Notebook()
        milk = book.add("Milk", "two litres")
        book.add("Bread")
        self.assertEqual(book.search("LITRES"), [milk])
'''

PRODUCT = """# Product: notes

Status: approved 2026-11-01

A small Python library that keeps a person's notes while their program runs: add a note
with a title, a body and tags, then find notes again by text or by tag.

## It works when

- a note added with a title can be listed again;
- a search for a word finds the notes that contain it, in the title or the body;
- notes can be listed by tag.

## Constraints

- Python standard library only.
"""

ARCHITECTURE = """# Architecture: notes

Status: approved 2026-11-01

One package, `notes`, with one module, `notes/core.py`: the `Note` record and the
`Notebook` class that holds notes in a list.

| Part | Choice | Why |
|---|---|---|
| Language | Python 3, standard library only | approved by the owner |
| Tests | `unittest` | no dependency |
| Data | in memory only | storage between runs is not chosen yet: the owner decides whether notes are kept at all and where (a file, SQLite or a service) |
"""

COMMANDS = """- Test: `python -m unittest discover -s tests -q`
- Lint and format: none in this project.
- Docs: the site is not built in this project; edit the Markdown pages only.
"""

TASKS_HEAD = """# Tasks: notes

## Now

{now}

## Stage 2: {stage}

Done when: {done_when}

{tasks}

## Technical debt

- nothing recorded

## Later

- Export notes to Markdown. Never built without the owner's agreement.

## Finished stages

- Stage 1, done 2026-11-05: the `Note` record and `Notebook.add` and `all`, 2 tests pass.
"""


def git(root, *args):
    done = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return done.stdout.strip()


def write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def tasks_text(now, stage, done_when, tasks):
    return TASKS_HEAD.format(now=now.strip(), stage=stage, done_when=done_when,
                             tasks=tasks.strip())


def build(root, plugin, tasks, with_search=False):
    """Create the project in `root` with the plugin's setup script and commit it."""
    script = Path(plugin) / "skills" / "idea" / "scripts" / "setup_project.py"
    subprocess.run([sys.executable, str(script), "--root", str(root), "--language", "en",
                    "--name", "notes"], capture_output=True, check=True)
    git(root, "config", "user.email", "eval@example.com")
    git(root, "config", "user.name", "Eval")
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    agents = re.sub(r"(## Project commands\n\n).*", r"\1" + COMMANDS, agents, flags=re.DOTALL)
    write(root, "AGENTS.md", agents)
    write(root, "notes/__init__.py", "")
    write(root, "notes/core.py", CORE + (SEARCH if with_search else ""))
    write(root, "tests/__init__.py", "")
    write(root, "tests/test_core.py",
          TESTS.replace("\n\nif __name__", (SEARCH_TESTS if with_search else "") +
                        "\n\nif __name__"))
    write(root, "docs/PRODUCT.md", PRODUCT)
    write(root, "docs/ARCHITECTURE.md", ARCHITECTURE)
    write(root, "docs/TASKS.md", tasks)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "Stage 1: notebook with add and all")
    return git(root, "rev-parse", "HEAD")


def python_ok(root, code):
    """True when the code runs without error inside the project."""
    done = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True,
                          text=True, timeout=60)
    return done.returncode == 0


def tests_pass(root):
    done = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
                          cwd=root, capture_output=True, text=True, timeout=120)
    return done.returncode == 0


def clean_tree(root):
    return git(root, "status", "--porcelain") == ""


def commits_since(root, base):
    return int(git(root, "rev-list", "--count", f"{base}..HEAD") or 0)


def tasks(root):
    return (root / "docs" / "TASKS.md").read_text(encoding="utf-8", errors="replace")


def records(root):
    """The task log with the finished stages: a closed stage moves to docs/history/."""
    history = sorted((root / "docs" / "history").glob("*.md"))
    return tasks(root) + "".join(path.read_text(encoding="utf-8", errors="replace")
                                 for path in history)


def ticked(root, task):
    return bool(re.search(rf"^\s*[-*] \[[xX]\]\s*\**{task}\b", records(root), re.MULTILINE))


def now_section(root):
    found = re.search(r"## Now\n(.*?)(?=\n## )", tasks(root), re.DOTALL)
    return found.group(1) if found else ""


def waiting(root):
    """The text after 'Waiting for the owner:' in Now, lower-cased."""
    found = re.search(r"Waiting for the owner[^:\n]*:\s*(.*?)(?=\n- |\Z)", now_section(root),
                      re.DOTALL | re.IGNORECASE)
    return found.group(1).strip().lower() if found else ""


def nothing_waits(root):
    return waiting(root) in ("", "nothing", "nothing.", "none", "-")
