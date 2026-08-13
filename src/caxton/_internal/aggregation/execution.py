from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from typing import Any

from caxton._internal.semantic import SemanticRowEvaluator
from caxton.core._values import normalize_cell_value
from caxton.core.errors import AggregateEvaluationError, CaxtonError
from caxton.core.models import AggregateExpr, Column
from caxton.core.protocols import DataSource
from caxton.core.values import CellValue


@dataclasses.dataclass(frozen=True, slots=True)
class InputRow:
    """One source row together with its evaluated semantic column values."""

    index: int
    raw: object
    values: Mapping[str, CellValue]


def read_rows(
    source: DataSource[Any],
    columns: Sequence[Column],
    evaluator: SemanticRowEvaluator,
) -> tuple[InputRow, ...]:
    rows: list[InputRow] = []
    for index, raw in evaluator.iter_source_rows(source):
        semantic = evaluator.evaluate_row(source, raw, columns, row_index=index)
        rows.append(InputRow(index=index, raw=raw, values=semantic.values))
    return tuple(rows)


def execute_aggregate(  # noqa: WPS211
    expression: AggregateExpr,
    rows: Sequence[InputRow],
    *,
    source: DataSource[Any],
    columns: Sequence[Column],
    evaluator: SemanticRowEvaluator,
    path: str,
) -> CellValue:
    included = tuple(
        row
        for row in rows
        if expression.where is None
        or bool(
            evaluator.evaluate_expression(
                source,
                row.raw,
                columns,
                expression.where,
                row_index=row.index,
                values=row.values,
            ),
        )
    )
    if not included and expression.has_default:
        return normalize_cell_value(expression.default)
    inputs = tuple(
        tuple(
            evaluator.evaluate_expression(
                source,
                row.raw,
                columns,
                item,
                row_index=row.index,
                values=row.values,
            )
            for row in included
        )
        for item in expression.expressions
    )
    function_name = getattr(
        expression.function,
        "__name__",
        type(expression.function).__name__,
    )
    try:
        result = expression.function(*inputs)
    except CaxtonError:
        raise
    except Exception as error:
        raise _aggregate_error(
            error,
            function_name,
            len(included),
            path,
            phase="callable",
        ) from error
    try:
        return normalize_cell_value(result)
    except Exception as error:
        raise _aggregate_error(
            error,
            function_name,
            len(included),
            path,
            phase="result_normalization",
        ) from error


def _aggregate_error(
    error: Exception,
    function_name: str,
    scope_size: int,
    path: str,
    *,
    phase: str,
) -> AggregateEvaluationError:
    message = (
        f"Aggregate {function_name!r} failed"
        if phase == "callable"
        else f"Aggregate {function_name!r} returned an unsupported result"
    )
    return AggregateEvaluationError(
        message,
        path=path,
        context={
            "exception_type": type(error).__name__,
            "function": function_name,
            "phase": phase,
            "scope_size": scope_size,
        },
    )


__all__ = ("InputRow", "execute_aggregate", "read_rows")
