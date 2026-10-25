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

Install the plugin, then paste this into the project's agent session:

> Migrate this project to the studio plugin. Work on a new git branch, commit the
> result, do not push.
> 1. Run the setup script of the studio `idea` skill; it adds missing files and keeps
>    existing ones. Then replace AGENTS.md and CLAUDE.md with the plugin's templates,
>    first carrying project-specific rules from the old files into the new documents.
> 2. Rebuild the documents with the studio templates. The product description and
>    specification become docs/PRODUCT.md, approved, since I agreed them before.
>    Technical decisions become docs/ARCHITECTURE.md and docs/decisions/, approved.
>    Plans and tasks become docs/TASKS.md: keep finished tasks with their evidence,
>    archive finished stages into docs/history/, and put the current position in Now.
>    Show me durable preferences from old memory files and where you put them.
> 3. Write the technical documentation from the actual code with the docs skill:
>    components, main flows, data, operations, glossary.
> 4. After their content is carried over, remove the old documents and toolkit files:
>    DESCRIPTION.md, SPECIFICATION.md, PLAN.md, MEMORY.md, AGENT_RUNS.md, specs/,
>    docs/explain/, .agents/docs, .agents/skills, .claude/skills,
>    .claude/commands/grill.md, .claude/commands/orchestrate.md, .claude/agents/executor.md,
>    .claude/agents/reviewer.md, .codex/agents/executor.toml, .codex/agents/reviewer.toml
>    and .agent-toolkit-manifest.tsv, whichever exist. Keep everything the project added
>    itself.
> 5. Fill in Project commands from the code, check that the documentation site builds,
>    and show me what changed and what the next task is. Do not start new product work.

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
