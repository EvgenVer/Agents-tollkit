# PLAN — Text helper

## Phases

| Phase | Outcome | After | Completion check |
|---|---|---|---|
| 1 | Text normalization | none | Normal, empty, Unicode and whitespace checks pass |
| 2 | Word frequency report | 1 | Repeated and normalized words produce correct counts |

## Technical decisions

Use two pure functions in src/formatter.py and unittest in tests/test_formatter.py.

## Verification

Run meaningful local checks for normal, empty, and Unicode inputs. Reuse phase 1
evidence for phase 2 integration when it remains applicable.
