from collections.abc import Iterable, Mapping

from src.csv_contract import CsvKind


def load_typed_csv(
    value: str,
    schema: Mapping[str, CsvKind],
    required: Iterable[str] = (),
) -> list[dict[str, object]]:
    raise NotImplementedError
