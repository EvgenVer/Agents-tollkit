"""A new session picks up a half-done task and keeps the record of the finished one."""

import fixture as f

PROMPT = "Continue"
MAX_TURNS = 120
EVIDENCE = "done 2026-11-10: `python -m unittest discover -s tests -q`, 3 tests pass"
TASKS = f.tasks_text(
    now="""
- Stage: 2, finding notes
- Active task: T3, half done: `by_tag` is written but not committed and has no tests
- Next step: add `Notebook.tags()`, test both, commit
- Waiting for the owner: nothing
""",
    stage="finding notes",
    done_when="search and tags work from Python and every test passes",
    tasks=f"""
- [x] T2 `Notebook.search(text)` returns the notes whose title or body contains the text,
  ignoring case, {EVIDENCE}
- [ ] T3 `Notebook.by_tag(tag)` returns the notes with that tag, ignoring case, and
  `Notebook.tags()` returns every tag once, lower-cased and sorted, check: unit tests
""")
HALF_DONE = '''
    def by_tag(self, tag):
        return [note for note in self._notes if tag in note.tags]
'''
TAGS_CHECK = (
    "from notes.core import Notebook\nb=Notebook()\nm=b.add('Milk',tags=['Shop'])\n"
    "b.add('Call',tags=['home','shop'])\nassert b.by_tag('SHOP')[0]==m\n"
    "assert len(b.by_tag('shop'))==2\nassert list(b.tags())==['home','shop']")
SEARCH_CHECK = (
    "from notes.core import Notebook\nb=Notebook()\nm=b.add('Milk','two litres')\n"
    "assert b.search('LITRES')==[m]")


def setup(workspace, plugin):
    base = f.build(workspace, plugin, TASKS, with_search=True)
    core = workspace / "notes" / "core.py"
    core.write_text(core.read_text(encoding="utf-8") + HALF_DONE, encoding="utf-8",
                    newline="\n")
    (workspace.parent / "base").write_text(base)


def check(workspace, run):
    base = (workspace.parent / "base").read_text()
    return {
        "tags work": f.python_ok(workspace, TAGS_CHECK),
        "search still works": f.python_ok(workspace, SEARCH_CHECK),
        "project tests pass": f.tests_pass(workspace),
        "T2 evidence kept": " ".join(EVIDENCE.split())
        in " ".join(f.records(workspace).split()),
        "T3 ticked": f.ticked(workspace, "T3"),
        "committed": f.commits_since(workspace, base) >= 1 and f.clean_tree(workspace),
    }
