# SPECIFICATION — Insert required rendering

## Requirements

normalize case-folds and joins whitespace. render(value) wraps normalized text in brackets.
summarize(value) must return render(normalize(value)); e.g. ' A  B ' becomes '[a b]'.

## Constraints and non-goals

No dependencies or external operations. Preserve the completed normalization work.

## Acceptance

Empty input becomes '[]'; Unicode and whitespace are handled by normalization.
