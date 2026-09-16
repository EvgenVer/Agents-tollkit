# One working workflow

AGENTS supplies the universal rules. This file owns transitions and recovery.
The planning skill owns document structure; other skills perform their bounded job
and return here. No separate mode catalog or extra tracking documents are required.

## Flow

```mermaid
flowchart TD
    A[Understand request and recover relevant context] --> B{Preparation needed?}
    B -- Read-only --> R[Answer]
    B -- New scope or missing decisions --> C[Prepare relevant documents and resolve decisions]
    C --> D{Execution authorized?}
    D -- No --> W[Present the missing decision or plan]
    D -- Yes --> E[Choose first ready work]
    B -- Authorized bounded work --> E
    E -- Phase not decomposed --> F[Prepare that phase's tasks]
    F --> E
    E -- Scope complete --> Z[Report verified result]
    E -- Checkpoint or no safe work --> W
    E -- Ready task --> G{Action permitted?}
    G -- No --> H[Ask for missing permission and block affected work]
    H --> K[Save state and find independent authorized work]
    G -- Yes --> I[Implement and verify]
    I -- Failed --> J[Reassess evidence and approach]
    J -- Justified safe next step --> G
    J -- No justified next step --> K
    I -- Passed --> L[Review and record result; consider MEMORY]
    L --> E
    K -- Available --> E
    K -- None --> W
```

## Transition rules

| Event | Action |
|---|---|
| Entry/resume | Read relevant project state and eligible MEMORY entries; reconcile files, task state, evidence, and pending user questions |
| Bounded authorized work | Use the existing task/request and relevant checks; do not bootstrap four documents or require a special exemption |
| New requirements/architecture/scope | Prepare affected documents using planning. Ask only material unanswered questions; resolve missing approval before dependent implementation |
| Start execution | An explicit execution instruction is sufficient, including “approved, execute”; preserve its scope and checkpoints |
| Activate a phase | Decompose its outcome before code. Its declared preceding phases must be verified; a later phase with After: none explicitly permits independent work |
| Select work | First ready task in row order in the active phase. Respect After prerequisites and known blockers; an omitted dependency is not evidence of independence |
| Insert work | In-scope necessary work joins the right position. If it is a prerequisite, update dependent After fields. Put new product ideas in Proposals |
| Before each action | Respect scope, permission, and checkpoints. See SECURITY for operation effects; missing permission is not a failed check |
| Successful task | Inspect the diff and relevant checks, record actual result/evidence, update Current references, and continue. A progress message does not end the run |
| Close phase | Confirm the outcome using sufficient task evidence, clear completed Current task references, and check TASKS. Add a check task only for a distinct uncovered integration result |
| Failed check | Reassess the hypothesis. Continue justified progress, not identical failed retries; a fixed failure count is not a stop condition |
| Stuck or missing input | Explain and block affected work. Continue independent ready work; cross-phase work needs explicit independence in PLAN and inclusion in execution scope |
| Permission/decision pending | Complete authorized preparation to make the requested action reviewable. Ask once and wait on affected work; continue independent work. Re-evaluate on new input, without retrying a forbidden operation |
| Finish/stop | Stop at completed scope, an explicit checkpoint, or no safely executable work. For completion, set Current task to none, retain the last phase number, and put the outcome in Resume note. For interruption/blockage, preserve the unfinished work and next action |
| Toolkit update | Only on explicit request, follow README's existing-project procedure as bounded maintenance; do not create another migration plan/scaffold |

Use the planning skill's event-to-document table when requirements or route change.
Reconcile affected documents before dependent work. Ordinary task progress updates TASKS,
not every document. Current is a short resume pointer, not a duplicate status table.

## Verification and review

Inspect unfamiliar checks for side effects. Use the smallest meaningful test set for
the change; broaden for unresolved integration concerns, not for a fixed file count.
Do not rerun a passing check without a relevant change. Reproduction and targeted
regression evidence are appropriate for a bug; prose edits usually need a diff check.

Every write gets a lightweight scope/diff/evidence check. Full code-review is for a
concrete requested review, public/shared contracts, dependencies, sensitive boundaries,
or integration risk. A standalone review remains findings-only; an authorized
implementation may resolve its own review findings without another permission ritual.
A fresh review can add confidence for a substantial/risky change when delegation is
authorized. It does not grant permission to start parallel implementation.

Run the read-only document checker after coherent structural changes, phase
decomposition/closure, requirement/route changes, numbering/dependency edits, or migration.
Correct errors before dependent work or a completion claim. If the checker is unavailable,
compare with the template manually and disclose the limitation. Routine progress updates
do not require repeating the same successful check on unchanged documents.
The checker cannot prove evidence true, infer permission, or judge requirement coverage.

Changed AI instructions need behavioral scenarios and honest coverage reporting;
see [EVALS.md](EVALS.md). Offline tests are not proof of model behavior.

## MEMORY

Create MEMORY only when the first eligible fact exists. Each fact must:
1. Help future sessions and not be cheaply recoverable from code or existing documents.
2. Be an explicit durable user preference, or an environment limitation/workaround
   supported by a reproduced observation and successful verification.
3. Not be a requirement, architecture decision, task status, hypothesis, permission,
   secret, or personal data.

Use Preferences and Environment notes sections; omit empty sections.
Each entry is `fact — source — verified date`. Consider additions/corrections after
verified work and before handoff; do not write something merely to satisfy the step.
Read applicable facts on resume. Reverify when the relevant environment/version changed
or evidence contradicts an entry; correct obsolete advice. Missing MEMORY never blocks.

## Parallel work

Orchestration requires explicit user opt-in and actual benefit from independent ready
work with disjoint ownership and stable contracts. No arbitrary minimum task/file count
or duration. Otherwise continue sequentially when execution is authorized, unless the
user requested parallel-only work. Never present serial dispatch as parallel execution.

Use the orchestration skill for dispatch/integration. The coordinator owns task state,
scope, approvals, and integration; executors own only their assigned files and checks.
No task renumbering while executors are running. Preserve local model selections.

## Reports and interruption

Explain in the user's language: current phase, verified outcome, active/next task,
deviations, and required decisions. Use concrete effects rather than internal ceremony.
Follow AGENTS's rule for an instruction-caused pause: identify the source and exact
requirement, including whether the blocker is an interpretation rather than an explicit
prohibition. A stale skill guideline cannot override the user's authorized scope.
At an interruption, preserve the task, actual checks, blocker, and next action in
existing TASKS or the bounded request's existing note. Do not create NOTES or a
separate STATUS/PROGRESS/ROADMAP. Do not claim completion from a changing task count.

Record results and applicable operation permissions with tasks. AGENT_RUNS is only for
an explicitly requested separate log; keep eval transcripts/reports in linked artifacts.
