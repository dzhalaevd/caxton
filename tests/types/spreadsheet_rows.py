from __future__ import annotations

from collections.abc import Iterator

from typing_extensions import assert_type

from caxton._spreadsheet.preparation.semantic import SemanticRowEvaluator  # noqa: PLC2701
from caxton.core.protocols import DataSource


class User:
    name: str


def check_source_rows(source: DataSource[User]) -> None:
    evaluator = SemanticRowEvaluator()
    rows = evaluator.iter_source_rows(source)
    assert_type(rows, Iterator[tuple[int, User]])
