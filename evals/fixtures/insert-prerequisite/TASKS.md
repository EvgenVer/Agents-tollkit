# TASKS — Insert required rendering

## Current

- Execution scope: implement the remaining text-rendering task
- Authorization source: fixture owner authorized local implementation; run prompt controls checkpoints
- Current phase: 1
- Current task: none
- Next checkpoint: none
- Resume note: continue the first ready task using existing evidence

## Tasks

### Phase 1

| ID | Task | Status | After | Verification |
|---|---|---|---|---|
| T7 | Normalize text | done | none | Check: tests.test_normalize; Result: passed — fixture setup verified empty, whitespace and Straße inputs |
| T8 | Compose summary text using normalize and render | todo | T7 | Check: summarize returns rendered normalized words; Result: pending |
