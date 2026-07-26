from collections.abc import Iterable


def load_json_events(
    value: str, required: Iterable[str] = ()
) -> list[dict[str, object]]:
    raise NotImplementedError


def group_json_events(
    value: str, field: str
) -> dict[str, list[dict[str, object]]]:
    raise NotImplementedError
