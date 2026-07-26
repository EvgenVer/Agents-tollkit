# SPECIFICATION — Independent ingestion pipelines

## Common key rules

Every pipeline normalizes keys by trimming surrounding whitespace, applying Unicode
case-folding, replacing each whitespace run with `_`, and rejecting empty or duplicate
normalized keys. Public functions raise `ValueError` for invalid input. No third-party
dependencies are allowed.

## Typed CSV ingestion

`load_typed_csv(value, schema, required=())` returns `list[dict[str, object]]`.

- `schema` maps normalized field names to one of `str`, `int`, `float`, or `bool`.
- The first non-blank CSV record is the header. Whitespace-only input returns `[]`.
- Header keys follow the common key rules. Every schema and required key must exist in
  the normalized header.
- Blank data records are ignored. Other records must match the header width.
- String cells are trimmed. Integers and finite floats use Python syntax after trimming.
  Booleans accept case-insensitive `true/false`, `yes/no`, and `1/0`.
- Blank cells become `None` unless required; a blank required cell is invalid.
- Conversion and width errors identify the one-based CSV record number.

`normalize_csv_header(values)` and `coerce_csv_value(value, kind, record, field,
required=False)` live in `csv_contract.py`; parsing lives in `csv_batch.py`.

## JSON Lines ingestion

`load_json_events(value, required=())` returns `list[dict[str, object]]`.

- Blank lines are ignored. Every other line must contain exactly one JSON object.
- Duplicate JSON members, including members that collide only after key normalization,
  are invalid.
- Top-level keys follow the common key rules. String values are trimmed; other JSON
  values are preserved.
- Every required normalized key must be present. Errors identify the one-based line.

`group_json_events(value, field)` loads the events and returns
`dict[str, list[dict[str, object]]]`, preserving input order. The grouping field is
normalized, must exist in every event, and must contain a scalar value; its string form
is the group key.

Pair validation lives in `jsonl_contract.py`; loading and grouping live in
`jsonl_batch.py`.

## Key-value ingestion

`load_kv_records(value, required=())` returns `list[dict[str, str]]`.

- Blank lines are ignored. Each other line uses standard shell quoting and contains
  whitespace-separated `key=value` tokens.
- Keys follow the common key rules. Values are trimmed. Missing `=`, empty/duplicate
  keys, malformed quoting, or missing required keys are invalid.
- Errors identify the one-based line.

`index_kv_records(value, key)` returns `dict[str, dict[str, str]]`. The normalized index
key must exist and have a non-empty unique value in every record.

Line parsing lives in `kv_contract.py`; loading and indexing live in `kv_batch.py`.

## Acceptance

All task tests and the integration suite pass. The three task file scopes remain
disjoint.
