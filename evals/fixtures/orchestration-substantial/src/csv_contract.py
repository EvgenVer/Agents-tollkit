from typing import Literal


CsvKind = Literal["str", "int", "float", "bool"]


def normalize_csv_header(values: list[str]) -> list[str]:
    raise NotImplementedError


def coerce_csv_value(
    value: str,
    kind: CsvKind,
    record: int,
    field: str,
    *,
    required: bool = False,
) -> object:
    raise NotImplementedError
