from __future__ import annotations

import dataclasses
import enum
from collections.abc import Callable, Sequence
from typing import Any, TypeAlias

from caxton.core._compat import StrEnum
from caxton.core._values import normalize_cell_value
from caxton.core.errors import CaxtonTypeError, CaxtonValueError

from ._operators import BinaryOperatorMixin
from ._validation import require_name


class _MissingAggregateDefault(enum.Enum):
    VALUE = enum.auto()


_MISSING_AGGREGATE_DEFAULT = _MissingAggregateDefault.VALUE


class BinaryOperator(StrEnum):
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

    def agg(
        self,
        function: AggregateCallable,
        *expressions: Expression,
        where: Expression | None = None,
        default: object = _MISSING_AGGREGATE_DEFAULT,
    ) -> AggregateExpr:
        """Aggregate this expression and any additional inputs in one scope.

        Returns:
            An immutable, backend-independent aggregation expression.
        """
        return AggregateExpr(
            function=function,
            expressions=(self, *expressions),
            where=where,
            default=default,
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
            raise CaxtonTypeError(message)
        object.__setattr__(self, "segments", tuple(self.segments))
        if not self.segments:
            message = "Path must contain at least one segment"
            raise CaxtonValueError(message)
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
            raise CaxtonTypeError(str(error)) from error
        object.__setattr__(self, "value", normalized)


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class BinaryExpression(Expression):
    operator: BinaryOperator
    left: Expression
    right: Expression


def contains_aggregate(expression: Expression) -> bool:
    """Return whether an expression tree contains aggregate intent."""
    if isinstance(expression, AggregateExpr):
        return True
    if isinstance(expression, BinaryExpression):
        return contains_aggregate(expression.left) or contains_aggregate(
            expression.right,
        )
    return False


AggregateCallable: TypeAlias = Callable[..., object]


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class AggregateExpr(Expression):
    """One result produced from expression sequences in an aggregate scope."""

    function: AggregateCallable
    expressions: Sequence[Expression]
    where: Expression | None = None
    default: object = _MISSING_AGGREGATE_DEFAULT

    def __post_init__(self) -> None:  # noqa: C901, WPS238
        if not callable(self.function):
            message = "Aggregate function must be callable"
            raise CaxtonTypeError(message)
        expressions = tuple(self.expressions)
        if not expressions:
            message = "Aggregate requires at least one input expression"
            raise CaxtonValueError(message)
        for expression in expressions:
            if not isinstance(expression, Expression) or contains_aggregate(expression):
                message = "Aggregate inputs must be non-aggregate expressions"
                raise CaxtonTypeError(message)
        if self.where is not None and (
            not isinstance(self.where, Expression) or contains_aggregate(self.where)
        ):
            message = "Aggregate filter must be a non-aggregate expression"
            raise CaxtonTypeError(message)
        if self.default is not _MISSING_AGGREGATE_DEFAULT:
            try:
                normalized = normalize_cell_value(self.default)
            except TypeError as error:
                raise CaxtonTypeError(str(error)) from error
            object.__setattr__(self, "default", normalized)
        object.__setattr__(self, "expressions", expressions)

    @property
    def has_default(self) -> bool:
        """Whether an explicit result was declared for an empty scope."""
        return self.default is not _MISSING_AGGREGATE_DEFAULT


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


def normalize_source(source: ColumnSourceInput) -> ColumnSource | None:
    """Normalize a declared column source into a model node.

    Returns:
        The normalized source node, or ``None`` when none was declared.

    Raises:
        CaxtonTypeError: If the source cannot be interpreted.
    """
    if source is None:
        return None
    if isinstance(source, str):
        return field(source)
    if isinstance(source, (Expression, CallableSource)):
        return source
    if callable(source):
        return CallableSource(source)
    message = f"Unsupported column source: {type(source).__name__}"
    raise CaxtonTypeError(message)


__all__ = (
    "AggregateCallable",
    "AggregateExpr",
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
    "contains_aggregate",
    "field",
    "path",
    "ref",
)
