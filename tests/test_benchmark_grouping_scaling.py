"""Scaling benchmarks for matrix sparsity and aggregate expression evaluation.

``test_benchmark_grouping`` measures dense matrices, where the produced cell
count grows linearly with the record count. These benchmarks isolate the two
workloads it cannot see: a sparse matrix, whose cost grows with the product of
its dimension cardinalities, and aggregate evaluation, whose cost grows with
the number of aggregate columns and filters rather than with the row count.

Every helper rebuilds its own row source, because a benchmark round consumes
the source and Caxton refuses to iterate a one-shot source twice.
"""

from __future__ import annotations

import tracemalloc
from collections.abc import Iterator

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from caxton import decimal, field, matrix, sheet, spreadsheet, table, text
from caxton.testing import Rows, inspect_layout

_SPARSE_SIDES = [250, 500, 1_000]
_AGGREGATE_COUNTS = [1, 4, 8]
_AGGREGATE_ROWS = 20_000
_AGGREGATE_GROUPS = 500
_DENSE_SIDE = 10
_QUADRATIC_TOLERANCE = 2.5


def _sparse_rows(side: int) -> Iterator[dict[str, object]]:
    """Yield ``side`` records on the diagonal of a ``side x side`` grid.

    Yields:
        One record per distinct row and column key pair.
    """
    for index in range(side):
        yield {"row": index, "column": index, "value": 1}


def _dense_rows(record_count: int) -> Iterator[dict[str, object]]:
    """Yield records inside a fixed, fully populated grid.

    Yields:
        One record per source row of a dense matrix workload.
    """
    for index in range(record_count):
        yield {
            "row": index % _DENSE_SIDE,
            "column": index % _DENSE_SIDE,
            "value": 1,
        }


def _prepare_sparse(side: int) -> int | None:
    return _prepare_pivot(_sparse_rows(side))


def _prepare_dense(record_count: int) -> int | None:
    return _prepare_pivot(_dense_rows(record_count))


def _prepare_pivot(rows: Iterator[dict[str, object]]) -> int | None:
    document = spreadsheet(
        sheet(
            "Matrix",
            matrix(
                source=rows,
                row=field("row"),
                column=field("column"),
                value=decimal(id="value", source=field("value").agg(sum)),
            ),
        ),
    )
    layout = inspect_layout(document, rows=Rows.none())
    return layout.worksheet("Matrix").block("block[0]").columns


def _prepare_aggregates(aggregate_count: int, *, filtered: bool) -> int | None:
    rows = (
        {
            "key": index % _AGGREGATE_GROUPS,
            "value": index,
            "active": index % 2 == 0,
        }
        for index in range(_AGGREGATE_ROWS)
    )
    condition = field("active") == True if filtered else None  # noqa: E712
    columns = [
        decimal(
            id=f"total_{position}",
            source=field("value").agg(sum, where=condition),
        )
        for position in range(aggregate_count)
    ]
    document = spreadsheet(
        sheet(
            "Summary",
            table(
                source=rows,
                columns=(
                    text(id="key", source="key").grouped(),
                    *columns,
                ),
            ),
        ),
    )
    layout = inspect_layout(document, rows=Rows.none())
    return layout.worksheet("Summary").block("block[0]").rows


def _sparse_peak_bytes(side: int) -> int:
    tracemalloc.start()
    try:
        _prepare_sparse(side)
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


@pytest.mark.benchmark(group="matrix-sparsity")
@pytest.mark.parametrize(
    "side",
    _SPARSE_SIDES,
    ids=[f"{side}-keys" for side in _SPARSE_SIDES],
)
def test_sparse_matrix_preparation(benchmark: BenchmarkFixture, side: int) -> None:
    """Measure a matrix whose dimensions are as high-cardinality as its input."""
    columns = benchmark(_prepare_sparse, side)

    assert columns == side + 1


@pytest.mark.benchmark(group="matrix-sparsity")
@pytest.mark.parametrize(
    "record_count",
    _SPARSE_SIDES,
    ids=[f"{side}-records" for side in _SPARSE_SIDES],
)
def test_dense_matrix_preparation(
    benchmark: BenchmarkFixture,
    record_count: int,
) -> None:
    """Measure the same record counts against a fixed, dense output grid."""
    columns = benchmark(_prepare_dense, record_count)

    assert columns == _DENSE_SIDE + 1


@pytest.mark.benchmark(group="aggregate-evaluation")
@pytest.mark.parametrize(
    "aggregate_count",
    _AGGREGATE_COUNTS,
    ids=[f"{count}-aggregates" for count in _AGGREGATE_COUNTS],
)
def test_aggregate_column_scaling(
    benchmark: BenchmarkFixture,
    aggregate_count: int,
) -> None:
    """Measure how aggregate evaluation scales with the aggregate column count."""
    rows = benchmark(_prepare_aggregates, aggregate_count, filtered=False)

    assert rows == _AGGREGATE_GROUPS + 1


@pytest.mark.benchmark(group="aggregate-filter")
@pytest.mark.parametrize(
    "aggregate_count",
    _AGGREGATE_COUNTS,
    ids=[f"{count}-aggregates" for count in _AGGREGATE_COUNTS],
)
def test_shared_filter_scaling(
    benchmark: BenchmarkFixture,
    aggregate_count: int,
) -> None:
    """Measure the cost of one shared filter across several aggregate columns."""
    rows = benchmark(_prepare_aggregates, aggregate_count, filtered=True)

    assert rows == _AGGREGATE_GROUPS + 1


def test_sparse_matrix_cost_is_not_quadratic() -> None:
    """Doubling sparse dimension cardinality must not quadruple the cost.

    This is a red scaling regression. A sparse matrix currently materializes
    the full cartesian product of its dimensions, so peak memory grows with
    ``rows * columns`` instead of with the record count.
    """
    small = _sparse_peak_bytes(_SPARSE_SIDES[1])
    large = _sparse_peak_bytes(_SPARSE_SIDES[2])

    assert large < small * _QUADRATIC_TOLERANCE
