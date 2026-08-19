from __future__ import annotations

from collections.abc import Iterator
from typing import ClassVar

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from caxton import decimal, field, matrix, sheet, spreadsheet, table, text
from caxton.testing import Rows, inspect_layout

_SMALL_GROUP_COUNT = 8_000
_LARGE_GROUP_COUNT = 32_000
_MATRIX_REPEATS = 20


def _prepare_distinct_groups(group_count: int) -> int | None:
    rows = ({"key": index, "value": 1} for index in range(group_count))
    document = spreadsheet(
        sheet(
            "Grouped",
            table(
                rows,
                text("key").grouped(),
                decimal("total", source=field("value").agg(sum)),
            ),
        ),
    )
    layout = inspect_layout(document, rows=Rows.none())
    return layout.worksheet("Grouped").block("block[0]").rows


def _prepare_dense_matrix(side: int) -> int | None:
    document = spreadsheet(
        sheet(
            "Matrix",
            matrix(
                _matrix_rows(side, _MATRIX_REPEATS),
                row=field("row"),
                column=field("column"),
                value=field("value").agg(sum),
            ),
        ),
    )
    layout = inspect_layout(document, rows=Rows.none())
    return layout.worksheet("Matrix").block("block[0]").rows


def _matrix_rows(side: int, repeats: int) -> Iterator[dict[str, int]]:
    for repeat in range(repeats):
        for row in range(side):
            for column in range(side):
                yield {
                    "row": row,
                    "column": column,
                    "repeat": repeat,
                    "value": 1,
                }


@pytest.mark.benchmark(group="grouping-preparation-scaling")
@pytest.mark.parametrize(
    "group_count",
    [_SMALL_GROUP_COUNT, _LARGE_GROUP_COUNT],
    ids=("8k-groups", "32k-groups"),
)
def test_distinct_group_preparation(
    benchmark: BenchmarkFixture,
    group_count: int,
) -> None:
    occupied_rows = benchmark(_prepare_distinct_groups, group_count)

    assert occupied_rows == group_count + 1


@pytest.mark.benchmark(group="matrix-preparation-scaling")
@pytest.mark.parametrize("side", [20, 40], ids=("20x20", "40x40"))
def test_dense_matrix_preparation(
    benchmark: BenchmarkFixture,
    side: int,
) -> None:
    occupied_rows = benchmark(_prepare_dense_matrix, side)

    assert occupied_rows == side + 1


class _CountedInt(int):  # noqa: WPS600
    comparisons: ClassVar[int] = 0

    def __eq__(self, other: object) -> bool:
        type(self).comparisons += 1
        return bool(super().__eq__(other))

    def __hash__(self) -> int:  # noqa: WPS612
        return super().__hash__()

    @classmethod
    def reset(cls) -> None:
        cls.comparisons = 0


def _counted_group_rows(row_count: int) -> Iterator[dict[str, object]]:
    for index in range(row_count):
        yield {"key": _CountedInt(index), "value": 1}


def _counted_matrix_rows(
    side: int,
    repeats: int,
) -> Iterator[dict[str, object]]:
    for repeat in range(repeats):
        for row in range(side):
            for column in range(side):
                yield {
                    "row": _CountedInt(row),
                    "column": _CountedInt(column),
                    "repeat": repeat,
                    "value": 1,
                }


def test_group_key_comparisons_are_linear() -> None:
    row_count = 2_000
    _CountedInt.reset()

    document = spreadsheet(
        sheet(
            "Grouped",
            table(
                _counted_group_rows(row_count),
                text("key").grouped(),
                decimal("total", source=field("value").agg(sum)),
            ),
        ),
    )
    inspect_layout(document, rows=Rows.none())

    assert _CountedInt.comparisons <= row_count * 4


def test_matrix_key_comparisons_are_linear() -> None:
    side = 30
    repeats = 10
    row_count = side * side * repeats
    _CountedInt.reset()

    document = spreadsheet(
        sheet(
            "Matrix",
            matrix(
                _counted_matrix_rows(side, repeats),
                row=field("row"),
                column=field("column"),
                value=field("value").agg(sum),
            ),
        ),
    )
    inspect_layout(document, rows=Rows.none())

    assert _CountedInt.comparisons <= row_count * 30
