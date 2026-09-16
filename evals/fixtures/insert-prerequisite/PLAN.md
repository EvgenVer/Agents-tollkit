# PLAN — Insert required rendering

## Phases

| Phase | Outcome | After | Completion check |
|---|---|---|---|
| 1 | Finish text rendering | none | Normalization, rendering and composed output pass |

## Technical decisions

Use two pure functions in src/formatter.py and unittest in tests/test_formatter.py.

## Verification

Run meaningful local checks for normal, empty, and Unicode inputs. Reuse phase 1
evidence for phase 2 integration when it remains applicable.
