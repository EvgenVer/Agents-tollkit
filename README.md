# Agents Toolkit

`studio` is a plugin for Claude Code, Codex and Antigravity for building your own apps
with an autonomous agent when you have some technical knowledge but are not a
professional developer. The agent brainstorms the product with you, agrees the
architecture, stack and key libraries with you, builds it stage by stage with tests, and
keeps technical documentation with diagrams, so you understand not only what your
product does but how it works inside.

Toolkit v1 is preserved under the git tag `v1-legacy`.

## What is inside

| Part | Where | What it does |
|---|---|---|
| Project rules | [AGENTS.md template](plugins/studio/skills/idea/project/AGENTS.md) | Who decides what, how options are presented, tests and evidence, technical debt, local dependencies, safety |
| `idea` skill | [skills/idea](plugins/studio/skills/idea/SKILL.md) | Sets up a new project with a script, then brainstorms the idea with you into `docs/PRODUCT.md` |
| `design` skill | [skills/design](plugins/studio/skills/design/SKILL.md) | Technical interview: architecture, stack and libraries go to `docs/ARCHITECTURE.md` and `docs/decisions/`, stages to `docs/TASKS.md` |
| `docs` skill | [skills/docs](plugins/studio/skills/docs/SKILL.md) | Technical documentation site: Markdown with Mermaid diagrams, code embedded from the source, hover hints for terms, dark theme |
| Hooks | [hooks](plugins/studio/hooks/studio_hooks.py) | Restore where work stopped; block secrets and destructive commands; ask before pushing, global installs and files outside the project; check records and docs before stopping |

Each project ends up with:

```text
AGENTS.md, CLAUDE.md     rules for the agents (CLAUDE.md just imports AGENTS.md)
.claude/settings.json    plugin and secret-file rules for Claude Code
.codex/config.toml       sandbox settings for Codex
zensical.toml            documentation site settings
docs/                    PRODUCT, ARCHITECTURE, decisions/, components/, flows/, data,
                         operations, glossary, TASKS (with Now: where work stopped),
                         history/ (finished stages)
```

Documents are written in the language you use with the agent; code and rules stay in
English.

## Install once per tool

You need Git and Python 3, available as `python` (Codex on macOS and Linux uses `python3`).

Claude Code:

```bash
claude plugin marketplace add EvgenVer/Agents-tollkit
```

```bash
claude plugin install studio@agents-toolkit
```

Codex:

```bash
codex plugin marketplace add EvgenVer/Agents-tollkit
```

```bash
codex plugin add studio@agents-toolkit
```

Codex runs plugin hooks only after you trust them: start Codex, run `/hooks` and trust
the three `studio` hooks. Repeat after every plugin update.

Antigravity (the app and the IDE share one setup; they cannot install plugins from
GitHub themselves, so the plugin is connected from a local copy):

```bash
git clone https://github.com/EvgenVer/Agents-tollkit "$HOME/.gemini/agents-toolkit"
```

```bash
python "$HOME/.gemini/agents-toolkit/scripts/antigravity.py" install
```

Then quit the app and the IDE completely and start them again: Antigravity loads plugins
and hooks only when it starts, so a window left open keeps working without studio. The
script copies the plugin to `~/.gemini/config/plugins/studio`, the one place where the
IDE looks for plugins (it does not follow links); `uninstall` instead of `install` removes
the copy. To update, run `git -C "$HOME/.gemini/agents-toolkit" pull`, run `install`
again and restart the same way.

Projects set up by the plugin also name this marketplace in `.claude/settings.json`, so
Claude Code offers to install the plugin when you open such a project elsewhere.

## Autonomy and safety

The agent works without asking for each step. What stops it is deterministic:

