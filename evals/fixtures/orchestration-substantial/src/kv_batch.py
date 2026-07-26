from collections.abc import Iterable


def load_kv_records(
    value: str, required: Iterable[str] = ()
) -> list[dict[str, str]]:
    raise NotImplementedError


def index_kv_records(
    value: str, key: str
) -> dict[str, dict[str, str]]:
    raise NotImplementedError
