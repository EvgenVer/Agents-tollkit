from collections.abc import Iterable


def normalize_json_pairs(
    pairs: Iterable[tuple[str, object]], line_number: int
) -> dict[str, object]:
    raise NotImplementedError
