from __future__ import annotations

import dataclasses
import operator
from collections.abc import Callable, Iterator, Mapping, Sequence
from functools import singledispatchmethod
from types import MappingProxyType
from typing import Any, cast

from formata._internal.data.accessors import DefaultRowAccessor
from formata.core._values import normalize_cell_value
from formata.core.errors import (
    DataSourceIterationError,
    FieldAccessError,
    FormataError,
    MissingFieldError,
    SourceEvaluationError,
)
from formata.core.models import (
    BinaryExpression,
    BinaryOperator,
    CallableSource,
    Column,
    Expression,
    FieldRef,
    Literal,
    PathRef,
)
from formata.core.protocols import DataSource
from formata.core.values import CellValue

BinaryOperation = Callable[[Any, Any], object]

_BINARY_OPERATIONS: Mapping[BinaryOperator, BinaryOperation] = {
    BinaryOperator.ADD: operator.add,
    BinaryOperator.SUBTRACT: operator.sub,
    BinaryOperator.MULTIPLY: operator.mul,
    BinaryOperator.DIVIDE: operator.truediv,
    BinaryOperator.EQUAL: operator.eq,
    BinaryOperator.NOT_EQUAL: operator.ne,
    BinaryOperator.LESS_THAN: operator.lt,
    BinaryOperator.LESS_THAN_OR_EQUAL: operator.le,
    BinaryOperator.GREATER_THAN: operator.gt,
    BinaryOperator.GREATER_THAN_OR_EQUAL: operator.ge,
}
_NOT_EVALUATED = object()
_SOURCE_END = object()


@dataclasses.dataclass(frozen=True, slots=True)
class SemanticRow:
    """One immutable row keyed by semantic column identity."""

    index: int
    values: Mapping[str, CellValue]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))

    def __getitem__(self, column: str) -> CellValue:
        return self.values[column]


@dataclasses.dataclass(slots=True)
class _RowContext:
    data_source: DataSource[Any]
    row: object
    row_index: int
    columns: Mapping[str, Column]
    values: dict[str, CellValue] = dataclasses.field(default_factory=dict)
    resolving: set[str] = dataclasses.field(default_factory=set)


