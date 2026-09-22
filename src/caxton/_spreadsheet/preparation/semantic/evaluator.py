from __future__ import annotations

import dataclasses
import operator
from collections.abc import Callable, Iterator, Mapping, Sequence
from types import MappingProxyType
from typing import Any, Generic, TypeVar, cast

from caxton.core._values import normalize_cell_value
from caxton.core.accessors import DefaultRowAccessor
from caxton.core.errors import (
    CaxtonError,
    ColumnNotFoundError,
    CyclicColumnError,
    DataSourceIterationError,
    FieldAccessError,
    InvalidOperationError,
    MissingFieldError,
    SourceEvaluationError,
)
from caxton.core.models import (
    AggregateExpr,
    BinaryExpression,
    BinaryOperator,
    CallableSource,
    Column,
    ColumnRef,
    ColumnSource,
    Expression,
    FieldRef,
    LiteralExpression,
    PathRef,
    TransformExpression,
)
from caxton.core.protocols import DataSource
from caxton.core.values import CellValue

RowT = TypeVar("RowT")
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
    BinaryOperator.AND: lambda left, right: left and right,
    BinaryOperator.OR: lambda left, right: left or right,
}
_NOT_EVALUATED = object()


class _SourceEnd:
    """Marker returned only when source iteration is exhausted."""


_SOURCE_END = _SourceEnd()


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
class _RowContext(Generic[RowT]):
    data_source: DataSource[RowT]
    row: RowT
    row_index: int
    columns: Mapping[str, Column]
    values: Mapping[str, CellValue] = dataclasses.field(default_factory=dict)
    evaluated: dict[str, CellValue] = dataclasses.field(default_factory=dict)
    resolving: set[str] = dataclasses.field(default_factory=set)


ExpressionHandler = Callable[[Expression, _RowContext[Any]], object]


