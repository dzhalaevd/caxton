from __future__ import annotations

import dataclasses
import warnings
from collections.abc import Mapping, MutableMapping, Sequence
from types import MappingProxyType
from typing import Any, Final

from caxton._internal.semantic import SemanticRowEvaluator
from caxton.core._values import normalize_cell_value
from caxton.core.errors import AggregateEvaluationError, CaxtonError, PerformanceWarning
from caxton.core.models import AggregateExpr, Column, Expression
from caxton.core.protocols import DataSource
from caxton.core.values import CellValue

BUFFERED_ROW_WARNING_THRESHOLD: Final[int] = 1_000_000


@dataclasses.dataclass(frozen=True, slots=True)
class InputRow:
    """Retained values needed after the original source row is released."""

    index: int
    values: Mapping[str, CellValue]
    expressions: Mapping[Expression, object]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "expressions",
            MappingProxyType(dict(self.expressions)),
        )


def read_rows(
    source: DataSource[Any],
    columns: Sequence[Column],
    evaluator: SemanticRowEvaluator,
    *,
    aggregates: Sequence[AggregateExpr] = (),
    path: str = "table",
) -> tuple[InputRow, ...]:
    """Read and evaluate retained row state in exactly one source pass.

    Returns:
        Buffered semantic and aggregate-input values.
    """
    rows: list[InputRow] = []
    column_catalog = {column.id: column for column in columns}
    for index, raw in evaluator.iter_source_rows(source):
        rows.append(
            evaluate_input_row(
                source,
                raw,
                index,
                columns,
                aggregates,
                evaluator,
                column_catalog=column_catalog,
                path=path,
            ),
        )
        if len(rows) == BUFFERED_ROW_WARNING_THRESHOLD + 1:
            warn_if_large_buffer(
                len(rows),
                path=path,
                reason="grouping or aggregation",
            )
    return tuple(rows)


def evaluate_input_row(  # noqa: WPS211
    source: DataSource[Any],
    raw: object,
    index: int,
    columns: Sequence[Column],
    aggregates: Sequence[AggregateExpr],
    evaluator: SemanticRowEvaluator,
    *,
    column_catalog: Mapping[str, Column],
    path: str = "table",
) -> InputRow:
    """Evaluate all retained state before releasing an original row.

    Returns:
        A buffered input row without the original source object.
    """
    semantic = evaluator.evaluate_row(
        source,
        raw,
        columns,
        row_index=index,
        column_catalog=column_catalog,
    )
    expressions = _evaluate_aggregate_expressions(
        aggregates,
        source=source,
        raw=raw,
        index=index,
        columns=column_catalog,
        values=semantic.values,
        evaluator=evaluator,
        path=path,
    )
    return InputRow(
        index=index,
        values=semantic.values,
        expressions=expressions,
    )


def _evaluate_aggregate_expressions(  # noqa: WPS211
    aggregates: Sequence[AggregateExpr],
    *,
    source: DataSource[Any],
    raw: object,
    index: int,
    columns: Mapping[str, Column],
    values: Mapping[str, CellValue],
    evaluator: SemanticRowEvaluator,
    path: str,
) -> Mapping[Expression, object]:
    filters = _unique_expressions(
        tuple(aggregate.where for aggregate in aggregates),
    )
    output = _evaluate_expression_mapping(
        filters,
        source=source,
        raw=raw,
        index=index,
        columns=columns,
        values=values,
        evaluator=evaluator,
    )
    inputs = _unique_expressions(
        tuple(
            expression
            for aggregate in aggregates
            if aggregate.where is None
            or _predicate_matches(output[aggregate.where], row_index=index, path=path)
            for expression in aggregate.expressions
        ),
    )
    output.update(
        _evaluate_expression_mapping(
            inputs,
            source=source,
            raw=raw,
            index=index,
            columns=columns,
            values=values,
            evaluator=evaluator,
        ),
    )
    return output


def _evaluate_expression_mapping(  # noqa: WPS211
    expressions: Sequence[Expression],
    *,
    source: DataSource[Any],
    raw: object,
    index: int,
    columns: Mapping[str, Column],
    values: Mapping[str, CellValue],
    evaluator: SemanticRowEvaluator,
) -> dict[Expression, object]:
    results = evaluator.evaluate_expressions(
        source,
        raw,
        columns,
        expressions,
        row_index=index,
        values=values,
    )
    return dict(zip(expressions, results, strict=True))