class SemanticRowEvaluator:
    """Evaluate every column source consistently before family lowering."""

    def __init__(self) -> None:
        self._path_accessor = DefaultRowAccessor()

    def iter_rows(
        self,
        data_source: DataSource[Any],
        columns: Sequence[Column],
    ) -> Iterator[SemanticRow]:
        """Evaluate rows lazily in source order.

        Yields:
            Immutable semantic rows.
        """
        for row_index, row in _iter_source_rows(data_source):
            yield self.evaluate_row(data_source, row, columns, row_index=row_index)

    def evaluate_row(
        self,
        data_source: DataSource[Any],
        row: object,
        columns: Sequence[Column],
        *,
        row_index: int,
    ) -> SemanticRow:
        """Evaluate one raw row against a semantic column schema.

        Returns:
            An immutable row keyed by semantic column identity.
        """
        context = _RowContext(
            data_source=data_source,
            row=row,
            row_index=row_index,
            columns={column.id: column for column in columns},
        )
        for column in columns:
            self._evaluate_column(column.id, context)
        ordered_values = {column.id: context.values[column.id] for column in columns}
        return SemanticRow(index=row_index, values=ordered_values)

    def _evaluate_column(self, column_id: str, context: _RowContext) -> CellValue:
        cached = context.values.get(column_id, _NOT_EVALUATED)
        if cached is not _NOT_EVALUATED:
            return cast("CellValue", cached)
        if column_id in context.resolving:
            message = f"Cyclic expression reference to column {column_id!r}"
            raise ValueError(message)
        try:
            column = context.columns[column_id]
        except KeyError:
            message = f"Unknown semantic column {column_id!r}"
            raise KeyError(message) from None

        return self._evaluate_uncached_column(column, context)

    def _evaluate_uncached_column(
        self,
        column: Column,
        context: _RowContext,
    ) -> CellValue:
        context.resolving.add(column.id)
        try:
            value = normalize_cell_value(
                self._evaluate_source(column.source, context),
            )
        except (MissingFieldError, FieldAccessError) as error:
            enriched = _with_row_context(error, context, column.id)
            raise enriched from (error.__cause__ or error)
        except SourceEvaluationError:
            raise
        except Exception as error:
            raise _source_error(error, context, column.id) from error
        finally:
            context.resolving.discard(column.id)

        context.values[column.id] = value
        return value

    @singledispatchmethod
    def _evaluate_source(self, source: object, _context: _RowContext) -> object:
        message = f"Unsupported column source: {type(source).__name__}"
        raise TypeError(message)

    @_evaluate_source.register
    def _field_source(self, source: FieldRef, context: _RowContext) -> object:
        return context.data_source.get_value(context.row, source.name)

    @_evaluate_source.register
    def _path_source(self, source: PathRef, context: _RowContext) -> object:
        first, *remaining = source.segments
        value = context.data_source.get_value(context.row, first)
        for segment in remaining:
            value = self._path_accessor(value, segment)
        return value

    @_evaluate_source.register
    def _callable_source(
        self,
        source: CallableSource,
        context: _RowContext,
    ) -> object:
        return source.function(context.row)

    @_evaluate_source.register
    def _expression_source(
        self,
        source: Expression,
        context: _RowContext,
    ) -> object:
        return self._evaluate_expression(source, context)

    @singledispatchmethod
    def _evaluate_expression(
        self,
        expression: object,
        _context: _RowContext,
    ) -> object:
        message = f"Unsupported expression: {type(expression).__name__}"
        raise TypeError(message)

    @_evaluate_expression.register
    def _field_expression(
        self,
        expression: FieldRef,
        context: _RowContext,
    ) -> object:
        return self._evaluate_column(expression.name, context)

    @_evaluate_expression.register
    def _literal_expression(
        self,
        expression: Literal,
        _context: _RowContext,
    ) -> object:
        return expression.value

    @_evaluate_expression.register
    def _binary_expression(
        self,
        expression: BinaryExpression,
        context: _RowContext,
    ) -> object:
        left = self._evaluate_expression(expression.left, context)
        right = self._evaluate_expression(expression.right, context)
        return _BINARY_OPERATIONS[expression.operator](left, right)


def _with_row_context(
    error: MissingFieldError | FieldAccessError,
    context: _RowContext,
    column_id: str,
) -> MissingFieldError | FieldAccessError:
    if error.row_index is not None:
        return error
    error_type = type(error)
    return error_type(
        field=error.field,
        row_type=error.row_type,
        row_index=context.row_index,
        path=_column_path(context.row_index, column_id),
        context=error.context,
    )


def _iter_source_rows(
    data_source: DataSource[Any],
) -> Iterator[tuple[int, object]]:
    iterator = _source_iterator(data_source)
    row_index = 0
    while True:
        row = _next_source_row(iterator, data_source, row_index)
        if row is _SOURCE_END:
            return
        yield row_index, row
        row_index += 1


def _source_iterator(data_source: DataSource[Any]) -> Iterator[Any]:
    try:
        return iter(data_source.iter_rows())
    except FormataError:
        raise
    except Exception as error:
        raise _iteration_error(data_source, 0, error) from error


def _next_source_row(
    iterator: Iterator[Any],
    data_source: DataSource[Any],
    row_index: int,
) -> object:
    try:
        return next(iterator)
    except StopIteration:
        return _SOURCE_END
    except FormataError:
        raise
    except Exception as error:
        raise _iteration_error(data_source, row_index, error) from error


def _iteration_error(
    data_source: DataSource[Any],
    row_index: int,
    error: Exception,
) -> DataSourceIterationError:
    return DataSourceIterationError(
        source_type=type(data_source).__name__,
        row_index=row_index,
        path=f"row[{row_index}]",
        context={"exception_type": type(error).__name__},
    )


def _source_error(
    error: Exception,
    context: _RowContext,
    column_id: str,
) -> SourceEvaluationError:
    return SourceEvaluationError(
        column=column_id,
        row_type=type(context.row).__name__,
        row_index=context.row_index,
        path=_column_path(context.row_index, column_id),
        context={"exception_type": type(error).__name__},
    )


def _column_path(row_index: int, column_id: str) -> str:
    return f'row[{row_index}].column["{column_id}"]'


__all__ = ("SemanticRow", "SemanticRowEvaluator")