| Layer | Claude Code | Codex | Antigravity |
|---|---|---|---|
| Operating-system sandbox | none on native Windows (only macOS, Linux, WSL2) | `.codex/config.toml`: `workspace-write` sandbox, network on, approval on request; applied once you trust the project. On Windows it works only after the sandbox setup below | not set up by studio; Antigravity's own permission settings apply |
| Hooks: denied | reading secrets (`.env`, keys, credential files), force-push, `git reset --hard`, `git clean -f`, discarding all changes, recursive deletes outside the project or of the project, disk commands | the same | the same |
| Hooks: owner asked | `git push`, global installs (`npm -g`, `pip` outside `.venv`, `winget`, `cargo install`, …), deleting files outside the project, reading or writing files outside the project (file tools, `cp`/`mv`, `Set-Content`/`Out-File`, `>` redirects) | the same actions are denied with an explanation, because Codex hooks cannot ask yet; file reads through the shell are not checked | denied with an explanation as in Codex, because Antigravity shows no prompt when a hook asks; the agent's own folders under `~/.gemini` stay readable and its plan artifacts writable |
| Reminders | session start: where work stopped, uncommitted changes, a long TASKS.md, empty project commands; before stopping: record evidence, update Now, check pages that mention changed files | the same | the same; before stopping, the agent is sent back once per turn |

Hooks are a safety net, not a wall: a script the agent writes can still do what the hooks
cannot see. Commit often, and keep backups of important folders outside your projects.

In Antigravity a hook that fails would block every tool, so the studio hooks let the
action through when they fail, and they do nothing at all when `python` is missing from
PATH. They were checked on Windows only.

In Claude Code use the auto permission mode for long sessions. In Codex on Windows, turn
on its sandbox once: accept the sandbox setup Codex offers, or set `[windows] sandbox =
"elevated"` in `~/.codex/config.toml` (the setup needs administrator approval). Inside
the sandbox `.git` is read-only, so Codex runs `git init`, `git add` and `git commit`
outside it and asks you first; allow those commands permanently when it offers.

## Start a new project

1. Create an empty folder and open it in Claude Code, Codex or Antigravity.
2. Write what you want to build, for example *"Use the idea skill. I want …"*. The agent
   sets up the project and brainstorms the idea with you.
3. Approve `docs/PRODUCT.md`, go through the technical interview, approve
   `docs/ARCHITECTURE.md`.
4. The agent builds stage by stage, reports after each stage and asks you only about
   decisions that are yours. Write *"Continue"* in any session or tool to resume.
5. Read the documentation site: the agent starts it at `http://localhost:8000`, or run
   `.venv\Scripts\zensical serve` yourself (`.venv/bin/zensical serve` on macOS/Linux).

## Move an existing project to this version

Install the plugin, open the project in Claude Code, Codex or Antigravity and paste the
text below. The agent moves the project on a separate branch, `studio-migration`, checks
the result against the branch you were on and merges it into that branch only when every
check passes. If a check fails, it stops and tells you, and your branch stays as it was.
Nothing is pushed, and the previous version stays in the git history. Codex asks before
each git command it runs outside its sandbox; allow them.

