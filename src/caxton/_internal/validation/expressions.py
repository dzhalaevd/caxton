"""Validate Python column references and dependency cycles."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator, Sequence
from functools import singledispatch

from caxton.core.errors import (
    ColumnNotFoundError,
    DuplicateColumnError,
    Notification,
)
from caxton.core.models import (
    AggregateExpr,
    BinaryExpression,
    Column,
    ColumnRef,
    Expression,
)


@dataclasses.dataclass(frozen=True, slots=True)
class _ReferenceScope:
    identifiers: set[str]
    formula_identifiers: set[str]
    aggregate_identifiers: set[str]
    inside_aggregate: bool


def validate_columns(
    columns: Sequence[Column],
    table_path: str,
    notification: Notification,
) -> None:
    if not columns:
        notification.add(
            "Table must contain at least one column",
            path=table_path,
            code="missing_column",
        )
        return
    identifiers = {column.id for column in columns}
    formula_identifiers = {
        column.id for column in columns if column.excel_formula is not None
    }
    aggregate_identifiers = {
        column.id for column in columns if isinstance(column.source, AggregateExpr)
    }
    seen: set[str] = set()
    dependencies: dict[str, tuple[str, ...]] = {}
    for column in columns:
        column_path = f'{table_path}.column["{column.id}"]'
        if column.id in seen:
            notification.add(
                DuplicateColumnError(column=column.id, path=column_path),
            )
        seen.add(column.id)
        references = tuple(_column_references(column))
        dependencies[column.id] = tuple(
            reference for reference in references if reference in identifiers
        )
        reference_scope = _ReferenceScope(
            identifiers=identifiers,
            formula_identifiers=formula_identifiers,
            aggregate_identifiers=aggregate_identifiers,
            inside_aggregate=isinstance(column.source, AggregateExpr),
        )
        for reference in references:
            _validate_python_reference(
                reference,
                reference_scope,
                path=f"{column_path}.source",
                notification=notification,
            )
    _validate_cycles(dependencies, table_path, notification)


@singledispatch
def expression_references(_expression: Expression) -> Iterator[str]:
    return iter(())


@expression_references.register
def _column_reference(expression: ColumnRef) -> Iterator[str]:
    yield expression.column_id


@expression_references.register
def _binary_references(expression: BinaryExpression) -> Iterator[str]:
    yield from expression_references(expression.left)
    yield from expression_references(expression.right)


@expression_references.register
def _aggregate_references(expression: AggregateExpr) -> Iterator[str]:
    for item in expression.expressions:
        yield from expression_references(item)
    if expression.where is not None:
        yield from expression_references(expression.where)


def _column_references(column: Column) -> Iterator[str]:
    if isinstance(column.source, Expression):
        yield from expression_references(column.source)


def _validate_python_reference(
    reference: str,
    scope: _ReferenceScope,
    *,
    path: str,
    notification: Notification,
) -> None:
    if reference not in scope.identifiers:
        notification.add(ColumnNotFoundError(column=reference, path=path))
        return
    if reference in scope.formula_identifiers:
        notification.add(
            "Python expressions cannot read formula-backed columns",
            path=path,
            code="formula_in_python_expression",
            context={"column": reference},
        )
        return
    if scope.inside_aggregate and reference in scope.aggregate_identifiers:
        notification.add(
            "Aggregate expressions cannot read aggregate-backed columns",
            path=path,
            code="aggregate_in_aggregate_expression",
            context={"column": reference},
        )


def _validate_cycles(
    dependencies: dict[str, tuple[str, ...]],
    table_path: str,
    notification: Notification,
) -> None:
    state = _CycleState(
        dependencies=dependencies,
        table_path=table_path,
        notification=notification,
    )
    for column_id in dependencies:
        _visit_column(column_id, state)


@dataclasses.dataclass(slots=True)
class _CycleState:
    dependencies: dict[str, tuple[str, ...]]
    table_path: str
    notification: Notification
    completed: set[str] = dataclasses.field(default_factory=set)
    active: set[str] = dataclasses.field(default_factory=set)


def _visit_column(
    column_id: str,
    state: _CycleState,
) -> None:
    if column_id in state.completed:
        return
    if column_id in state.active:
        state.notification.add(
            f"Cyclic column reference involving {column_id!r}",
            path=f'{state.table_path}.column["{column_id}"].source',
            code="cyclic_column_reference",
            context={"column": column_id},
        )
        return
    state.active.add(column_id)
    for dependency in state.dependencies[column_id]:
        _visit_column(dependency, state)
    state.active.discard(column_id)
    state.completed.add(column_id)


__all__ = ("expression_references", "validate_columns")
