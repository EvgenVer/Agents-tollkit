# AI-Agent Workflow Toolkit

Shared working rules for Codex, Claude Code, and agents that can read AGENTS.md.
The aim is a readable plan, one task ledger, and continued work within the user's
authorized scope. Project details stay out of the universal rules.

## Choose a version

| Version | Best fit | What to copy/install |
|---|---|---|
| Lite | Small projects with a short plan and sequential work | Only [lite/AGENTS.md](lite/AGENTS.md) |
| Full toolkit | Projects needing packaged skills, templates, and a document checker | Use the installers below |

### Use Lite

Copy [lite/AGENTS.md](lite/AGENTS.md) to the project root as `AGENTS.md`. Review and
merge any existing rules instead of overwriting them. No installer, Python, skills,
or other toolkit files are required. The current installers install the full toolkit.

Start the agent with:

> Read AGENTS.md. Use the project idea I provide for DESCRIPTION.md. Prepare only
> the planning documents this work needs, then implement within my authorized scope.

For a client that does not automatically load AGENTS.md, explicitly ask it to read
the file at the start of the session. Keep the file's rules project-neutral.

Lite includes the canonical headings and PLAN/TASKS table formats. Bounded corrections
use existing documents or the request; multi-step project work gets a written plan
and task ledger. Document consistency is checked by the agent without an external
script. A [bounded Luna comparison](evals/README.md#lite-comparison) found working
results and valid document structure in 15/15 Lite attempts; 13/15 met every strict
criterion. Total processed context fell, but uncached input plus output increased
relative to the full toolkit; cost or account-limit savings are not established.
The earlier minimal AGENTS baseline is a different file, not this Lite version.

When moving from Lite to the full toolkit, use the existing-project update procedure
below. Compatible document formats reduce rewriting; review actual documents and
custom rules, and preserve their contents. The clean installer refuses existing rules.

## Start a new project with the full toolkit

Requirements: PowerShell on Windows, or Bash on Linux/macOS/Git Bash.
Git is needed only when downloading the toolkit. Python 3.10+ is needed for the
optional document checker, not installation.

Keep a reviewed toolkit checkout **outside** the target project. Run from an empty
project directory (a Git directory, README, LICENSE, .gitignore, and .gitattributes
are allowed):

~~~powershell
# Windows; replace the example path with your toolkit checkout.
& "C:\tools\AGENTS_toolkit\install.ps1" -Source "C:\tools\AGENTS_toolkit" -DryRun
& "C:\tools\AGENTS_toolkit\install.ps1" -Source "C:\tools\AGENTS_toolkit"
~~~

~~~bash
# Linux / macOS / Git Bash
bash /path/to/AGENTS_toolkit/install.sh --source /path/to/AGENTS_toolkit --dry-run
bash /path/to/AGENTS_toolkit/install.sh --source /path/to/AGENTS_toolkit
~~~

Source selection: an explicit source, then TK_SRC, then the script's toolkit checkout.
Without a local source, a downloaded script clones the repository's master branch
into a temporary directory. Inspect that revision before trusting it. Dry run requires
a local source and makes no writes or downloads.

The installer adds AGENTS.md, CLAUDE.md, .agents, Claude commands/skills/roles, Codex
roles, and an informational file inventory. It does not initialize Git, install
packages, create project plans, or change existing bootstrap files. Application files,
existing rules/plans, and a previous toolkit installation cause refusal **before
installation writes**. Re-running the installer is not an update. The old migration
flags are explicitly rejected. Links, junctions where detectable, hard links, and
protected source paths are unsupported. Do not modify source or target concurrently
with installation; an I/O failure can leave a partial install that needs inspection.

Open the project in your agent and describe the idea. For example:

> Read AGENTS.md. I want an offline reading-list utility. Use what I have already
> explained, ask only for missing decisions, and prepare the project documents.

Then authorize the desired implementation scope:

> Implement the agreed plan through all phases. Continue with independent ready work
> when one task is blocked. Explain progress in plain language.

A direct request for a bounded correction can authorize that correction without a
full document set. Approving a design alone does not imply permission for every
external or destructive operation. Existing explicit permissions remain valid within
their scope; progress reports and phase boundaries are not automatic stopping points.

## Read the project state

| File | Read it to understand |
|---|---|
| DESCRIPTION.md | The idea, audience, and context |
| SPECIFICATION.md | Required behavior, constraints, and acceptance |
| PLAN.md | Ordered phase outcomes, architecture/stack decisions, verification approach |
| TASKS.md | Current scope/checkpoint and atomic tasks, dependencies, results |

All four use [fixed templates](.agents/skills/planning/assets/) with stable English
headings; project prose can use the agreed language. PLAN contains no duplicate task
status. TASKS is grouped by phase; decompose a phase before starting it, retain completed
rows, and normally leave future phases coarse.

For full-toolkit task entry, read Current, the requested task and prerequisites, its
PLAN phase, and global constraints first. An optional `Context:` line before a phase's
table points to relevant file sections or code directories; tasks inherit it. Add
`- T4: Context: ...` below the table only for extra sources. These are reading pointers,
not copied requirements, required inventories, or access permissions. Missing pointers
do not block work. Follow dependencies, search for specific gaps, and reuse unchanged
context within a session. Refresh affected pointers during ordinary source changes.
The [selective-context comparison](evals/README.md#selective-context-comparison)
preserved all 15 scenario passes; reduced total token usage is not established.

Task table columns are **ID / Task / Status / After / Verification**. Rows express
priority; After expresses actual prerequisites. Insert T7.1 before T8 if new work
belongs there, and add T7.1 to T8's After when it is required. Do not create T7.1.1.
A done task needs actual verification evidence; skipped checks remain unverified.
A phase can reuse task checks that already prove its outcome.

See the [filled example and state transitions](.agents/skills/planning/examples/reading-list/README.md).
To inspect structure or derive a status view:

~~~text
python .agents/skills/planning/scripts/check_docs.py check --root .
python .agents/skills/planning/scripts/check_docs.py status --root .
~~~

Use --json for machine-readable output. Check after phase decomposition/closure or
other coherent structural changes, not every progress note. Reuse an unchanged passing
result. The script reads only the four named documents and
does not run project commands or edit files. It checks format and references; the
agent still assesses task size, requirement coverage, permissions, and evidence truth.
Context links are reviewed by the agent; the script does not follow their targets.

The single [workflow graph](.agents/docs/AGENT_WORKFLOWS.md) defines selection,
decomposition, verification, recovery, checkpoints, and continuation. A report explains
what changed, what was verified, and what comes next or needs the user.

## Create optional files only when needed

| Artifact | Exact trigger |
|---|---|
| MEMORY.md | An explicit durable preference or reproduced environment limitation with a verified workaround, useful across sessions and not cheaply recoverable elsewhere |
| specs/name.md | A separately maintained public API/file-format compatibility contract, persisted-schema evolution, permission/state matrix, or independently versioned AI behavior contract |
| PLAN / Technical decisions / Integrations | A service or MCP is actually adopted |
| TASKS / Proposals | There is an out-of-scope idea to retain |
| TASKS / ID changes | A format migration changes existing IDs |
| AGENT_RUNS.md | The user explicitly asks for a separate run log |

MEMORY entries record the fact, source, and date; reevaluate them when context changes.
Do not store current progress, requirements, architecture, hypotheses, permissions, or
secrets there. NOTES, STATUS, PROGRESS, and ROADMAP are not extra workflow requirements.

## Update an existing project

**Ask the agent to update it; do not run the installer.** This is the authoritative
update procedure. A template change requires understanding task meaning and references,
so no script converts or merges existing project documents.

1. Identify the reviewed new toolkit source and inspect the project's current rules,
   documents, relevant code, and version-control status. Read only needed nonsecret
   content. Identify project-specific rules, configured models, completed work, live
   references, and useful legacy documentation. Reuse known decisions.
2. Preserve originals of every nonsecret file to be replaced or removed, including
   uncommitted changes, under .agent-toolkit-backup/date-time/ in the project (or an
   already agreed equivalent). Add that location to the project's ignore file. Do not
   copy secrets or rely on Git alone to preserve uncommitted content. No whole-project
   backup, reset, or automatic rollback engine is required.
3. Reconcile the new universal AGENTS/CLAUDE rules, .agents skills/guides, Claude
   commands/skill copies, and Claude/Codex roles. Keep configured model choices and
   compatible user customizations. Move product context into DESCRIPTION/SPECIFICATION,
   technical decisions into PLAN; resolve any material conflicting rule with the user.
   Refresh both skill copies from the reconciled canonical .agents source.
4. Rewrite the four core documents using the new templates. Recover facts from the
   project instead of inventing requirements, approval, completion, or evidence.
   Keep a coarse phase sequence in PLAN; decompose the current phase in TASKS and retain
   useful future decomposition. Preserve done/cancelled work and its result evidence.
   If old completion has no proof, record Result: unverified — evidence unavailable.
5. Normalize **all** legacy phase/task IDs, including terminal rows, into the new
   sequence. Update Current, After, links in active specs/code/comments/docs, and every
   other live reference together. Under TASKS / Tasks / ID changes, record qualified
   previous references and their new targets. Historical text in backups is not a live
   alias. If the project already uses the canonical format, keep its valid IDs stable.
6. Move useful content before removing obsolete toolkit-owned docs/TOOLS.md,
   docs/CODE_REVIEW.md, old toolkit guides in docs/, NOTES/template, or risk-summary
   template. Tool choices belong in PLAN; working results belong with tasks; durable
   facts may qualify for MEMORY. Preserve unrelated project docs and requested historic
   logs. Remove only the identified obsolete files covered by the update authorization.
   Treat a previous manifest as historical installation information, not overwrite
   authority.
7. Run the new document checker once; review semantic coverage, task order, blockers,
   evidence, customizations, adapter links, and the final diff. Run relevant existing
   project checks if behavior changed. Resolve ambiguous meaning before dependent work;
   continue independent reconciliation. Report changed files, remaining decisions, and
   the next ready task. The update request itself does not start product implementation.

Example: legacy references such as "phase A / item 1.2", "B-03", and "patch-final"
become T1, T2, and T3 in execution order. A completed "B-03" remains done with the same
evidence but is now T2; all live prerequisites use T2. The ID changes table records
"B-03 → T2". During later ordinary work, done/cancelled IDs stay stable; only a bounded
unfinished queue may be renumbered.

Copy this request into the **existing project's** agent session and replace the path:

> Update this project to the reviewed toolkit at /absolute/path/to/AGENTS_toolkit.
> Follow its README section "Update an existing project"; do not use its installer.
> I authorize reconciliation of toolkit files and planning documents, preservation of
> nonsecret originals in the project's ignored backup directory, and removal of the
> obsolete toolkit-owned files identified in that procedure after their useful content
> is preserved. Keep project code, unrelated documentation, configured models, and
> compatible custom rules. Normalize legacy task IDs, including completed ones, and
> update all live references; preserve task meaning, statuses, and evidence. Ask only
> about decisions you cannot infer reliably. Check the result and report the next
> ready task; do not begin product implementation as part of this update.

## Tool entry points and skills

AGENTS.md is the shared source; CLAUDE.md imports it. Installation copies the canonical
.agents/skills to .claude/skills. Claude commands are thin adapters. Codex role files
and Claude role files support explicit orchestration; orchestration may use a sequential
fallback when parallel work provides no benefit, unless the user requested parallel
execution only. Role model choices are configuration and must survive an update.

For a tool that does not automatically load AGENTS.md (including an Antigravity setup
without such a rule), explicitly instruct it to read AGENTS.md and follow linked skills.
The common file format supports handoff; tool discovery and real session behavior
still need validation in each installed client. This repository's runner supports
Codex and Claude; it does not establish Antigravity compatibility by itself.

The nine skills are planning, grill, bug-forensics, code-review, dependency-vetting,
ai-eval-design, docs-maintenance, orchestration, and security-review. Load them for
their stated triggers; the default is one continuing workflow, not a menu of modes.

## Maintain and verify the toolkit

Toolkit guides live in [.agents/docs](.agents/docs/); project docs/ stays project-owned.
Review/security checklists live in the corresponding skills. Behavior benchmark
commands, baselines, cases, and coverage limits are in [evals/README.md](evals/README.md).

~~~text
python -m unittest discover -s tests -v
python .agents/skills/planning/scripts/check_docs.py check --root .agents/skills/planning/examples/reading-list
~~~

Tests use disposable synthetic fixtures. Live model evaluations are a separate,
bounded operation; passing unit tests does not demonstrate improved agent behavior.
