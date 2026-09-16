# TASKS — Shared event contract

## Current

- Execution scope: all phase 1 fixture tasks, when the run prompt authorizes execution
- Authorization source: unknown
- Current phase: 1
- Current task: none
- Next checkpoint: none
- Resume note: use the run prompt to establish execution scope; no task has started

## Tasks

### Phase 1

| ID | Task | Status | After | Verification |
|---|---|---|---|---|
| T1 | Define the event schema | todo | none | Check: python -m unittest produces the specified result; Result: pending |
| T2 | Update the producer | todo | T1 | Check: python -m unittest produces the specified result; Result: pending |
| T3 | Update the consumer | todo | T1 | Check: python -m unittest produces the specified result; Result: pending |

- T1: Owned files: `src/event.py`.
- T2: Owned files: `src/event.py`, `src/producer.py`.
- T3: Owned files: `src/event.py`, `src/consumer.py`.
