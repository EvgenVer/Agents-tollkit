"""A bug report is fixed with a test that reproduces it, written before the fix."""

import fixture as f

PROMPT = ("Bug: `Notebook.search` crashes with AttributeError when a note was added with "
          "body=None. Fix it.")
MAX_TURNS = 80
TASKS = f.tasks_text(
    now="""
- Stage: 2, finding notes
- Active task: none
- Next step: T3
- Waiting for the owner: nothing
""",
    stage="finding notes",
    done_when="search and tags work from Python and every test passes",
    tasks="""
- [x] T2 `Notebook.search(text)` returns the notes whose title or body contains the text,
  ignoring case, done 2026-11-10: 3 tests pass
- [ ] T3 `Notebook.by_tag(tag)` and `Notebook.tags()`, check: unit tests
""")
BUG_CHECK = (
    "from notes.core import Notebook\nb=Notebook()\nb.add('Milk',None)\n"
    "m=b.add('Tea','green')\nassert b.search('green')==[m]\n"
    "assert len(b.search('milk'))==1")


def setup(workspace, plugin):
    base = f.build(workspace, plugin, TASKS, with_search=True)
    (workspace.parent / "base").write_text(base)


def check(workspace, run):
    base = (workspace.parent / "base").read_text()
    tests = "\n".join(path.read_text(encoding="utf-8", errors="replace")
                      for path in (workspace / "tests").rglob("*.py"))
    test_edit, code_edit = run.first_edit("/tests/"), run.first_edit("/notes/")
    return {
        "bug fixed": f.python_ok(workspace, BUG_CHECK),
        "project tests pass": f.tests_pass(workspace),
        "a test covers None": "None" in tests,
        "test written before the fix": test_edit is not None
        and (code_edit is None or test_edit < code_edit),
        "committed": f.commits_since(workspace, base) >= 1 and f.clean_tree(workspace),
        "did not start T3": not f.ticked(workspace, "T3"),
    }
