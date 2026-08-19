from __future__ import annotations

import string

from caxton._internal.normalization import format_cell_address
from caxton.core.ir import (
    ResolvedCellReference,
    ResolvedFormula,
    ResolvedFormulaBinary,
    ResolvedFormulaLiteral,
    ResolvedRangeReference,
)
from caxton.core.models import FormulaOperator

from .const import _OPERATORS, _PRECEDENCE


def lower_excel_formula(formula: ResolvedFormula, *, current_row: int) -> str:
    """Lower resolved Spreadsheet IR to an Excel formula string.

    Returns:
        A formula beginning with ``=`` and containing resolved A1 references.
    """
    return f"={_lower(formula, current_row=current_row, parent_precedence=0)}"


def _lower(  # noqa: C901, WPS212
    formula: ResolvedFormula,
    *,
    current_row: int,
    parent_precedence: int,
) -> str:
    if isinstance(formula, ResolvedFormulaLiteral):
        return _literal(formula.value)
    if isinstance(formula, ResolvedCellReference):
        return _cell(formula, current_row=current_row)
    if isinstance(formula, ResolvedRangeReference):
        if formula.column_absolute or formula.row_absolute:
            return _physical_range(formula)
        return _structured_range(formula)
    if isinstance(formula, ResolvedFormulaBinary):
        if formula.operator in {FormulaOperator.AND, FormulaOperator.OR}:
            function = "AND" if formula.operator is FormulaOperator.AND else "OR"
            left = _lower(
                formula.left,
                current_row=current_row,
                parent_precedence=0,
            )
            right = _lower(
                formula.right,
                current_row=current_row,
                parent_precedence=0,
            )
            return f"{function}({left},{right})"
        precedence = _PRECEDENCE[formula.operator]
        expression = (
            _lower(
                formula.left,
                current_row=current_row,
                parent_precedence=precedence,
            )
            + _OPERATORS[formula.operator]
            + _lower(
                formula.right,
                current_row=current_row,
                parent_precedence=precedence + 1,
            )
        )
        return f"({expression})" if precedence < parent_precedence else expression
    message = f"Unsupported resolved formula node: {type(formula).__name__}"
    raise TypeError(message)


def _cell(reference: ResolvedCellReference, *, current_row: int) -> str:
    row = current_row if reference.row is None else reference.row
    address = _coordinate(
        row,
        reference.column,
        column_absolute=reference.column_absolute,
        row_absolute=reference.row_absolute,
    )
    return f"{_sheet_qualifier(reference.sheet_name)}{address}"


def _coordinate(
    row: int,
    column: int,
    *,
    column_absolute: bool,
    row_absolute: bool,
) -> str:
    address = format_cell_address(row, column)
    letters = address.rstrip(string.digits)
    digits = address[len(letters) :]
    if column_absolute:
        letters = f"${letters}"
    if row_absolute:
        digits = f"${digits}"
    return f"{letters}{digits}"


def _sheet_qualifier(sheet_name: str | None) -> str:
    if sheet_name is None:
        return ""
    return f"'{sheet_name.replace(chr(39), chr(39) * 2)}'!"


def _physical_range(reference: ResolvedRangeReference) -> str:
    start = _coordinate(
        reference.start.row,
        reference.start.column,
        column_absolute=reference.column_absolute,
        row_absolute=reference.row_absolute,
    )
    end = _coordinate(
        reference.end.row,
        reference.end.column,
        column_absolute=reference.column_absolute,
        row_absolute=reference.row_absolute,
    )
    return f"{_sheet_qualifier(reference.sheet_name)}{start}:{end}"


def _structured_range(reference: ResolvedRangeReference) -> str:
    table = reference.table_name.replace("]", "]]")
    column = reference.column_title.replace("]", "]]")
    return f"{table}[{column}]"


def _literal(value: object) -> str:
    if value is None:
        return '""'
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, str):
        return f'"{value.replace(chr(34), chr(34) * 2)}"'
    return str(value)


__all__ = ("lower_excel_formula",)
