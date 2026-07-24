# AGENTS.md

Universal working rules for AI coding agents in this repository.

Keep this file project-neutral. Do not put product descriptions, stack choices, implementation details, or task progress here. Store project-specific context in the documents listed below.

---

## Purpose

`AGENTS.md` defines how an agent should work in this repository.

It should help the agent:
- understand where project context lives
- avoid duplicated or conflicting documentation
- plan before risky or broad changes
- make small, verifiable changes
- keep the user informed

This file is not the project description. For project intent, read `DESCRIPTION.md`.

---

## Source of Truth

Use project documents in this order:

1. `SPECIFICATION.md` - approved requirements: what must be built and why.
2. `PLAN.md` - approved technical approach and phased implementation plan.
3. `TASKS.md` - current execution checklist and progress log.
4. `DESCRIPTION.md` - original project concept, intent, audience, and product context.
5. `MEMORY.md` - concise stable cross-session context, if present.
6. `AGENTS.md` - repository working rules for agents.

If `SPECIFICATION.md` does not exist yet, derive requirements from `DESCRIPTION.md`.

If documents conflict, do not silently choose one. State the conflict clearly and pause for user clarification when it materially affects scope, architecture, business logic, data handling, dependencies, or implementation.

---

## Instruction Precedence

Follow the most specific applicable instructions.

If a subdirectory contains its own `AGENTS.md`, apply it to files inside that subdirectory. More specific instructions override broader repository instructions when they conflict.

Tool-specific instruction files, such as `CLAUDE.md` or similar, may reference this file for compatibility with a specific agent tool. Avoid duplicating the full contents of `AGENTS.md` into those files unless the tool requires it.

When instruction files conflict, state the conflict and ask for clarification before making risky or broad changes.

---

## Documentation Boundaries

Keep each project document focused on its own purpose.

### `DESCRIPTION.md`

Contains:
- original project idea and intent
- target users or audience
- product or project goals
- product guardrails and non-goals
- domain-specific context

Does not contain:
- detailed implementation tasks
- current progress
- dependency decisions
- technical execution logs

### `SPECIFICATION.md`

Contains:
- approved problem statement
- goals and non-goals
- user-facing or externally visible requirements
- assumptions
- constraints
- acceptance criteria
- risks
- open questions

Does not contain:
- detailed architecture
- dependency installation steps
- atomic implementation tasks
- progress logs

### `PLAN.md`

Contains:
- chosen architecture
- approved technology stack, when applicable
- approved dependency managers
- selected dependencies and why they are needed
- module or component boundaries
- data, API, external service, and integration strategy
- validation strategy
- major business logic decisions
- implementation phases at a high level
- risks and tradeoffs

Does not contain:
- full product description copied from `DESCRIPTION.md`
- atomic task checklist
- task completion progress
- long research notes

`PLAN.md` must describe the implementation plan by phases. Each phase should have a clear goal, expected deliverables, and validation approach.

### `TASKS.md`

Contains:
- detailed decomposition of `PLAN.md` phases into atomic executable tasks
- task status
- dependencies between tasks, when useful
- expected files, modules, or areas for a task, when useful
- whether a task can run in parallel with other tasks, when useful
- validation method for each task or task group
- blocked tasks
- newly discovered tasks
- completed tasks

Does not contain:
- broad architecture reasoning
- duplicated requirements
- full product description
- unrelated notes from previous sessions

`TASKS.md` must be usable as the active development checklist. Every implementation phase in `PLAN.md` must have corresponding tasks in `TASKS.md`.

### `MEMORY.md`

If present, contains only concise stable cross-session context that does not belong in the other planning files.

Appropriate examples:
- durable user preferences
- repeated corrections from the user
- important context that future agents should not rediscover
- temporary decisions that should later be moved to `SPECIFICATION.md`, `PLAN.md`, or `TASKS.md`

Does not contain:
- project requirements
- technical plans
- task lists
- progress logs
- long session summaries
- information already present in other source-of-truth documents

