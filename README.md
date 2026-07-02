# AI-Agent Workflow Toolkit

A portable governance harness for AI coding agents (Claude Code, Codex, …). It makes an
agent plan before risky work, stop at approval gates, treat external content as untrusted,
vet dependencies, and validate AI behavior with evals — not just tests.

`AGENTS.md` is the always-loaded entry router; everything else loads on demand.

## What's in here
| Path | Role |
|------|------|
| `AGENTS.md` | Always-loaded router: hard rules, source-of-truth map, skills catalog. **Start here.** |
| `CLAUDE.md` | Thin pointer so Claude Code obeys `AGENTS.md`. |
| `docs/` | Detailed policies: SECURITY, EVALS, TOOLS, CODE_REVIEW, AGENT_WORKFLOWS. |
| `.agents/skills/<name>/SKILL.md` | On-demand procedures (planning, bug-forensics, code-review, …). |
| `.agents/skills/planning/assets/` | Templates: SPECIFICATION, PLAN, TASKS, DESCRIPTION, MEMORY, NOTES, AGENT_RUNS, spec.feature. |
| `.claude/commands/` | Claude Code slash commands (e.g. `/grill`) — Claude-Code-specific; other tools use the natural-language trigger. |

## Install (one command)
From your project directory:

```powershell
# Windows (PowerShell)
irm https://raw.githubusercontent.com/EvgenVer/Agents-tollkit/master/install.ps1 | iex
```
```bash
# macOS / Linux / Git-Bash
curl -fsSL https://raw.githubusercontent.com/EvgenVer/Agents-tollkit/master/install.sh | bash
```

The installer copies the toolkit (`AGENTS.md`, `CLAUDE.md`, `README.md`, `docs/`, `.agents/`,
`.claude/commands/`), **generates `.claude/skills/`** so Claude Code discovers the skills
natively, merges the secrets section into `.gitignore`, and runs `git init` if needed. It is
**idempotent and update-safe** — re-run any time to refresh the toolkit; your `DESCRIPTION`,
`SPECIFICATION`, `PLAN`, `TASKS`, `MEMORY`, `NOTES` are never overwritten.

To start a project: open Claude Code or Codex here and say — *"Follow AGENTS.md. No
DESCRIPTION yet, grill me on <your idea>, then the planning gate, and stop for approval."*
(In Claude Code you can also run `/grill`.) From there the agent runs: bootstrap DESCRIPTION →
planning gate → risk gate → small-batch implement → validate → self-review → report.

*Manual install (no script):* copy `AGENTS.md`, `CLAUDE.md`, `docs/`, `.agents/`, and
`.claude/commands/` (not the whole `.claude/` — it may hold a machine-specific
`settings.local.json`); merge the `.gitignore` secrets section; and copy `.agents/skills/` to
`.claude/skills/` for native Claude Code discovery.

## How the templates are used
You don't fill these by hand. The master skeletons live in
`.agents/skills/planning/assets/` as `*.template.md` and stay there for reuse. When the
planning gate runs, **the agent instantiates them**: it reads a skeleton and writes the
real document into the project — `SPECIFICATION.template.md` → `SPECIFICATION.md` —
dropping the `.template` suffix and deleting the commented-out EXAMPLE block.

Your role is to supply the content and decisions (especially `DESCRIPTION` at the start)
and to approve. The agent fills them in this order: `DESCRIPTION` → `SPECIFICATION` →
`specs/<feature>` → `PLAN` → `TASKS`.

## Skills across tools
`.agents/skills/` is the source of truth and is **natively discovered by Codex and
Antigravity**. **Claude Code** discovers skills from `.claude/skills/`, so the installer
generates `.claude/skills/` as a copy — the same `SKILL.md` files, so all three tools find
them without a hint. The catalog in `AGENTS.md` §12 stays as the router/index — keep it in
sync when you add a skill.

## Don't duplicate the rules
`AGENTS.md` is authoritative. This README only explains how to adopt the toolkit; it is not
a second copy of the rules. Change rules in `AGENTS.md` (with approval), never here.
