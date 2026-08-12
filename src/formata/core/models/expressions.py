from __future__ import annotations

import dataclasses
import enum
from collections.abc import Callable, Sequence
from typing import Any, TypeAlias

from formata.core._values import normalize_cell_value
from formata.core.errors import FormataTypeError, FormataValueError

from ._operators import BinaryOperatorMixin
from ._validation import require_name


class BinaryOperator(enum.StrEnum):
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    AND = "and"
    OR = "or"


class Expression(BinaryOperatorMixin["BinaryExpression"]):
    """Base for immutable, backend-independent row expressions."""

    __slots__ = ()

    node_label = "Expressions"

    def _binary(self, operator_name: str, other: object) -> BinaryExpression:
        return BinaryExpression(
            BinaryOperator[operator_name],
            self,
            as_expression(other),
        )

    def _reverse(self, operator_name: str, other: object) -> BinaryExpression:
        return BinaryExpression(
            BinaryOperator[operator_name],
            as_expression(other),
            self,
        )


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class FieldRef(Expression):
    """Exact top-level row field read through the data source."""

    name: str

    def __post_init__(self) -> None:
        require_name(self.name, "Field name")


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class ColumnRef(Expression):
    """Value of another semantic column of the same table."""

    column_id: str

    def __post_init__(self) -> None:
        require_name(self.column_id, "Column id")


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class PathRef(Expression):
    """Explicit nested row path."""

    segments: Sequence[str]

    def __post_init__(self) -> None:
        if isinstance(self.segments, str):
            message = "Path segments must be a sequence of strings"
            raise FormataTypeError(message)
        object.__setattr__(self, "segments", tuple(self.segments))
        if not self.segments:
            message = "Path must contain at least one segment"
            raise FormataValueError(message)
        for segment in self.segments:
            require_name(segment, "Path segment")


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class LiteralExpression(Expression):
    """Constant operand of a row expression."""

    value: object

    def __post_init__(self) -> None:
        try:
            normalized = normalize_cell_value(self.value)
        except TypeError as error:
            raise FormataTypeError(str(error)) from error
        object.__setattr__(self, "value", normalized)


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class BinaryExpression(Expression):
    operator: BinaryOperator
    left: Expression
    right: Expression


RowCallable: TypeAlias = Callable[[Any], object]


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class CallableSource:
    """Explicit source evaluated against the original row object."""

    function: RowCallable


ColumnSource: TypeAlias = Expression | CallableSource
ColumnSourceInput: TypeAlias = str | ColumnSource | RowCallable | None


def field(name: str) -> FieldRef:
    """Read one exact top-level field of the raw data row.

    Returns:
        A row field reference.
    """
    return FieldRef(name)


def ref(column_id: str) -> ColumnRef:
    """Read the evaluated value of another semantic column.

    Returns:
        A semantic column reference.
    """
    return ColumnRef(column_id)


def path(*segments: str) -> PathRef:
    """Traverse a nested row structure segment by segment.

    Returns:
        A nested row path reference.
    """
    return PathRef(tuple(segments))


def as_expression(value: object) -> Expression:
    """Wrap a plain operand into an expression node.

    Returns:
        The value itself when it is already an expression, a literal otherwise.
    """
    if isinstance(value, Expression):
        return value
    return LiteralExpression(value)


def normalize_source(column_id: str, source: ColumnSourceInput) -> ColumnSource:
    """Normalize a declared column source into a model node.

    Returns:
        The column source node, defaulting to a field named after the column.

    Raises:
        FormataTypeError: If the source cannot be interpreted.
    """
    if source is None:
        return field(column_id)
    if isinstance(source, str):
        return field(source)
    if isinstance(source, (Expression, CallableSource)):
        return source
    if callable(source):
        return CallableSource(source)
    message = f"Unsupported column source: {type(source).__name__}"
    raise FormataTypeError(message)


__all__ = (
    "BinaryExpression",
    "BinaryOperator",
    "CallableSource",
    "ColumnRef",
    "ColumnSource",
    "ColumnSourceInput",
    "Expression",
    "FieldRef",
    "LiteralExpression",
    "PathRef",
    "RowCallable",
    "field",
    "path",
    "ref",
)