If a memory item becomes an approved requirement, move it to `SPECIFICATION.md`.
If it becomes an approved technical decision, move it to `PLAN.md`.
If it becomes executable work, move it to `TASKS.md`.

### `AGENTS.md`

Contains:
- stable repo-wide working rules for agents
- documentation workflow rules
- safety rules
- validation and reporting expectations

Does not contain:
- project description
- stack-specific instructions
- product-specific business logic
- implementation progress
- temporary notes

---

## Project Context Intake

Before creating or updating planning documents, read:
- `DESCRIPTION.md`
- existing `SPECIFICATION.md`, if present
- existing `PLAN.md`, if present
- existing `TASKS.md`, if present
- `MEMORY.md`, if present

Before implementation, read the planning documents relevant to the requested work.

Do not duplicate `DESCRIPTION.md` in other documents. Reference it and extract only the specific requirements or constraints needed for the current planning or implementation decision.

---

## Project Bootstrap When `DESCRIPTION.md` Is Missing

If `DESCRIPTION.md` does not exist, treat the project as undefined.

Do not create or update `SPECIFICATION.md`, `PLAN.md`, `TASKS.md`, or implementation files until the project idea has been discussed and a user-approved `DESCRIPTION.md` exists.

This bootstrap rule does not block read-only inspection, validation, or explicitly requested narrow maintenance that does not depend on project requirements. In those cases, keep the scope minimal and do not infer broader project intent.

When `DESCRIPTION.md` is missing:
- stay in discussion mode first
- help the user brainstorm and clarify the project idea
- identify the intended users, problem, goals, non-goals, constraints, and important context
- challenge unclear assumptions when they affect scope or direction
- draft `DESCRIPTION.md` from the discussion
- ask the user to approve the draft before continuing

After the user approves `DESCRIPTION.md`, create or update the remaining planning documents according to the mandatory planning workflow.

---

## Discussion Mode vs Execution Mode

Default to discussion mode when the user asks for brainstorming, analysis, comparison, review of options, or clarification.

In discussion mode:
- refine the idea
- ask clarifying questions when needed
- propose alternatives
- compare tradeoffs
- avoid editing files unless explicitly asked
- avoid installing dependencies
- avoid starting implementation

Switch to execution mode only when the user explicitly asks to create, update, implement, fix, install, run, or otherwise change something.

In execution mode:
- follow the planning workflow when required
- keep changes scoped
- update the relevant planning and tracking documents
- validate the result
- report what changed

---

## User Approval

User approval must be explicit.

Agent-created drafts, assumptions, or unanswered proposals are not approved plans. If approval is ambiguous, ask for confirmation before continuing.

---

## Standard Workflow

Use this workflow for every non-trivial request.

### 1. Classify the Request

First decide what kind of work the user is asking for:

- discussion: explain, analyze, compare, brainstorm, or advise
- planning: create or update `SPECIFICATION.md`, `PLAN.md`, `TASKS.md`, or related docs
- implementation: change code, configuration, assets, dependencies, or project files
- validation: run tests, inspect behavior, review output, or diagnose failures
- maintenance: update documentation, memory, task status, or repository rules

If the request is unclear, ask for clarification before making changes.

### 2. Load the Right Context

Read only the context needed for the request.

For product or project questions, read `DESCRIPTION.md`.
For requirements, read `SPECIFICATION.md`.
For architecture, stack, dependencies, phases, or validation strategy, read `PLAN.md`.
For current work and progress, read `TASKS.md`.
For stable cross-session context, read `MEMORY.md` if present.
For agent workflow rules, read `AGENTS.md`.

Do not rely on memory when the answer should come from a source-of-truth file.

### 3. Check Whether Planning Is Required

Before editing implementation files, decide whether the change is already covered by approved planning documents.

Planning is required when the request changes:
- requirements
- architecture
- implementation phases
- business logic
- dependency choices
- external service behavior
- data handling
- validation strategy
- security, privacy, authentication, payments, AI, automation, or integration behavior

If planning is required, follow the mandatory planning workflow and stop for approval before implementation.

If planning is not required, proceed with scoped implementation and keep `TASKS.md` current when task status changes.

