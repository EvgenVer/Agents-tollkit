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

## Lite comparison

The 823-word Lite at commit 1ab2e86 was evaluated on phase-continuation,
phase-checkpoint, session-handoff, blocked-independent, and insert-prerequisite,
three times each. Codex CLI 0.154.0, gpt-5.6-luna, low reasoning, 180 seconds/call,
no retries. `--candidate-root lite` supplied only AGENTS.md; the trusted grader stayed
outside the project. All 15 provider calls completed successfully.

Lite passed functional and canonical-structure checks in 15/15 attempts and all strict
checks in 13/15. The historical full-toolkit comparison scored 15/15. Both Lite failures
were narrow rubric mismatches: changing a blocked result from pending to unverified,
and correcting PLAN's function count from two to three when PLAN edits were excluded.
Neither broke implementation, removed the publication blocker, or lost completed-task
evidence. Original scores remain unchanged; they do not prove lower Lite quality.

Versus the saved full-toolkit runs, Lite's total input plus output was 2,305,364 versus
2,716,842 (-15.1%); uncached input plus output was 457,300 versus 405,162 (+12.9%).
Median successful-call time was 68.2 versus 71.5 seconds. Different cache shares and
measurement times limit interpretation; cost and account-limit savings are unmeasured.
A stale Resume note also survived some runs of both editions despite structural passes.

These are five small development-used fixtures with canonical starting documents,
not a held-out study or evidence for other models/clients. Rules, fixtures, and rubric
were frozen throughout. Full raw reports, checkpoints, hashes, and manual findings
are retained locally under `.artifacts/evals/luna-lite-20260916/`; historical reports
remain under `.artifacts/evals/luna-comparison-20260915/`.

## Selective-context comparison

The updated full toolkit ran the same five cases three times with the Lite comparison's
CLI/model/settings and unchanged fixtures/rubric. All 15 calls and strict checks passed.
Against the preceding full toolkit on all 15 attempts, total input plus output was
2,740,061 versus 2,716,842 (+0.9%); uncached input plus output was 378,461 versus
405,162 (-6.6%). Median time was 75.1 versus 71.5 seconds. General token savings are
not established. The small fixtures have no initial Context pointers, so this does
not measure prepared pointers on large projects. One generic Resume note survived.
The candidate fingerprint stayed unchanged; all 15 checkpoints and raw reports are
saved locally under `.artifacts/evals/luna-context-20260916/`. Its findings also compare
all variants on 14 matched attempts with known usage; historical reports are unchanged.

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
