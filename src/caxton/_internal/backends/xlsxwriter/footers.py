"""Write table total rows with XlsxWriter formulas and formats."""

from __future__ import annotations

import xlsxwriter  # type: ignore[import-untyped]
from xlsxwriter.worksheet import Worksheet  # type: ignore[import-untyped]

from caxton._internal.backends._xlsx_values import validate_xlsx_text
from caxton._internal.backends.xlsxwriter.styles import footer_format, style_format
from caxton._internal.const import _AGGREGATES
from caxton.core.ir import SpreadsheetTableIR
from caxton.core.models import AggregateFunction


def write_footer(  # noqa: WPS211
    workbook: xlsxwriter.Workbook,
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    header_row: int,
    last_row: int,
    start_column: int,
) -> None:
    """Write an optional aggregate footer."""
    footer = table.footer
    if footer is None:
        return
    footer_row = last_row + 1
    cell_format = style_format(workbook, footer.style)
    worksheet.write_string(
        footer_row,
        start_column + footer.label_column_offset,
        validate_xlsx_text(footer.label, role="table footer label"),
        cell_format,
    )
    for item in footer.items:
        column = start_column + item.column_offset
        item_format = footer_format(
            workbook,
            footer.style,
            table.columns[item.column_offset],
        )
        if last_row == header_row:
            worksheet.write(footer_row, column, 0, item_format)
            continue
        formula = _aggregate_formula(
            item.function,
            first_row=header_row + 2,
            last_row=last_row + 1,
            column=column + 1,
        )
        worksheet.write_formula(footer_row, column, formula, item_format)


def _aggregate_formula(
    function: AggregateFunction,
    *,
    first_row: int,
    last_row: int,
    column: int,
) -> str:
    from caxton._internal.normalization import format_cell_address  # noqa: PLC0415

    start = format_cell_address(first_row, column)
    end = format_cell_address(last_row, column)
    return f"={_AGGREGATES[function]}({start}:{end})"


__all__ = ("write_footer",)
