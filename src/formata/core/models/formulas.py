from __future__ import annotations

import dataclasses
import decimal
import enum
import math
from typing import Self, TypeAlias, overload

from formata.core._values import normalize_cell_value
from formata.core.errors import FormataTypeError, FormataValueError

from ._operators import BinaryOperatorMixin
from ._validation import require_name, require_optional_name
from .expressions import Expression


class FormulaOperator(enum.StrEnum):
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


class Formula(BinaryOperatorMixin["FormulaBinary"]):
    """Base for immutable formulas evaluated by the spreadsheet artifact."""

    __slots__ = ()

    node_label = "Formulas"

    def _binary(self, operator_name: str, other: object) -> FormulaBinary:
        return FormulaBinary(
            FormulaOperator[operator_name],
            self,
            coerce_formula(other),
        )

    def _reverse(self, operator_name: str, other: object) -> FormulaBinary:
        return FormulaBinary(
            FormulaOperator[operator_name],
            coerce_formula(other),
            self,
        )


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class FormulaLiteral(Formula):
    value: FormulaScalar

    def __post_init__(self) -> None:
        if isinstance(self.value, (float, decimal.Decimal)) and not math.isfinite(
            self.value,
        ):
            message = "Formula numeric literals must be finite"
            raise FormataValueError(message)
        try:
            normalized = normalize_cell_value(self.value)
        except TypeError as error:
            raise FormataTypeError(str(error)) from error
        object.__setattr__(self, "value", normalized)


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class FormulaBinary(Formula):
    operator: FormulaOperator
    left: Formula
    right: Formula


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class CellReference(Formula):
    """Semantic cell reference; ``row_index=None`` means the current data row."""

    column_id: str
    table_name: str | None = None
    sheet_name: str | None = None
    row_index: int | None = None
    column_absolute: bool = False
    row_absolute: bool = False

    def __post_init__(self) -> None:
        require_name(self.column_id, "Column id")
        require_optional_name(self.table_name, "Table name")
        require_optional_name(self.sheet_name, "Worksheet name")
        if self.sheet_name is not None and self.table_name is None:
            message = "A sheet-qualified cell reference requires a table"
            raise FormataValueError(message)
        if self.row_index is not None and (
            isinstance(self.row_index, bool)
            or not isinstance(self.row_index, int)
            or self.row_index < 0
        ):
            message = "Semantic row index must be a non-negative integer"
            raise FormataValueError(message)

    def absolute(self, *, column: bool = True, row: bool = True) -> Self:
        """Return a reference whose axes are absolute exactly as requested.

        Returns:
            A reference with ``column_absolute``/``row_absolute`` set to the
            supplied flags, so ``absolute(column=False)`` makes the column
            relative instead of silently doing nothing.
        """
        return dataclasses.replace(
            self,
            column_absolute=column,
            row_absolute=row,
        )

    def relative(self, *, column: bool = True, row: bool = True) -> Self:
        """Return a reference whose axes are relative exactly as requested.

        Returns:
            A reference with the requested axes made relative and the others
            made absolute.
        """
        return self.absolute(column=not column, row=not row)


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class RangeReference(Formula):
    """Semantic data range for one named table column."""

    table_name: str
    column_id: str
    sheet_name: str | None = None
    column_absolute: bool = False
    row_absolute: bool = False

    def __post_init__(self) -> None:
        require_name(self.table_name, "Table name")
        require_name(self.column_id, "Column id")
        require_optional_name(self.sheet_name, "Worksheet name")

    def cell(self, row_index: int) -> CellReference:
        return CellReference(
            column_id=self.column_id,
            table_name=self.table_name,
            sheet_name=self.sheet_name,
            row_index=row_index,
            column_absolute=self.column_absolute,
            row_absolute=self.row_absolute,
        )

    def absolute(self, *, column: bool = True, row: bool = True) -> Self:
        """Return a range whose axes are absolute exactly as requested.

        Returns:
            A range with ``column_absolute``/``row_absolute`` set to the
            supplied flags.
        """
        return dataclasses.replace(
            self,
            column_absolute=column,
            row_absolute=row,
        )

    def relative(self, *, column: bool = True, row: bool = True) -> Self:
        """Return a range whose axes are relative exactly as requested.

        Returns:
            A range with the requested axes made relative and the others made
            absolute.
        """
        return self.absolute(column=not column, row=not row)


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class TableReference:
    name: str
    sheet_name: str | None = None

    def __post_init__(self) -> None:
        require_name(self.name, "Table name")
        require_optional_name(self.sheet_name, "Worksheet name")

    def column(self, column_id: str) -> RangeReference:
        return RangeReference(
            table_name=self.name,
            column_id=column_id,
            sheet_name=self.sheet_name,
        )


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class SheetReference:
    name: str

    def __post_init__(self) -> None:
        require_name(self.name, "Worksheet name")

    def table(self, table_name: str) -> TableReference:
        return TableReference(table_name, sheet_name=self.name)


FormulaScalar: TypeAlias = bool | decimal.Decimal | float | int | str | None
FormulaInput: TypeAlias = Formula | FormulaScalar


def col(column_id: str) -> CellReference:
    return CellReference(column_id)


def table_ref(table_name: str) -> TableReference:
    return TableReference(table_name)


def sheet_ref(sheet_name: str) -> SheetReference:
    return SheetReference(sheet_name)


@overload
def absolute(
    reference: CellReference,
    *,
    column: bool = True,
    row: bool = True,
) -> CellReference: ...


@overload
def absolute(
    reference: RangeReference,
    *,
    column: bool = True,
    row: bool = True,
) -> RangeReference: ...


def absolute(
    reference: CellReference | RangeReference,
    *,
    column: bool = True,
    row: bool = True,
) -> CellReference | RangeReference:
    """Set the absolute axes of a cell or range reference.

    Returns:
        A reference whose axes match the supplied flags exactly.
    """
    return reference.absolute(column=column, row=row)


def as_formula(value: FormulaInput) -> Formula:
    """Normalize declared formula input into a formula node.

    Returns:
        The value itself when it is already a formula, a literal otherwise.
    """
    return coerce_formula(value)


def coerce_formula(value: object) -> Formula:
    """Normalize an operand that arrives without a static type.

    Python passes arbitrary objects to operator dunders, so this entry point
    keeps the runtime checks while ``as_formula`` stays precisely typed.

    Returns:
        The value itself when it is already a formula, a literal otherwise.

    Raises:
        FormataTypeError: If the value is a row expression or an unsupported
            literal type.
    """
    if isinstance(value, Formula):
        return value
    if isinstance(value, Expression):
        message = "Python row expressions cannot be used as Excel formulas; use col()"
        raise FormataTypeError(message)
    if value is None or isinstance(value, (bool, decimal.Decimal, float, int, str)):
        return FormulaLiteral(value)
    message = f"Unsupported formula literal: {type(value).__name__}"
    raise FormataTypeError(message)


__all__ = (
    "CellReference",
    "Formula",
    "FormulaBinary",
    "FormulaInput",
    "FormulaLiteral",
    "FormulaOperator",
    "FormulaScalar",
    "RangeReference",
    "SheetReference",
    "TableReference",
    "absolute",
    "as_formula",
    "coerce_formula",
    "col",
    "sheet_ref",
    "table_ref",
)
