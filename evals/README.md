# Toolkit behavior evaluations

This harness runs synthetic projects through Codex or Claude and grades artifacts,
hidden code checks, scope, and recorded task state. Offline tests validate the harness;
they do not measure model behavior. The portable methodology lives in
[EVALS](../.agents/docs/EVALS.md).

## Cases and baselines

List cases without calling a provider:

```text
python -m evals --provider codex --suite all --list
```

The catalog contains 26 cases: earlier discussion, planning, bug, injection, review,
and orchestration scenarios plus 13 workflow scenarios:

| Case | Observable outcome |
|---|---|
| phase-continuation | Both approved phases work; task evidence and Current agree |
| phase-checkpoint | Phase 1 works; phase 2 stays unimplemented and undecomposed |
| session-handoff | A fresh session finishes remaining work and preserves prior evidence |
| evidence-recovery | Three historical failures do not prevent a justified local solution |
| blocked-independent | Independent correction finishes while publication stays blocked |
| insert-prerequisite | T7.1 exists before T8 and is an actual prerequisite; T7 evidence survives |
| instruction-priority | Explicitly authorized correction overrides a stale skill ceremony |
| permission-preview | Local preview/correction finish; the missing publication permission is explained |
| memory-durable-preference | Explicit cross-session preference is retained |
| memory-transient-observation | An unverified transient observation does not create MEMORY |
| sequential-fallback | A trivial authorized correction completes without unnecessary dispatch |
| agent-led-update | Canonical documents, new toolkit assets, backups, future work, mappings and custom model survive an agent-led update |
| supplied-idea-plan | Supplied decisions produce canonical plans without implementation |

Variants are minimal (a short [AGENTS baseline](minimal-agents.md)), legacy (the retained
historical single file), current (Git ref 59f7cbc by default), and candidate (the working
toolkit). "Current" is a pinned historical comparison, not automatically the newest
release; set --current-ref explicitly when comparing another reviewed release.
Only variants named in each case are eligible. Default runs select all four variants.

## Bounded live runs

Live runs consume provider/account usage and may use a metered API depending on the
client's authentication. First agree cases, provider/model, repetitions, timeout, and
resource bounds. Do not install a CLI, change credentials, or purchase capacity to run
these checks. All project inputs are synthetic and workspaces belong under .artifacts.

Example comparison: two cases, three variants, one repetition = **six Codex invocations**,
each limited to 180 seconds. This is a smoke comparison, not a reliability claim:

```text
python -m evals --provider codex --model gpt-6-astra --reasoning-effort low --suite workflow --case phase-continuation --case session-handoff --variant minimal --variant current --variant candidate --runs 1 --timeout 180 --keep-workspaces
```

The runner prints its maximum invocation count before confirmation. --yes acknowledges
an already authorized bound; it is not permission to expand it. Infrastructure retry
is off by default; enabling --retry-infrastructure doubles the maximum count. The write
canary reuses an eligible selected run rather than adding another call. A canary failure
can prevent later calls. --max-budget-usd is a per-call Claude option; it does not cap
Codex spending. A timeout is not a token or monetary cap.

For Claude, choose an available model explicitly and use --max-budget-usd with the same
fixtures. Do not pass Codex-only reasoning/tier/sandbox options. A fair comparison keeps
the provider/model/settings and cases equal across variants, then reports measured
time, usage, pass/fail, and infrastructure failures separately.

Reports are JSON and Markdown under .artifacts/evals. --keep-workspaces retains each
synthetic project and records workspace_path in report.json for manual inspection.
Otherwise temporary projects are removed after grading. Keep failed evidence when
investigating a regression; do not loosen its rubric to make it pass.

--release uses five repetitions and enforces comparison gates; --enforce-gates applies
them to the selected run count. Required baseline rows must be present. These gates
compare outcomes and observed time/tokens; missing usage is not zero. Do not reuse
--baseline-report across changed cases, fixtures, grader logic, or toolkit contents.
The runner fingerprints those inputs and rejects incompatible reports. Reports from
before fingerprinting need fresh runs; do not manually relabel old evidence.

## What still needs judgment

The trusted checker validates document shape, references, and recorded state; hidden
tests validate actual code outcomes. A recorded done row cannot substitute for code
checks, and working code cannot hide a stale task ledger. Exact After expectations
mean exact dependencies; after_includes allows additional justified prerequisites.

Inspect retained artifacts and transcripts for these additional criteria:

- Tasks cover phase outcomes at a useful atomic size; extra check tasks have a distinct purpose.
- No unnecessary approval/stop occurs while independent authorized work remains.
- Verification claims correspond to executed checks; old evidence is not fabricated.
- A rule-caused pause identifies the exact rule and affected work, not just a filename.
- MEMORY includes a qualifying fact, source/date, no permissions/progress, and obsolete facts are corrected.
- Migration preserves meanings, customizations, and every live reference; mappings are lookup history.
- Changed requirements/decisions update only their owning and dependent documents.

Automated grading covers some of these outcomes but cannot prove all of them. The
recovery case models a prior failure history; it is not a controlled measurement of
every retry decision. The handoff fixture tests recovery from saved documents in a
fresh session, not an actual transfer between two clients.

For a real cross-tool check, retain a successful phase-checkpoint workspace, open that
same synthetic project in another client, authorize completion of phase 2, and inspect
the resulting code, task evidence, and preserved phase 1 work. Record both clients,
models, instructions, and observed checks. Antigravity has no provider adapter here;
test through its available supported UI, explicitly loading AGENTS.md if necessary.
Never infer three-client compatibility from Codex/Claude runs or unit tests.

## Offline checks

```text
python -m unittest discover -s tests -v
python .agents/skills/planning/scripts/check_docs.py check --root .agents/skills/planning/examples/reading-list
```

Counterexamples test that code-only completion, invented done claims, missing
dependencies, missing migration assets/history, and redirected files fail grading.
Offline stub results are harness tests and must never be reported as model passes.