### 4. Define Success Before Changing Files

For implementation or validation work, identify:
- the intended outcome
- the files or areas likely to change
- the validation command or manual check
- the main risk or assumption, if any

For small changes, this can be a short internal checklist.
For larger changes, communicate the plan to the user before editing.

### 5. Decide Whether Work Can Be Parallelized

Before editing, check whether any independent parts of the work can be safely done in parallel.

Use parallel work only when tasks do not depend on each other and do not require editing the same files or shared contracts.

If subagents are available, use them only for clearly scoped independent work. The main agent remains responsible for integration, validation, document updates, and the final response.

### 6. Make the Smallest Correct Change

Implement only the approved or requested change.

Prefer:
- local changes over broad rewrites
- existing project patterns over new conventions
- direct readable code over clever abstractions
- documented decisions over silent architecture changes

Do not fix unrelated issues unless the user asks.

### 7. Validate the Result

Run the relevant checks from the project.

Validation may include:
- automated tests
- type checks
- linters
- build commands
- formatting checks
- manual UI or behavior checks
- document consistency review

If validation fails because of your changes, fix the issue and rerun the relevant check.

If validation cannot be run, explain why and report the remaining risk.

### 8. Update Tracking Documents

After implementation or planning work, update only the documents that actually changed in meaning:

- update `SPECIFICATION.md` for requirement changes
- update `PLAN.md` for technical approach or phase changes
- update `TASKS.md` for task progress, blockers, or discovered tasks
- update `MEMORY.md` for stable cross-session context that belongs nowhere else
- update `AGENTS.md` only for durable repo-wide agent workflow rules

Do not duplicate the same information across multiple documents.

### 9. Final Report

End with a concise report that includes:
- what changed
- which files changed
- what validation was run and its result
- whether planning documents remain current
- dependency changes, if any
- blockers or follow-up tasks, if any
- manual verification steps, when useful

---

## Workflow Decision Rules

Use these decision rules when choosing the next action.

If the user asks "what do you suggest?", stay in discussion mode and do not edit files.

If the user asks to "formalize", "plan", "create planning docs", or "prepare execution", update planning documents and stop for approval.

If the user asks to "implement", "fix", "add", "change", or "create", check whether planning is required before implementation.

If existing planning documents are missing and the work is non-trivial, create them first and stop for approval.

If the requested change is small, local, and already covered by approved planning, implement it and validate it.

If implementation reveals a new requirement, architecture change, dependency need, or business logic change, stop implementation, update planning documents, and ask for approval.

If the user corrects workflow behavior repeatedly, propose an `AGENTS.md` update.

---

## Think Before Coding

Do not assume requirements silently.

Before implementing:
- state important assumptions when they affect the solution
- ask when ambiguity materially affects scope, architecture, business logic, data handling, dependencies, or user-visible behavior
- present options when there are multiple reasonable interpretations
- surface tradeoffs when a decision has meaningful cost, risk, or maintenance impact
- push back politely when a simpler or safer approach is clearly better

For trivial, low-risk changes, use judgment and proceed without unnecessary ceremony.

---

## Simplicity First

Prefer the minimum solution that correctly solves the stated problem.

Do not add:
- features that were not requested or approved
- abstractions for one-off code
- speculative configurability
- broad frameworks or tools without a documented need
- complex error handling for unrealistic cases

If a solution becomes larger or more complex than expected, pause and reassess whether a simpler approach is available.

---

## Surgical Changes

Touch only what is needed for the current task.

When editing existing code or documents:
- match the existing style and structure
- avoid unrelated refactors
- avoid formatting churn
- avoid renaming files or moving code unless required
- clean up only unused code created by your own changes
- mention unrelated issues instead of fixing them silently

Every changed line should have a clear reason connected to the user's request.

---

## Goal-Driven Execution

Turn work into verifiable goals.

For multi-step tasks, use a short plan with validation checks:

```text
1. Step - verify with: check
2. Step - verify with: check
3. Step - verify with: check
```