> Migrate this project to the studio plugin. Do not push and do not start new product
> work.
> 1. Prepare. If there are uncommitted changes, stop and ask me what to do with them.
>    The current branch is the base. Run the project's tests, if it has any, and note
>    the result. Create the branch `studio-migration` from the base and do steps 2-7
>    there, committing as you go.
> 2. Rename AGENTS.md, CLAUDE.md, .claude/settings.json and .codex/config.toml, those
>    that exist, by adding `.old` to the name. Then run the setup script of the studio
>    `idea` skill as the skill describes: it creates these files fresh from its
>    templates, adds the other missing files and keeps the rest, and commits what it
>    created (in Codex, commit them yourself before any edit). The new AGENTS.md and
>    CLAUDE.md replace the old ones: do not bring back the old rules on how agents work
>    (workflow, planning, documents, memory, reviews, subagents, safety), because the
>    new rules cover them. Carry over only what belongs to this project: facts about the
>    product and its code go into the documents, rules only this project needs (for
>    example, a folder that must not be changed) go into a short `## Project rules`
>    section before `Project commands`, and the project's own settings go into the new
>    settings files.
> 3. Rebuild the documents with the studio templates. The product description and
>    specification become docs/PRODUCT.md, approved, since I agreed them before.
>    Technical decisions become docs/ARCHITECTURE.md and docs/decisions/, approved.
>    Plans and tasks (PLAN.md, TASKS.md, specs/) become docs/TASKS.md: keep finished
>    tasks with their evidence, archive finished stages into docs/history/, and put the
>    current position in Now. Note durable preferences from old memory files and where
>    you put them.
> 4. Write the technical documentation from the actual code with the docs skill:
>    components, main flows, data, operations, glossary. Keep the project's own pages in
>    docs/ and link them into the site.
> 5. After their content is carried over, remove the old documents and toolkit files,
>    whichever exist: the `.old` files from step 2; DESCRIPTION.md, SPECIFICATION.md,
>    PLAN.md, TASKS.md and MEMORY.md in the project root; AGENT_RUNS.md, specs/,
>    docs/explain/, .agents/docs/ and .agent-toolkit-manifest.tsv;
>    .claude/commands/grill.md, .claude/commands/orchestrate.md,
>    .claude/agents/executor.md, .claude/agents/reviewer.md, .codex/agents/executor.toml
>    and .codex/agents/reviewer.toml; and the toolkit skills ai-eval-design,
>    bug-forensics, code-review, dependency-vetting, docs-maintenance, grill,
>    orchestration, planning and security-review in .agents/skills/ and .claude/skills/.
>    Keep everything the project added itself, its own skills included. Leave the
>    ignored backup folder .agent-toolkit-backup/ as it is.
> 6. Fill in Project commands in AGENTS.md from the code.
> 7. Check the migration against the base branch. Fix what fails and check again:
>    - The project's code, data and settings are unchanged: `git diff --stat <base>`
>      lists only the files the setup script created or updated, docs/ and the files
>      removed in step 5.
>    - Every file from step 5 that existed is gone. Any other deleted file had its
>      content moved into a new document.
>    - AGENTS.md and CLAUDE.md are the new versions: `git diff` against the step 2
>      commit that created them shows no change in CLAUDE.md and, in AGENTS.md, only
>      Project commands and Project rules. None of the old rules on how agents work
>      came back.
>    - Every project-specific rule and setting from the base branch's AGENTS.md,
>      CLAUDE.md and agent settings is in Project rules, a document or the new settings
>      files.
>    - docs/PRODUCT.md and docs/ARCHITECTURE.md are approved and cover what the old
>      description, specification and decisions said.
>    - Every task from the old plans is in docs/TASKS.md or docs/history/, finished ones
>      with their evidence, and Now shows the current position.
>    - The documentation site builds without errors, and every embedded code snippet
>      points to an existing file.
>    - Every command in Project commands runs, and the tests give the same result as in
>      step 1.
> 8. Only when every check passes, merge `studio-migration` into the base branch, so
>    the base holds only the new version, and delete `studio-migration`. If a check
>    still fails or the merge conflicts, do not merge: leave both branches as they are.
> 9. Report to me: each check with its result and evidence, the project rules and
>    durable preferences you carried over and where you put them, what changed, whether
>    .agent-toolkit-backup/ exists, whether the base branch now holds the new version,
>    and what the next task is.

## Maintain the toolkit

```bash
python -m unittest discover -s tests
```

```bash
claude plugin validate .
```

```bash
agy plugin validate plugins/studio
```

Raise `version` in `plugins/studio/.claude-plugin/plugin.json`,
`plugins/studio/.codex-plugin/plugin.json` and `plugins/studio/.antigravity-plugin/plugin.json`
with every change, so installed copies update after
`claude plugin marketplace update agents-toolkit` and `codex plugin marketplace upgrade`.
Each tool reads its own hook file: Claude Code `hooks/hooks.json`, Codex
`hooks/codex-hooks.json`, Antigravity `hooks.json` at the plugin root.