def _unique_expressions(
    expressions: Sequence[Expression | None],
) -> tuple[Expression, ...]:
    output: dict[Expression, None] = {}
    for expression in expressions:
        if expression is not None:
            output.setdefault(expression, None)
    return tuple(output)


def warn_if_large_buffer(row_count: int, *, path: str, reason: str) -> None:
    """Warn once when a shape-dependent block retains a very large source."""
    if row_count <= BUFFERED_ROW_WARNING_THRESHOLD:
        return
    warnings.warn(
        f"{path} buffered {row_count:,} rows for {reason}",
        PerformanceWarning,
        stacklevel=3,
    )


def execute_aggregate(
    expression: AggregateExpr,
    rows: Sequence[InputRow],
    *,
    path: str,
    filter_cache: MutableMapping[
        Expression | None,
        tuple[InputRow, ...],
    ]
    | None = None,
) -> CellValue:
    """Execute one aggregate from captured values.

    Returns:
        The normalized aggregate result.
    """
    included = _included_rows(
        expression.where,
        rows,
        filter_cache=filter_cache,
        path=path,
    )
    if not included and expression.has_default:
        return normalize_cell_value(expression.default)
    inputs = tuple(
        tuple(row.expressions[item] for row in included)
        for item in expression.expressions
    )
    function_name = getattr(
        expression.function,
        "__name__",
        type(expression.function).__name__,
    )
    result = _call_aggregate(
        expression,
        inputs,
        function_name=function_name,
        scope_size=len(included),
        path=path,
    )
    return _normalize_aggregate_result(
        result,
        function_name=function_name,
        scope_size=len(included),
        path=path,
    )


def _included_rows(
    where: Expression | None,
    rows: Sequence[InputRow],
    *,
    filter_cache: MutableMapping[
        Expression | None,
        tuple[InputRow, ...],
    ]
    | None,
    path: str,
) -> tuple[InputRow, ...]:
    if filter_cache is not None and where in filter_cache:
        return filter_cache[where]
    included = (
        tuple(rows)
        if where is None
        else tuple(
            row
            for row in rows
            if _predicate_matches(
                row.expressions[where],
                row_index=row.index,
                path=path,
            )
        )
    )
    if filter_cache is not None:
        filter_cache[where] = included
    return included


def _predicate_matches(value: object, *, row_index: int, path: str) -> bool:
    try:
        return bool(value)
    except Exception as error:
        message = "Aggregate predicate evaluation failed"
        raise AggregateEvaluationError(
            message,
            path=path,
            context={
                "exception_type": type(error).__name__,
                "phase": "predicate",
                "row_index": row_index,
            },
        ) from error


def _call_aggregate(
    expression: AggregateExpr,
    inputs: Sequence[Sequence[object]],
    *,
    function_name: str,
    scope_size: int,
    path: str,
) -> object:
    try:
        return expression.function(*inputs)
    except CaxtonError:
        raise
    except Exception as error:
        message = f"Aggregate {function_name!r} failed"
        raise AggregateEvaluationError(
            message,
            path=path,
            context={
                "exception_type": type(error).__name__,
                "function": function_name,
                "phase": "callable",
                "scope_size": scope_size,
            },
        ) from error


def _normalize_aggregate_result(
    result: object,
    *,
    function_name: str,
    scope_size: int,
    path: str,
) -> CellValue:
    try:
        return normalize_cell_value(result)
    except Exception as error:
        message = f"Aggregate {function_name!r} returned an unsupported result"
        raise AggregateEvaluationError(
            message,
            path=path,
            context={
                "exception_type": type(error).__name__,
                "function": function_name,
                "phase": "result_normalization",
                "scope_size": scope_size,
            },
        ) from error


__all__ = (
    "BUFFERED_ROW_WARNING_THRESHOLD",
    "InputRow",
    "evaluate_input_row",
    "execute_aggregate",
    "read_rows",
    "warn_if_large_buffer",
)
