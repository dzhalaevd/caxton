from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import cast

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from formata import data_source

Row = dict[str, int]
MaterializedRows = list[Row]
MaterializedOperation = Callable[[MaterializedRows], int]
GeneratorOperation = Callable[[int], int]

_ROW_COUNT = 100_000
_EXPECTED_TOTAL = sum(range(_ROW_COUNT))


def _direct_list_access(rows: MaterializedRows) -> int:
    return sum(row["value"] for row in rows)


def _formata_list_access(rows: MaterializedRows) -> int:
    source = data_source(rows)
    values = (source.get_value(row, "value") for row in source.iter_rows())
    return sum(cast("Iterator[int]", values))


def _rows_iterator(row_count: int) -> Iterator[Row]:
    for index in range(row_count):
        yield {"value": index}


def _direct_generator_access(row_count: int) -> int:
    return sum(row["value"] for row in _rows_iterator(row_count))


def _formata_generator_access(row_count: int) -> int:
    source = data_source(_rows_iterator(row_count))
    values = (source.get_value(row, "value") for row in source.iter_rows())
    return sum(cast("Iterator[int]", values))


@pytest.fixture(scope="module")
def materialized_rows() -> MaterializedRows:
    return [{"value": index} for index in range(_ROW_COUNT)]


@pytest.mark.benchmark(group="list-of-dicts")
@pytest.mark.parametrize(
    "operation",
    [_direct_list_access, _formata_list_access],
    ids=("direct-python", "formata-data-source"),
)
def test_materialized_mapping_field_access(
    benchmark: BenchmarkFixture,
    materialized_rows: MaterializedRows,
    operation: MaterializedOperation,
) -> None:
    actual = benchmark(operation, materialized_rows)

    assert actual == _EXPECTED_TOTAL


@pytest.mark.benchmark(group="one-shot-generator")
@pytest.mark.parametrize(
    "operation",
    [_direct_generator_access, _formata_generator_access],
    ids=("direct-python", "formata-data-source"),
)
def test_one_shot_generator_field_access(
    benchmark: BenchmarkFixture,
    operation: GeneratorOperation,
) -> None:
    actual = benchmark(operation, _ROW_COUNT)

    assert actual == _EXPECTED_TOTAL
