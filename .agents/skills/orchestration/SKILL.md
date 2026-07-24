---
name: orchestration
description: Execute an approved TASKS.md with bounded parallel executor waves and one integration review. Use ONLY after an explicit /orchestrate or equivalent request. Before dispatching, decline with ORCHESTRATION_NOT_BENEFICIAL when fewer than three meaningful tasks exist, the ready-set width is below two, file scopes overlap, shared contracts are unresolved, risk is high, or safe parallel subagents are unavailable. Do not use for planning or ordinary sequential implementation.
---

# Orchestration

Use parallelism only where it can provide a measurable benefit. The coordinator owns
scope, scheduling, integration, validation, and reporting; executors own disjoint task
files. Do not turn every task into an executor/reviewer ceremony.

## Activation

Activate only on an explicit `/orchestrate` or an equally explicit request for
orchestrated execution. Never self-trigger.

## Preflight

Complete every check before the first dispatch:

1. Confirm that `SPECIFICATION.md`, `PLAN.md`, and `TASKS.md` are approved.
2. Parse each active task's `files:`, `verify:`, `dep:`, and `parallel:` fields. Do not
   infer missing scope.
3. Confirm that parallel subagents and safe concurrent writes are available.
4. Build the dependency-ready set.
5. Apply the eligibility gate below.
6. Report the effective role models once. Ask for approval only if a requested model is
   unavailable, a fallback or material model change is required, or the user explicitly
   asks to choose models. Otherwise use the configured/session defaults without another
   confirmation round.

## Eligibility gate

Dispatch no subagents unless all conditions hold:

- at least three meaningful active tasks remain;
- at least two tasks are ready at the same time;
- at least two ready tasks have disjoint declared file scopes;
- no selected task changes an unresolved shared API, schema, type, migration, dependency,
  security boundary, or other shared contract;
- each selected task has a bounded verification command;
- the environment can run the selected executors concurrently.

If any condition fails, stop before dispatch and return:

```text
ORCHESTRATION_NOT_BENEFICIAL
reason: <specific failed condition>
recommended_mode: sequential
```

This is a successful routing decision, not an orchestration failure. Do not silently
fall back to sequential implementation inside this skill.

## Coordinator contract

The coordinator does not edit production code. It may update orchestration state after
integration. It:

- computes ready waves and prevents overlapping ownership;
- dispatches all executors in a wave before waiting;
- validates returned file scopes and rejects unrelated changes;
- runs integration checks after each wave;
- commits a validated logical wave when repository policy calls for commits;
- performs one final independent review of the integrated diff.

## Wave algorithm

Repeat until no active tasks remain:

1. Recompute tasks whose dependencies are complete.
2. Select the maximum safe disjoint set, capped at three. If two or more eligible tasks
   are ready, never dispatch a one-task wave.
3. Brief each executor with only its task, exact file ownership, relevant contract
   excerpt, verification command, and areas it must not touch.
4. Dispatch every executor in the wave before waiting for any result.
5. Collect concise results: changed files, verification command and outcome, blockers.
6. Reject scope overlap or unrelated edits. Stop the affected task rather than merging
   ambiguous ownership.
7. Run the wave's task checks and the smallest relevant integration check.
8. Mark verified tasks complete; leave failed tasks blocked with evidence. Recompute the
   next ready set.

Executors self-verify their atomic work. Do not dispatch a reviewer per successful task.

## Review and correction budget

After all waves pass integration validation, dispatch one fresh-context reviewer for the
complete integrated diff, relevant requirements, and `docs/CODE_REVIEW.md`.

- No findings: finish.
- Localized finding: send only the affected task and finding to one executor, then rerun
  its check plus integration validation.
- Integration failure: dispatch one targeted reviewer/diagnostician with the failure
  evidence and relevant diffs.
- Allow one correction iteration. If it still fails, stop and report the blocker. Do not
  create an open-ended executor/reviewer loop.

## Stop conditions

Stop on high-risk actions, unresolved requirements, overlapping file ownership,
unexpected dependency changes, repeated validation failure, or loss of parallel
execution capability. Continue an independent wave only when it cannot be affected by
the blocked work.

## Report

Report:

- eligibility decision and ready-set width;
- tasks and executor count per wave;
- wall-clock duration when the environment exposes it;
- validation commands and outcomes;
- review and correction count;
- blocked work and residual risks.

Keep resumable status in `TASKS.md` only when the project already uses that status
convention.