class SemanticRowEvaluator:
    """Evaluate every column source consistently before family lowering."""

    def __init__(self) -> None:
        self._path_accessor = DefaultRowAccessor()
        self._expression_handlers: Mapping[type[Expression], ExpressionHandler] = {
            FieldRef: cast("ExpressionHandler", self._field_expression),
            PathRef: cast("ExpressionHandler", self._path_expression),
            ColumnRef: cast("ExpressionHandler", self._column_expression),
            LiteralExpression: cast("ExpressionHandler", self._literal_expression),
            TransformExpression: cast(
                "ExpressionHandler",
                self._transform_expression,
            ),
            BinaryExpression: cast("ExpressionHandler", self._binary_expression),
            AggregateExpr: cast("ExpressionHandler", self._aggregate_expression),
        }

    def iter_rows(
        self,
        data_source: DataSource[RowT],
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
        data_source: DataSource[RowT],
    ) -> Iterator[tuple[int, RowT]]:
        """Iterate raw rows with stable data-source error translation.

        Yields:
            Zero-based row indexes paired with original row objects.
        """
        yield from _iter_source_rows(data_source)

    def evaluate_expression(  # noqa: WPS211
        self,
        data_source: DataSource[RowT],
        row: RowT,
        columns: Sequence[Column] | Mapping[str, Column],
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
            columns=_column_catalog(columns),
            values={} if values is None else values,
        )
        return self._evaluate_expression(expression, context)

    def evaluate_expressions(  # noqa: WPS211
        self,
        data_source: DataSource[RowT],
        row: RowT,
        columns: Sequence[Column] | Mapping[str, Column],
        expressions: Sequence[Expression],
        *,
        row_index: int,
        values: Mapping[str, CellValue] | None = None,
    ) -> tuple[object, ...]:
        """Evaluate several expressions in one reusable row context.

        Returns:
            Results in declaration order.
        """
        context = _RowContext(
            data_source=data_source,
            row=row,
            row_index=row_index,
            columns=_column_catalog(columns),
            values={} if values is None else values,
        )
        return tuple(
            self._evaluate_expression(expression, context) for expression in expressions
        )

    def evaluate_row(
        self,
        data_source: DataSource[RowT],
        row: RowT,
        columns: Sequence[Column],
        *,
        row_index: int,
        column_catalog: Mapping[str, Column] | None = None,
    ) -> SemanticRow:
        """Evaluate one raw row against a semantic column schema.

        Returns:
            An immutable row keyed by semantic column identity.
        """
        context = _RowContext(
            data_source=data_source,
            row=row,
            row_index=row_index,
            columns=(
                _column_catalog(columns) if column_catalog is None else column_catalog
            ),
        )
        ordered_values = {
            column.id: self._evaluate_column(column.id, context) for column in columns
        }
        return SemanticRow(index=row_index, values=ordered_values)

    def _evaluate_column(self, column_id: str, context: _RowContext[RowT]) -> CellValue:
        """Evaluate one semantic column, memoizing the result for the row.

        Returns:
            The evaluated cell value of the column.

        Raises:
            CyclicColumnError: If the column takes part in a reference cycle.
            ColumnNotFoundError: If no column carries the requested identity.
        """
        cached = context.evaluated.get(column_id, _NOT_EVALUATED)
        if cached is _NOT_EVALUATED:
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
        context: _RowContext[RowT],
    ) -> CellValue:
        context.resolving.add(column.id)
        try:
            value = normalize_cell_value(
                self._evaluate_source(column.source, context),
            )
        except (MissingFieldError, FieldAccessError) as error:
            enriched = _with_row_context(error, context, column.id)
            raise enriched from (error.__cause__ or error)
        except CaxtonError:
            raise
        except Exception as error:
            raise _source_error(error, context, column.id) from error
        finally:
            context.resolving.discard(column.id)

        context.evaluated[column.id] = value
        return value

    def _evaluate_source(
        self, source: ColumnSource | None, context: _RowContext[RowT]
    ) -> object:
        if isinstance(source, FieldRef):
            return self._field_source(source, context)
        if isinstance(source, PathRef):
            return self._path_source(source, context)
        if isinstance(source, CallableSource):
            return self._callable_source(source, context)
        if isinstance(source, Expression):
            return self._evaluate_expression(source, context)
        message = f"Unsupported column source: {type(source).__name__}"
        raise TypeError(message)

    def _field_source(self, source: FieldRef, context: _RowContext[RowT]) -> object:
        return context.data_source.get_value(context.row, source.name)

    def _path_source(self, source: PathRef, context: _RowContext[RowT]) -> object:
        first, *remaining = source.segments
        value = context.data_source.get_value(context.row, first)
        for segment in remaining:
            value = self._path_accessor(value, segment)
        return value

    def _callable_source(
        self,
        source: CallableSource,
        context: _RowContext[RowT],
    ) -> object:
        return source.function(context.row)

    def _evaluate_expression(
        self,
        expression: Expression,
        context: _RowContext[RowT],
    ) -> object:
        handler = self._expression_handlers.get(type(expression))
        if handler is None:
            message = f"Unsupported expression: {type(expression).__name__}"
            raise TypeError(message)
        return handler(expression, context)

    def _aggregate_expression(
        self,
        _expression: AggregateExpr,
        context: _RowContext[RowT],
    ) -> object:
        message = "Aggregate expressions cannot be evaluated in row scope"
        raise InvalidOperationError(
            message,
            path=f"row[{context.row_index}].expression",
        )

    def _field_expression(
        self,
        expression: FieldRef,
        context: _RowContext[RowT],
    ) -> object:
        return self._field_source(expression, context)

    def _path_expression(
        self,
        expression: PathRef,
        context: _RowContext[RowT],
    ) -> object:
        return self._path_source(expression, context)

    def _column_expression(
        self,
        expression: ColumnRef,
        context: _RowContext[RowT],
    ) -> object:
        return self._evaluate_column(expression.column_id, context)

    def _literal_expression(
        self,
        expression: LiteralExpression,
        _context: _RowContext[RowT],
    ) -> object:
        return expression.value

    def _binary_expression(
        self,
        expression: BinaryExpression,
        context: _RowContext[RowT],
    ) -> object:
        left = self._evaluate_expression(expression.left, context)
        right = self._evaluate_expression(expression.right, context)
        return _BINARY_OPERATIONS[expression.operator](left, right)

    def _transform_expression(
        self,
        expression: TransformExpression,
        context: _RowContext[RowT],
    ) -> object:
        value = self._evaluate_expression(expression.expression, context)
        return expression.function(value)


def _column_catalog(
    columns: Sequence[Column] | Mapping[str, Column],
) -> Mapping[str, Column]:
    if isinstance(columns, Mapping):
        return columns
    return {column.id: column for column in columns}


def _with_row_context(
    error: MissingFieldError | FieldAccessError,
    context: _RowContext[RowT],
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
    data_source: DataSource[RowT],
) -> Iterator[tuple[int, RowT]]:
    iterator = _source_iterator(data_source)
    row_index = 0
    while True:
        row = _next_source_row(iterator, data_source, row_index)
        if row is _SOURCE_END:
            return
        yield row_index, cast("RowT", row)
        row_index += 1


def _source_iterator(data_source: DataSource[RowT]) -> Iterator[RowT]:
    try:
        return iter(data_source.iter_rows())
    except CaxtonError:
        raise
    except Exception as error:
        raise _iteration_error(data_source, 0, error) from error


def _next_source_row(
    iterator: Iterator[RowT],
    data_source: DataSource[RowT],
    row_index: int,
) -> RowT | _SourceEnd:
    try:
        return next(iterator)
    except StopIteration:
        return _SOURCE_END
    except CaxtonError:
        raise
    except Exception as error:
        raise _iteration_error(data_source, row_index, error) from error


def _iteration_error(
    data_source: DataSource[RowT],
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
    context: _RowContext[RowT],
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
