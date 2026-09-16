# TASKS — Event normalization library

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
| T1 | Implement CSV table normalization | todo | none | Check: python -m unittest tests.test_csv_normalizer produces the specified result; Result: pending |
| T2 | Implement JSON Lines normalization | todo | none | Check: python -m unittest tests.test_json_normalizer produces the specified result; Result: pending |
| T3 | Implement key-value line normalization | todo | none | Check: python -m unittest tests.test_text_normalizer produces the specified result; Result: pending |

- T1: Owned files: `src/csv_normalizer.py`, `tests/test_csv_normalizer.py`.
- T2: Owned files: `src/json_normalizer.py`, `tests/test_json_normalizer.py`.
- T3: Owned files: `src/text_normalizer.py`, `tests/test_text_normalizer.py`.
