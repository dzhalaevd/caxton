from __future__ import annotations

import dataclasses
import enum
from collections.abc import Callable, Sequence
from typing import Any, TypeAlias

from formata.core._values import freeze_value
from formata.core.errors import FormataTypeError, FormataValueError


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


class Expression:
    """Base for immutable, backend-independent row expressions."""

    __hash__ = object.__hash__

    def __bool__(self) -> bool:
        message = "Expressions cannot be used as boolean values"
        raise FormataTypeError(message)

    def _binary(self, operator: BinaryOperator, other: object) -> BinaryExpression:
        return BinaryExpression(operator, self, as_expression(other))

    def __add__(self, other: object) -> BinaryExpression:
        return self._binary(BinaryOperator.ADD, other)

    def __sub__(self, other: object) -> BinaryExpression:
        return self._binary(BinaryOperator.SUBTRACT, other)

    def __mul__(self, other: object) -> BinaryExpression:
        return self._binary(BinaryOperator.MULTIPLY, other)

    def __truediv__(self, other: object) -> BinaryExpression:
        return self._binary(BinaryOperator.DIVIDE, other)

    def __eq__(self, other: object) -> BinaryExpression:  # type: ignore[override]
        return self._binary(BinaryOperator.EQUAL, other)

    def __ne__(self, other: object) -> BinaryExpression:  # type: ignore[override]
        return self._binary(BinaryOperator.NOT_EQUAL, other)

    def __lt__(self, other: object) -> BinaryExpression:
        return self._binary(BinaryOperator.LESS_THAN, other)

    def __le__(self, other: object) -> BinaryExpression:
        return self._binary(BinaryOperator.LESS_THAN_OR_EQUAL, other)

    def __gt__(self, other: object) -> BinaryExpression:
        return self._binary(BinaryOperator.GREATER_THAN, other)

    def __ge__(self, other: object) -> BinaryExpression:
        return self._binary(BinaryOperator.GREATER_THAN_OR_EQUAL, other)


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class FieldRef(Expression):
    """Exact top-level row field reference."""

    name: str

    def __post_init__(self) -> None:
        _require_name(self.name, "Field name")


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class PathRef:
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
            _require_name(segment, "Path segment")


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class Literal(Expression):
    value: object

    def __post_init__(self) -> None:
        try:
            frozen = freeze_value(self.value, label="Literal")
        except TypeError as error:
            raise FormataTypeError(str(error)) from error
        except ValueError as error:
            raise FormataValueError(str(error)) from error
        object.__setattr__(self, "value", frozen)


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


ColumnSource: TypeAlias = FieldRef | PathRef | Expression | CallableSource
ColumnSourceInput: TypeAlias = str | ColumnSource | RowCallable | None


def field(name: str) -> FieldRef:
    return FieldRef(name)


def path(*segments: str) -> PathRef:
    return PathRef(tuple(segments))


def as_expression(value: object) -> Expression:
    if isinstance(value, Expression):
        return value
    return Literal(value)


def normalize_source(column_id: str, source: ColumnSourceInput) -> ColumnSource:
    if source is None:
        return field(column_id)
    if isinstance(source, str):
        return field(source)
    if isinstance(source, (Expression, PathRef, CallableSource)):
        return source
    if callable(source):
        return CallableSource(source)
    message = f"Unsupported column source: {type(source).__name__}"
    raise FormataTypeError(message)


def _require_name(value: str, label: str) -> None:
    if not isinstance(value, str):
        message = f"{label} must be a string"
        raise FormataTypeError(message)
    if not value.strip():
        message = f"{label} cannot be empty"
        raise FormataValueError(message)


__all__ = (
    "BinaryExpression",
    "BinaryOperator",
    "CallableSource",
    "ColumnSource",
    "ColumnSourceInput",
    "Expression",
    "FieldRef",
    "Literal",
    "PathRef",
    "RowCallable",
    "field",
    "path",
)
