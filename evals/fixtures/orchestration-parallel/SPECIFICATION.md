# SPECIFICATION — Event normalization library

## Requirements

All three modules normalize field names by trimming surrounding whitespace, applying
Unicode case-folding, and replacing each whitespace run with `_`. Empty or duplicate
normalized field names are invalid.

### CSV

- `normalize_csv_table(value)` returns `list[dict[str, str]]`.
- The first non-empty record is the header.
- Quoted fields and embedded commas follow Python's standard CSV rules.
- Values are trimmed. Entirely blank data records are ignored.
- A data record whose width differs from the header raises `ValueError`.
- Empty input returns an empty list.

### JSON Lines

- `normalize_json_lines(value)` returns `list[dict[str, Any]]`.
- Blank lines are ignored; every other line must contain one JSON object.
- String values are trimmed; non-string values are preserved.
- Invalid JSON, a non-object value, or invalid normalized keys raise `ValueError` that
  identifies the one-based line number.

### Key-value lines

- `normalize_key_value_lines(value)` returns `list[dict[str, str]]`.
- Blank lines are ignored.
- Each non-empty line is split with standard shell quoting rules into `key=value`
  tokens, so quoted spaces in values are supported.
- Values are trimmed. Missing `=`, empty keys, or duplicate normalized keys raise
  `ValueError` that identifies the one-based line number.

- No third-party dependencies.

## Acceptance

All existing and integration tests pass.
