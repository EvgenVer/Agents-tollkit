"""'Continue' takes the open tasks of the stage, proves them, records them and commits."""

import fixture as f

PROMPT = "Continue"
MAX_TURNS = 120
TASKS = f.tasks_text(
    now="""
- Stage: 2, finding notes
- Active task: T2
- Next step: add `Notebook.search` with its tests
- Waiting for the owner: nothing
""",
    stage="finding notes",
    done_when="search and tags work from Python and every test passes",
    tasks="""
- [ ] T2 `Notebook.search(text)` returns the notes whose title or body contains the text,
  ignoring case, check: unit tests for title, body and case
- [ ] T3 `Notebook.by_tag(tag)` returns the notes with that tag, ignoring case, and
  `Notebook.tags()` returns every tag once, lower-cased and sorted, check: unit tests
""")
SEARCH_CHECK = (
    "from notes.core import Notebook\nb=Notebook()\nm=b.add('Milk','Two LITRES')\n"
    "b.add('Bread')\nassert b.search('litres')==[m] and b.search('MILK')==[m]\n"
    "assert b.search('zzz')==[]")
TAGS_CHECK = (
    "from notes.core import Notebook\nb=Notebook()\nm=b.add('Milk',tags=['Shop'])\n"
    "b.add('Call',tags=['home','shop'])\nassert b.by_tag('SHOP')[0]==m\n"
    "assert len(b.by_tag('shop'))==2\nassert list(b.tags())==['home','shop']")


def setup(workspace, plugin):
    base = f.build(workspace, plugin, TASKS)
    (workspace.parent / "base").write_text(base)


def check(workspace, run):
    base = (workspace.parent / "base").read_text()
    return {
        "search works": f.python_ok(workspace, SEARCH_CHECK),
        "tags work": f.python_ok(workspace, TAGS_CHECK),
        "project tests pass": f.tests_pass(workspace),
        "T2 and T3 ticked": f.ticked(workspace, "T2") and f.ticked(workspace, "T3"),
        "Now moved past T2": "Active task: T2" not in f.now_section(workspace),
        "committed": f.commits_since(workspace, base) >= 1 and f.clean_tree(workspace),
    }
