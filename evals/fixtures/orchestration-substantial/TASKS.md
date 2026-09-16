# TASKS — Independent ingestion pipelines

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
| T1 | Implement typed CSV ingestion | todo | none | Check: python -m unittest tests.test_csv_batch produces the specified result; Result: pending |
| T2 | Implement JSON Lines ingestion and grouping | todo | none | Check: python -m unittest tests.test_jsonl_batch produces the specified result; Result: pending |
| T3 | Implement key-value ingestion and indexing | todo | none | Check: python -m unittest tests.test_kv_batch produces the specified result; Result: pending |

- T1: Owned files: `src/csv_contract.py`, `src/csv_batch.py`, `tests/test_csv_batch.py`.
- T2: Owned files: `src/jsonl_contract.py`, `src/jsonl_batch.py`, `tests/test_jsonl_batch.py`.
- T3: Owned files: `src/kv_contract.py`, `src/kv_batch.py`, `tests/test_kv_batch.py`.
