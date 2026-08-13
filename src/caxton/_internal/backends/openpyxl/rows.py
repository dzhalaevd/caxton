from __future__ import annotations

from collections.abc import Sequence

from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from caxton._internal.backends.openpyxl.styles import apply_style, style_cell
from caxton._internal.formulas import lower_excel_formula
from caxton.core.ir import SpreadsheetTableIR
from caxton.core.values import CellValue


def write_headers(
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    header_row: int,
    start_column: int,
) -> None:
    """Write table headers and explicit width hints."""
    for column in table.columns:
        cell = worksheet.cell(
            row=header_row,
            column=start_column + column.offset,
            value=column.title,
        )
        apply_style(cell, table.header_style)
        if column.width_hint is not None:
            letter = get_column_letter(start_column + column.offset)
            worksheet.column_dimensions[letter].width = column.width_hint


def write_rows(
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    header_row: int,
    start_column: int,
) -> tuple[int, tuple[int, ...]]:
    """Write data rows and collect their display widths.

    Returns:
        The last physical row and observed display widths.
    """
    last_row = header_row
    widths = [len(column.title) for column in table.columns]
    for row in table.rows:
        physical_row = header_row + row.index + 1
        last_row = physical_row
        _write_row(
            worksheet,
            table,
            row.values,
            physical_row,
            start_column,
            widths,
        )
    return last_row, tuple(widths)


def _write_row(  # noqa: WPS211
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    values: Sequence[CellValue],
    physical_row: int,
    start_column: int,
    widths: list[int],
) -> None:
    for column, value in zip(table.columns, values, strict=True):
        widths[column.offset] = max(widths[column.offset], _display_width(value))
        cell_value: CellValue = value
        if column.formula is not None:
            cell_value = lower_excel_formula(
                column.formula,
                current_row=physical_row,
            )
        cell = worksheet.cell(
            row=physical_row,
            column=start_column + column.offset,
            value=cell_value,
        )
        style_cell(cell, column)


def apply_merges(worksheet: Worksheet, table: SpreadsheetTableIR) -> None:
    """Materialize compiled cell merges."""
    for cell_range in table.merges:
        worksheet.merge_cells(
            start_row=cell_range.start.row,
            start_column=cell_range.start.column,
            end_row=cell_range.end.row,
            end_column=cell_range.end.column,
        )


def apply_auto_widths(
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    start_column: int,
    widths: tuple[int, ...],
) -> None:
    """Apply widths derived from rendered values."""
    for column in table.columns:
        if column.auto_width:
            letter = get_column_letter(start_column + column.offset)
            worksheet.column_dimensions[letter].width = min(
                80,
                max(1, widths[column.offset] + 2),
            )


def _display_width(value: object) -> int:
    return 0 if value is None else len(str(value))


__all__ = ("apply_auto_widths", "apply_merges", "write_headers", "write_rows")
