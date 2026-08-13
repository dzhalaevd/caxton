from __future__ import annotations

import dataclasses
from collections.abc import Iterator, Mapping, Sequence
from functools import singledispatchmethod
from types import MappingProxyType
from typing import Any, cast

from caxton._internal.const import _BINARY_OPERATIONS, _NOT_EVALUATED, _SOURCE_END
from caxton._internal.data.accessors import DefaultRowAccessor
from caxton.core._values import normalize_cell_value
from caxton.core.errors import (
    CaxtonError,
    ColumnNotFoundError,
    CyclicColumnError,
    DataSourceIterationError,
    FieldAccessError,
    MissingFieldError,
    SourceEvaluationError,
)
from caxton.core.models import (
    BinaryExpression,
    CallableSource,
    Column,
    ColumnRef,
    Expression,
    FieldRef,
    LiteralExpression,
    PathRef,
)
from caxton.core.protocols import DataSource
from caxton.core.values import CellValue


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
        self._evaluate_source_dispatch = self._evaluate_source
        self._evaluate_expression_dispatch = self._evaluate_expression

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

    def iter_source_rows(
        self,
        data_source: DataSource[Any],
    ) -> Iterator[tuple[int, object]]:
        """Iterate raw rows with stable data-source error translation.

        Yields:
            Zero-based row indexes paired with original row objects.
        """
        yield from _iter_source_rows(data_source)

    def evaluate_expression(  # noqa: WPS211
        self,
        data_source: DataSource[Any],
        row: object,
        columns: Sequence[Column],
        expression: Expression,
        *,
        row_index: int,
        values: Mapping[str, CellValue] | None = None,
    ) -> object:
        """Evaluate one non-aggregate expression for an original row.

        Returns:
            The expression result without cell-value normalization.
        """
        context = _RowContext(
            data_source=data_source,
            row=row,
            row_index=row_index,
            columns={column.id: column for column in columns},
            values={} if values is None else dict(values),
        )
        return self._evaluate_expression_dispatch(expression, context)

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
        """Evaluate one semantic column, memoizing the result for the row.

        Returns:
            The evaluated cell value of the column.

        Raises:
            CyclicColumnError: If the column takes part in a reference cycle.
            ColumnNotFoundError: If no column carries the requested identity.
        """
        cached = context.values.get(column_id, _NOT_EVALUATED)
        if cached is not _NOT_EVALUATED:
            return cast("CellValue", cached)
        if column_id in context.resolving:
            raise CyclicColumnError(
                column=column_id,
                row_index=context.row_index,
                path=_column_path(context.row_index, column_id),
            )
        column = context.columns.get(column_id)
        if column is None:
            raise ColumnNotFoundError(
                column=column_id,
                path=_column_path(context.row_index, column_id),
            )
        return self._evaluate_uncached_column(column, context)

    def _evaluate_uncached_column(
        self,
        column: Column,
        context: _RowContext,
    ) -> CellValue:
        context.resolving.add(column.id)
        try:
            value = normalize_cell_value(
                self._evaluate_source_dispatch(column.source, context),
            )
        except (MissingFieldError, FieldAccessError) as error:
            enriched = _with_row_context(error, context, column.id)
            raise enriched from (error.__cause__ or error)
        except (ColumnNotFoundError, CyclicColumnError, SourceEvaluationError):
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
        return self._evaluate_expression_dispatch(source, context)

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
        return self._field_source(expression, context)

    @_evaluate_expression.register
    def _path_expression(
        self,
        expression: PathRef,
        context: _RowContext,
    ) -> object:
        return self._path_source(expression, context)

    @_evaluate_expression.register
    def _column_expression(
        self,
        expression: ColumnRef,
        context: _RowContext,
    ) -> object:
        return self._evaluate_column(expression.column_id, context)

    @_evaluate_expression.register
    def _literal_expression(
        self,
        expression: LiteralExpression,
        _context: _RowContext,
    ) -> object:
        return expression.value

    @_evaluate_expression.register
    def _binary_expression(
        self,
        expression: BinaryExpression,
        context: _RowContext,
    ) -> object:
        left = self._evaluate_expression_dispatch(expression.left, context)
        right = self._evaluate_expression_dispatch(expression.right, context)
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
    except CaxtonError:
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
    except CaxtonError:
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