Examples:
- "Fix the bug" means reproduce the bug when practical, fix it, then verify the fix.
- "Add validation" means identify invalid inputs, add validation, then test invalid and valid cases.
- "Refactor" means preserve behavior and run relevant checks before marking it done.

Loop until the result is verified or a blocker is clearly reported.

---

## Parallel Work and Subagents

Use parallel work when tasks are independent and can be completed without conflicting changes.

If subagent capabilities are not available, do not invent a workaround. Do the work sequentially and keep the same validation standards.

Good candidates for parallelization:
- reading independent files
- searching different parts of the codebase
- comparing documentation sources
- running independent validation checks
- reviewing separate modules
- researching alternative approaches
- implementing independent tasks with stable boundaries

Do not parallelize:
- edits to the same files
- dependent implementation steps
- architecture or product decisions that require one shared source of truth
- dependency installation or migration steps
- destructive or high-risk operations
- changes to shared contracts that are still being designed

Use subagents, when available, for isolated work such as:
- code review of a specific area
- research on a specific technology or API
- test failure investigation
- large codebase exploration
- independent implementation options
- implementation of isolated tasks from `TASKS.md`

The main agent remains responsible for:
- defining each subagent's scope
- merging results
- resolving conflicts
- ensuring consistency with `SPECIFICATION.md`, `PLAN.md`, and `TASKS.md`
- updating planning and tracking documents
- running final validation
- giving the final answer to the user

Do not use subagents as a way to bypass planning, approval, validation, or safety rules.

---

## Parallel Implementation with Subagents

When subagents are available, the main agent should look for safe opportunities to implement independent tasks in parallel.

Parallel implementation is allowed only for work that is already approved or explicitly requested under the planning rules above. If the mandatory planning workflow applies, approval must happen before assigning implementation work to subagents.

Before parallel implementation:
- read `PLAN.md` to understand phases, modules, boundaries, and shared contracts
- read `TASKS.md` to identify atomic tasks, dependencies, blockers, and validation steps
- build a simple dependency map between tasks
- identify files, modules, APIs, schemas, or interfaces each task is expected to touch

A task may be assigned to a subagent for parallel implementation only when:
- it is atomic and clearly described in `TASKS.md`
- it has no dependency on another in-progress task
- it does not require changing the same files as another parallel task
- it does not require changing shared contracts without prior approval
- it has a clear validation method
- its expected output can be reviewed and integrated by the main agent

Good candidates for parallel implementation:
- independent modules with stable interfaces
- separate UI components that do not share state changes
- independent backend endpoints with approved API contracts
- isolated tests for different modules
- documentation updates for separate areas
- independent bug fixes in unrelated files

Do not parallelize implementation when tasks involve:
- shared architecture decisions
- dependency installation or package manager changes
- database schema changes or migrations
- authentication, permissions, security, payments, or privacy-sensitive logic
- shared type definitions, API contracts, or data models still under discussion
- files that multiple agents would need to edit
- tasks whose order is unclear

For each subagent, the main agent must provide:
- exact task scope
- files or modules likely involved
- files or areas to avoid
- expected output
- validation command or manual check
- requirement to avoid unrelated refactors

If tasks could be parallelized but `TASKS.md` does not clearly show dependencies, expected files, or touched areas, update `TASKS.md` first or ask for clarification before launching parallel implementation.

After subagents finish, the main agent must:
- review all subagent results
- reject unrelated changes
- resolve conflicts
- ensure architectural consistency
- run final integration validation
- update `TASKS.md`
- report what was parallelized and how it was validated

---

## Mandatory Planning Workflow

Before implementation, update planning documents and stop for approval when the work involves:
- starting a new project
- adding or changing a feature
- changing architecture
- changing business logic
- adding or replacing dependencies
- adding or changing external services
- changing data storage, privacy, security, authentication, payments, AI, automation, or integration behavior
- diverging from the approved plan

Planning sequence:

0. Read `DESCRIPTION.md` and any existing `SPECIFICATION.md`, `PLAN.md`, `TASKS.md`, and `MEMORY.md`.
1. Create or update `SPECIFICATION.md`.
2. Create or update `PLAN.md`.
3. Create or update `TASKS.md`.
4. Run the planning consistency review.
5. Stop and ask the user for approval.

