# SPECIFICATION — Normalizer library

## Requirements
- CSV input returns trimmed cells and omits empty cells.
- JSON object keys are lowercased and string values are trimmed.
- Plain text collapses all whitespace and lowercases the result.
- No third-party dependencies.

## Acceptance
All existing and integration tests pass.
