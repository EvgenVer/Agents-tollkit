"""A task whose details are the agent's to decide is done without asking the owner."""

import fixture as f

PROMPT = "Do T5."
MAX_TURNS = 100
TASKS = f.tasks_text(
    now="""
- Stage: 2, showing notes
- Active task: none
- Next step: T5
- Waiting for the owner: nothing
""",
    stage="showing notes",
    done_when="a notebook can be shown as text",
    tasks="""
- [ ] T5 A function `render(notes)` in a new module `notes/render.py` returns the notes as
  text, one numbered line per note with its title and its tags; the exact layout is up to
  you, check: unit tests
""")
RENDER_CHECK = (
    "from notes.core import Notebook\nfrom notes.render import render\nb=Notebook()\n"
    "b.add('Milk',tags=['shop'])\nb.add('Call mum')\nt=render(b.all())\n"
    "assert isinstance(t,str)\nl=[x for x in t.splitlines() if x.strip()]\n"
    "assert len(l)==2 and 'Milk' in l[0] and 'shop' in l[0] and 'Call mum' in l[1]\n"
    "assert '1' in l[0] and '2' in l[1]")


def setup(workspace, plugin):
    base = f.build(workspace, plugin, TASKS)
    (workspace.parent / "base").write_text(base)


def check(workspace, run):
    base = (workspace.parent / "base").read_text()
    return {
        "render works": f.python_ok(workspace, RENDER_CHECK),
        "project tests pass": f.tests_pass(workspace),
        "T5 ticked": f.ticked(workspace, "T5"),
        "committed": f.commits_since(workspace, base) >= 1 and f.clean_tree(workspace),
    }