Do not start implementation until the user explicitly approves the planning documents.

For small fixes that are already covered by approved planning documents, implementation may proceed without rewriting all planning files. Update `TASKS.md` if task status, newly discovered work, or blockers change.

---

## Planning Consistency Review

After creating or updating planning documents, review them before asking for approval.

Check that:
- `SPECIFICATION.md` reflects `DESCRIPTION.md` without copying it wholesale
- `SPECIFICATION.md` states what must be built and why
- `PLAN.md` explains how the approved requirements will be implemented
- `PLAN.md` contains high-level implementation phases
- every phase in `PLAN.md` has matching tasks in `TASKS.md`
- `TASKS.md` tasks are atomic, actionable, and verifiable
- `TASKS.md` captures dependencies, expected files or modules, and parallelization notes when useful
- tasks cover the full planned implementation
- requirements, technical decisions, and task progress are not duplicated across files
- `MEMORY.md`, if present, does not duplicate planning documents
- no document contradicts a higher-priority source of truth

If a task is too broad, split it before asking for approval.

If coverage is incomplete, add the missing tasks or call out the gap as blocked.

If documents conflict, state the conflict clearly and pause for clarification.

---

## Atomic Task Criteria

A task in `TASKS.md` is atomic when:
- it has one clear outcome
- it can be completed in one focused work session
- it has a clear validation method
- it does not hide multiple unrelated changes
- it can be marked done or blocked without ambiguity
- its dependencies and expected touched areas can be stated clearly when needed

Prefer concrete verbs such as create, update, add, remove, test, document, validate, or refactor.

Avoid vague tasks such as "implement backend", "finish UI", "improve logic", or "clean up code" unless they are immediately decomposed into smaller tasks.

Each task in `TASKS.md` should include, when useful:
- status
- dependency or blocker
- expected files, modules, or areas
- whether it can run in parallel with another task
- validation command or manual check

---

## Ongoing Maintenance

Keep planning documents current.

Update:
- `SPECIFICATION.md` when requirements change
- `PLAN.md` when technical decisions, architecture, dependencies, integrations, or implementation phases change
- `TASKS.md` when execution steps, progress, blockers, or newly discovered tasks change
- `MEMORY.md` when stable cross-session context should be preserved and does not belong elsewhere
- `AGENTS.md` only when repo-wide agent working rules need to change

Do not continue work from outdated planning documents. Reconcile the documents first.

---

## Dependency Management

Do not assume or introduce a technology stack before it is approved in `PLAN.md`.

Before adding or changing a dependency, identify:
- what part of the project it affects
- why it is needed
- whether it is runtime, development, test, build, infrastructure, AI, integration, or tooling dependency
- whether it introduces platform, privacy, security, licensing, cost, or maintenance implications
- where it is recorded according to the approved project structure

Use the dependency manager and project structure already approved in `PLAN.md`.

Do not install packages globally unless the approved setup explicitly requires it.

Prefer:
- the smallest reasonable dependency set
- mature and well-supported libraries
- clear documentation
- active maintenance
- avoiding dependencies for simple functionality

When a dependency is added or changed, report:
- dependency name
- version or version range, if available
- where it was recorded
- why it was added
- what files changed
- what validation was run

---

## External Services, Data, and AI

Document the approach in `PLAN.md` before adding or changing behavior involving:
- external APIs or SDKs
- AI models or AI-generated data
- authentication or authorization
- payments or billing
- analytics or telemetry
- email, messaging, notifications, or automation
- file storage or databases
- user data, private data, secrets, or credentials
- audio, voice, camera, location, biometrics, or other sensitive capabilities

For generated, stored, or externally exchanged data, prefer explicit schemas and clear validation over loosely structured free-form data.

Do not expose secrets, tokens, private keys, or sensitive user data in logs, commits, documentation, or responses.

---

## Research Rules

Use current, authoritative sources when technical facts may have changed or when adding unfamiliar dependencies, APIs, SDKs, or platform features.

