from __future__ import annotations

import dataclasses
import decimal
import enum
import math
from typing import Self, TypeAlias, overload

from formata.core._values import normalize_cell_value
from formata.core.errors import FormataTypeError, FormataValueError

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


class Formula:
    """Base for immutable formulas evaluated by the spreadsheet artifact."""

    __hash__ = object.__hash__

    def __bool__(self) -> bool:
        message = "Formulas cannot be used as boolean values"
        raise FormataTypeError(message)

    def _binary(self, operator: FormulaOperator, other: object) -> FormulaBinary:
        return FormulaBinary(operator, self, as_formula(other))

    def _reverse(self, operator: FormulaOperator, other: object) -> FormulaBinary:
        return FormulaBinary(operator, as_formula(other), self)

    def __add__(self, other: object) -> FormulaBinary:
        return self._binary(FormulaOperator.ADD, other)

    def __radd__(self, other: object) -> FormulaBinary:
        return self._reverse(FormulaOperator.ADD, other)

    def __sub__(self, other: object) -> FormulaBinary:
        return self._binary(FormulaOperator.SUBTRACT, other)

    def __rsub__(self, other: object) -> FormulaBinary:
        return self._reverse(FormulaOperator.SUBTRACT, other)

    def __mul__(self, other: object) -> FormulaBinary:
        return self._binary(FormulaOperator.MULTIPLY, other)

    def __rmul__(self, other: object) -> FormulaBinary:
        return self._reverse(FormulaOperator.MULTIPLY, other)

    def __truediv__(self, other: object) -> FormulaBinary:
        return self._binary(FormulaOperator.DIVIDE, other)

    def __rtruediv__(self, other: object) -> FormulaBinary:
        return self._reverse(FormulaOperator.DIVIDE, other)

    def __eq__(self, other: object) -> FormulaBinary:  # type: ignore[override]
        return self._binary(FormulaOperator.EQUAL, other)

    def __ne__(self, other: object) -> FormulaBinary:  # type: ignore[override]
        return self._binary(FormulaOperator.NOT_EQUAL, other)

    def __lt__(self, other: object) -> FormulaBinary:
        return self._binary(FormulaOperator.LESS_THAN, other)

    def __le__(self, other: object) -> FormulaBinary:
        return self._binary(FormulaOperator.LESS_THAN_OR_EQUAL, other)

    def __gt__(self, other: object) -> FormulaBinary:
        return self._binary(FormulaOperator.GREATER_THAN, other)

    def __ge__(self, other: object) -> FormulaBinary:
        return self._binary(FormulaOperator.GREATER_THAN_OR_EQUAL, other)

    def __and__(self, other: object) -> FormulaBinary:
        return self._binary(FormulaOperator.AND, other)

    def __rand__(self, other: object) -> FormulaBinary:
        return self._reverse(FormulaOperator.AND, other)

    def __or__(self, other: object) -> FormulaBinary:
        return self._binary(FormulaOperator.OR, other)

    def __ror__(self, other: object) -> FormulaBinary:
        return self._reverse(FormulaOperator.OR, other)


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
        _require_name(self.column_id, "Column id")
        if self.table_name is not None:
            _require_name(self.table_name, "Table name")
        if self.sheet_name is not None:
            _require_name(self.sheet_name, "Worksheet name")
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
        return dataclasses.replace(
            self,
            column_absolute=column or self.column_absolute,
            row_absolute=row or self.row_absolute,
        )

    def relative(self, *, column: bool = True, row: bool = True) -> Self:
        return dataclasses.replace(
            self,
            column_absolute=False if column else self.column_absolute,
            row_absolute=False if row else self.row_absolute,
        )


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class RangeReference(Formula):
    """Semantic data range for one named table column."""

    table_name: str
    column_id: str
    sheet_name: str | None = None
    column_absolute: bool = False
    row_absolute: bool = False

    def __post_init__(self) -> None:
        _require_name(self.table_name, "Table name")
        _require_name(self.column_id, "Column id")
        if self.sheet_name is not None:
            _require_name(self.sheet_name, "Worksheet name")

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
        return dataclasses.replace(
            self,
            column_absolute=column or self.column_absolute,
            row_absolute=row or self.row_absolute,
        )

    def relative(self, *, column: bool = True, row: bool = True) -> Self:
        return dataclasses.replace(
            self,
            column_absolute=False if column else self.column_absolute,
            row_absolute=False if row else self.row_absolute,
        )


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class TableReference:
    name: str
    sheet_name: str | None = None

    def __post_init__(self) -> None:
        _require_name(self.name, "Table name")
        if self.sheet_name is not None:
            _require_name(self.sheet_name, "Worksheet name")

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
        _require_name(self.name, "Worksheet name")

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
    return reference.absolute(column=column, row=row)


def as_formula(value: FormulaInput | object) -> Formula:
    if isinstance(value, Formula):
        return value
    if isinstance(value, Expression):
        message = "Python row expressions cannot be used as Excel formulas; use col()"
        raise FormataTypeError(message)
    if value is None or isinstance(value, (bool, decimal.Decimal, float, int, str)):
        return FormulaLiteral(value)
    message = f"Unsupported formula literal: {type(value).__name__}"
    raise FormataTypeError(message)


def _require_name(value: str, label: str) -> None:
    if not isinstance(value, str):
        message = f"{label} must be a string"
        raise FormataTypeError(message)
    if not value.strip():
        message = f"{label} cannot be empty"
        raise FormataValueError(message)


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
    "col",
    "sheet_ref",
    "table_ref",
)
