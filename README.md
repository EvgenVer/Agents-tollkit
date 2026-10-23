# Agents Toolkit

A small set of rules, skills and hooks for building your own apps with Claude Code and
Codex when you are not a software developer. You describe what you want; the agent
interviews you, designs and plans the product, builds it on its own, and explains what
it built in plain language so you keep understanding your product.

Toolkit v1 (the large rule set with evals) is preserved under the git tag `v1-legacy`.

## What is inside

| Part | Where | What it does |
|---|---|---|
| Project rules | [AGENTS.md template](plugins/studio/skills/idea/assets/AGENTS.md) | Short rules every project gets: who decides what, when to ask you, how to prove work, how to keep state |
| `idea` skill | [plugins/studio/skills/idea](plugins/studio/skills/idea/SKILL.md) | Interviews you and writes `docs/PRODUCT.md` for your approval |
| `plan` skill | [plugins/studio/skills/plan](plugins/studio/skills/plan/SKILL.md) | Designs the architecture and stages: `docs/ARCHITECTURE.md`, `docs/TASKS.md` |
| `explain` skill | [plugins/studio/skills/explain](plugins/studio/skills/explain/SKILL.md) | Makes interactive HTML explainers with diagrams and keeps the product map |
| Hooks | [plugins/studio/hooks](plugins/studio/hooks/studio_hooks.py) | Restore where work stopped, block secrets and destructive commands, record progress before stopping |

Each project you build ends up with:

```text
AGENTS.md              rules for the agents (CLAUDE.md just imports it)
docs/PRODUCT.md        what the product does and for whom — you approve it
docs/ARCHITECTURE.md   how it is built, and why: the decision log
docs/TASKS.md          stages, tasks, evidence, and "Now": where work stopped
docs/explain/          explanations for you; open index.html for the product map
```

## Install once per tool

The hooks need Python 3 available as `python` (on macOS and Linux Codex uses `python3`).
Replace the path with your checkout of this repository, or use `EvgenVer/Agents-tollkit`
once this version is on GitHub's default branch.

Claude Code:

```bash
claude plugin marketplace add "D:/my program/AGENTS_toolkit"
```

```bash
claude plugin install studio@agents-toolkit
```

Codex:

```bash
codex plugin marketplace add "D:/my program/AGENTS_toolkit"
```

```bash
codex plugin add studio@agents-toolkit
```

Codex does not run plugin hooks until you approve them: start Codex, run `/hooks`, and
trust the three `studio` hooks. Repeat after the hooks change.

For long autonomous sessions, let the agent edit and run commands inside the project
without asking each time: in Claude Code use the auto permission mode; in Codex use the
`workspace-write` sandbox with the `on-request` approval policy. The hooks and the rules
still stop destructive and outward-facing actions.

## Start a new project

1. Create an empty folder, initialise git in it (or ask the agent to), and open it in
   Claude Code or Codex.
2. Write: *"Use the idea skill. I want …"* and describe your idea in your own words.
3. Answer the interview questions and approve `docs/PRODUCT.md`.
4. The agent designs the product, shows you an explainer, and asks only about the real
   choices. After you agree, it builds stage by stage, reports after each stage, and
   asks you only at important forks.
5. Later, write *"Continue"* in any session or tool; the agent reads `Now` and goes on.
   Ask *"Explain how … works"* whenever something is unclear.

## Move a v1 project to this version

Install the plugin first, then paste this request into the project's agent session:

> Migrate this project from AGENTS toolkit v1 to the studio plugin. Work on a new git
> branch, commit the result, do not push.
> 1. Replace AGENTS.md and CLAUDE.md with the templates from the studio plugin's `idea`
>    skill assets. First carry any project-specific rules from the old files (anything
>    that is not generic toolkit text) into the new documents.
> 2. Rebuild the documents with the studio templates: DESCRIPTION.md and
>    SPECIFICATION.md become docs/PRODUCT.md (approved, since I agreed them before);
>    PLAN.md technical decisions become docs/ARCHITECTURE.md with a decision log;
>    PLAN.md phases and TASKS.md become docs/TASKS.md, keeping finished tasks with their
>    evidence and the current position in Now. Show me any durable preferences from
>    MEMORY.md and where you put them.
> 3. After their content is carried over, remove the old DESCRIPTION.md,
>    SPECIFICATION.md, PLAN.md, TASKS.md, MEMORY.md, AGENT_RUNS.md and specs/, and the
>    toolkit v1 files: .agents/docs, .agents/skills, .claude/skills,
>    .claude/commands/grill.md, .claude/commands/orchestrate.md,
>    .claude/agents/executor.md, .claude/agents/reviewer.md, .codex/agents/executor.toml,
>    .codex/agents/reviewer.toml and .agent-toolkit-manifest.tsv. Keep everything the
>    project added itself.
> 4. Fill in Project commands in AGENTS.md from the code, then use the explain skill to
>    create the product map docs/explain/index.html.
> 5. Show me what changed and what the next task is. Do not start new product work.

## How the hooks behave

- **Session start** (also after the context is compacted): gives the agent the `Now`
  section of `docs/TASKS.md` and mentions uncommitted changes.
- **Before each tool call**: blocks reading or printing secret files (`.env`, keys,
  credentials), force-pushing, `git reset --hard`, `git clean -f`, discarding all
  changes, and recursive deletes outside the project or of the whole project.
- **Before the agent stops**: if changed files are newer than `docs/TASKS.md`, the agent
  is asked once to record the evidence and commit, or to update `Now`.

The hooks act only in projects with `docs/TASKS.md`, except the guard, which protects
every project. They are a safety net, not a sandbox: an agent determined to read a
secret could still find a way, so keep real secrets out of reach where you can.

## Maintain the toolkit

```bash
python -m unittest discover -s tests
```

```bash
claude plugin validate .
```

Raise `version` in both `plugins/studio/.claude-plugin/plugin.json` and
`plugins/studio/.codex-plugin/plugin.json` with every change, so installed copies
update after `claude plugin marketplace update` and `codex plugin marketplace upgrade`.