Prefer:
- official documentation
- package or API references
- standards documents
- repository documentation from the maintainers

Use research to compare options, identify risks, and recommend maintainable approaches.

When research affects a decision, summarize the conclusion and include source links where useful.

---

## Validation Rules

Before marking work complete:
- run the relevant validation commands available in the project
- test changed behavior manually when needed
- fix validation failures when they are caused by your changes
- report validation commands and whether they passed or failed

If the project has an approved validation workflow in `PLAN.md`, follow it.

If no validation workflow exists, inspect the project for available scripts, tests, or documented commands and use the most relevant checks.

If validation cannot be run, explain why and describe the remaining risk.

---

## Scope and Safety

Stay inside the current repository or approved workspace.

Do not:
- modify files outside the project
- make unrelated refactors
- rename or move files without need
- delete user work
- overwrite changes you did not make
- run destructive operations without explicit approval
- bypass the documented planning workflow

If an action requires broader permissions, destructive operations, unusual dependency changes, or major architecture changes, stop and ask first.

---

## Version Control Rules

Do not commit, push, create branches, rebase, merge, tag, or open pull requests unless the user explicitly asks.

Before any requested commit:
- inspect the changed files
- distinguish your changes from pre-existing user changes
- include only the intended files
- summarize what will be committed

Never use destructive version control commands, such as hard reset or forced checkout, unless the user explicitly requests that exact action and the risk has been explained.

Do not revert or overwrite changes you did not make. If user changes conflict with the task, pause and ask how to proceed.

---

## Implementation Style

Prefer code and documentation that are:
- simple
- explicit
- easy to read
- easy to debug
- easy to maintain

Avoid:
- cleverness that reduces clarity
- premature optimization
- hidden side effects
- unnecessary abstractions
- inconsistent style

Explain technical terms simply when communicating with a non-specialist user.

---

## Communication Rules

Keep the user informed during substantial work.

Before major changes:
- explain the plan
- identify assumptions
- mention risks or tradeoffs

When proposing options:
- give concise pros and cons
- recommend one option when enough information is available

After changes:
- summarize what was done
- list changed files
- list dependency changes
- report validation results
- explain manual verification steps when relevant
- identify blockers or remaining risks

Avoid unnecessary jargon.

---

## Definition of Done

A task or feature is complete only when:
- relevant planning documents are current
- implementation matches the approved plan
- relevant validation has passed or remaining validation risk is clearly reported
- changed files are listed
- dependency changes are documented
- the result is explained clearly
- manual verification steps are provided when relevant
- `TASKS.md` reflects completed, blocked, or newly discovered work

---

## Feedback Loop

If the user corrects the same type of mistake more than once, propose a small update to `AGENTS.md` so the rule becomes persistent.

Only update `AGENTS.md` for repo-wide working rules.

Do not put project requirements, implementation details, task progress, or temporary notes in `AGENTS.md`.

When updating `AGENTS.md`:
- keep the new rule short
- make it concrete
- make it easy to verify
- avoid duplicating rules already stated elsewhere

---

## Supporting Documents

Keep `AGENTS.md` concise.

Create or update supporting documents only when the information is stable and too detailed for `AGENTS.md`.

Possible supporting documents:
- `docs/ARCHITECTURE.md`
- `docs/API.md`
- `docs/SECURITY.md`
- `docs/DATA.md`
- `docs/EVALS.md`
- `docs/OPERATIONS.md`
- `code_review.md`

Reference supporting documents from `AGENTS.md` only when they become part of the regular workflow.

Do not create supporting documents just to avoid making a decision in `SPECIFICATION.md`, `PLAN.md`, or `TASKS.md`.

---

## Default Behavior in Case of Ambiguity

If requirements are unclear:
- do not guess silently
- state assumptions explicitly
- choose the safest and simplest interpretation only when risk is low
- ask for clarification when ambiguity materially affects scope, architecture, data, dependencies, business logic, or user-visible behavior
- update planning documents before implementation when the ambiguity changes requirements or technical direction

If the user asks for advice or proposals, do not edit files unless they explicitly request file changes.
