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
| `.claude/commands/` | Claude Code slash commands (e.g. `/grill`, `/orchestrate`) — Claude-Code-specific; other tools use the natural-language trigger. |
| `.claude/agents/`, `.codex/agents/` | Managed role agents for opt-in orchestration (executor/reviewer); local model tuning is never silently overwritten. |
| `evals/` | Local legacy/current/candidate behavior benchmark with hidden checks and JSON/Markdown reports. |
| `AGENTS_WORKFLOW_LEGACY/AGENTS_v1.md` | Immutable single-file baseline used by the benchmark. |

## Install

Clone or download the toolkit, inspect it, and run the preflight from your project
directory. The installer deliberately does not fetch executable content. Do not pipe a
remote script directly into a shell.

```powershell
# Windows (PowerShell)
$toolkit = Join-Path $env:TEMP "Agents-toolkit"
git clone --depth 1 https://github.com/EvgenVer/Agents-tollkit.git $toolkit
Get-Content "$toolkit\install.ps1"
& "$toolkit\install.ps1" -Source $toolkit -DryRun
& "$toolkit\install.ps1" -Source $toolkit
```

```bash
# macOS / Linux / Git-Bash
toolkit="$(mktemp -d)/Agents-toolkit"
git clone --depth 1 https://github.com/EvgenVer/Agents-tollkit.git "$toolkit"
less "$toolkit/install.sh"
bash "$toolkit/install.sh" --source "$toolkit" --dry-run
bash "$toolkit/install.sh" --source "$toolkit"
```

The preflight prints every create/update/preserve action and aborts on conflicts before
writing. The installer updates files it owns using `.agent-toolkit-manifest.tsv` hashes;
it never deletes project directories, never overwrites a locally modified managed file,
and does not run `git init`. Project documents and the project's `README.md` remain
untouched. A locally tuned role-agent file causes a visible conflict so its model choice
can be reconciled with updated role instructions.

To migrate a project that contains the exact legacy single-file toolkit:

```powershell
& "$toolkit\install.ps1" -Source $toolkit -DryRun -MigrateLegacy
& "$toolkit\install.ps1" -Source $toolkit -MigrateLegacy
```

```bash
bash "$toolkit/install.sh" --source "$toolkit" --dry-run --migrate-legacy
bash "$toolkit/install.sh" --source "$toolkit" --migrate-legacy
```

The old `AGENTS.md` is backed up under `.agent-toolkit-backup/<timestamp>/`. A modified
legacy file is treated as a conflict and must be reconciled manually. An existing modular
installation can be adopted without changes when its files exactly match the source;
otherwise the first manifest-based update stops instead of guessing which edits are yours.

To start a project: open Claude Code or Codex here and say — *"Follow AGENTS.md. No
DESCRIPTION yet, grill me on <your idea>, then the planning gate, and stop for approval."*
(In Claude Code you can also run `/grill`.) From there the agent runs: bootstrap DESCRIPTION →
planning gate → risk gate → small-batch implement → validate → self-review → report.

**Optional — orchestrated execution:** once SPEC/PLAN/TASKS are approved, `/orchestrate`
(Claude Code; explicit phrase in other tools) first checks whether parallelism is useful.
Eligible work runs in dependency-ready waves of up to three disjoint executors, followed
by integration validation and one final review. Small, sequential, overlapping, or
high-risk work returns `ORCHESTRATION_NOT_BENEFICIAL` without dispatching subagents.
Strictly opt-in: without the command the workflow is unchanged.

*Manual install (no script):* copy `AGENTS.md`, `CLAUDE.md`, `docs/`, `.agents/`,
`.claude/commands/`, `.claude/agents/`, and `.codex/agents/` (not the whole `.claude/` —
it may hold a machine-specific `settings.local.json`); merge the `.gitignore` secrets
section; and copy `.agents/skills/` to `.claude/skills/` for native Claude Code discovery.

## Automated comparison

List the deterministic scenarios without calling a model:

```bash
python -m evals --provider codex --suite all --list
```

Run a bounded smoke comparison of legacy, the pinned current baseline, and the working
candidate:

```bash
python -m evals --provider codex --suite smoke --runs 1 --yes
```

Run the reproducible three-pass comparison (75 provider calls) from a standalone terminal,
not from a nested Codex Desktop session:

```bash
python -m evals --provider codex --suite all --runs 3 --enforce-gates --model gpt-5.6-sol --reasoning-effort high --service-tier default --yes
```

The first scheduled write case doubles as a write-canary. A read-only provider workspace
or a failed trivial candidate edit stops the run immediately instead of wasting the
remaining calls or turning blocked edits into behavioral failures.
The enforced gates require the candidate workflow to stay within 15% of legacy/current
for wall time and tokens while passing every run. Candidate orchestration is compared
with the same candidate executing the same fixture sequentially; it must preserve
quality, dispatch real parallel agents, reduce median wall time by at least 20%, and
keep tokens within 1.5x.

Use `--provider claude` for Claude Code. `--release` uses five repetitions and enforces
the same gates. Reports are written to `.artifacts/evals/`; provider calls are never made
without explicit `--yes`. A real run sends the selected fixture and installed toolkit
instructions to that provider, so review the fixtures and call bound before adding
`--yes`. The pinned `current` commit must exist locally; fetch it in a shallow CI checkout
or override it with `--current-ref <commit>`.

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
