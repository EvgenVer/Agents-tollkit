# SPECIFICATION — Text helper

## Requirements

normalize(value) case-folds text, trims it, and joins whitespace-separated words with one space.
summarize(value) returns word frequencies after normalization, as a Python dict.

## Constraints and non-goals

Python standard library only; no network, package installation, or unrelated files.

## Acceptance

Unicode, repeated whitespace, empty input, and repeated words produce the specified results.
