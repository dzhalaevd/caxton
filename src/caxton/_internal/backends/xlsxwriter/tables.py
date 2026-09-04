"""Coordinate rendering of one Spreadsheet IR table with XlsxWriter."""

from __future__ import annotations

import xlsxwriter  # type: ignore[import-untyped]
from xlsxwriter.worksheet import Worksheet  # type: ignore[import-untyped]

from caxton._internal.backends._common import reserved_last_row
from caxton._internal.backends.xlsxwriter.conditional_formats import (
    add_conditional_formats,
)
from caxton._internal.backends.xlsxwriter.footers import write_footer
from caxton._internal.backends.xlsxwriter.native_tables import configure_table_range
from caxton._internal.backends.xlsxwriter.rows import (
    apply_auto_widths,
    apply_merges,
    write_headers,
    write_rows,
)
from caxton._internal.backends.xlsxwriter.styles import column_format, style_format
from caxton.core.ir import SpreadsheetTableIR


def render_table(
    workbook: xlsxwriter.Workbook,
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
) -> None:
    """Render one Spreadsheet IR table into a worksheet."""
    header_row = table.anchor.row - 1
    start_column = table.anchor.column - 1
    header_format = style_format(workbook, table.header_style)
    column_formats = tuple(column_format(workbook, column) for column in table.columns)

    write_headers(worksheet, table, header_row, start_column, header_format)
    last_row, widths, merge_values = write_rows(
        worksheet,
        table,
        header_row,
        start_column,
        column_formats,
    )
    body_last_row = reserved_last_row(table, header_row, last_row)
    apply_merges(worksheet, table, column_formats, merge_values)
    apply_auto_widths(worksheet, table, start_column, widths)
    write_footer(workbook, worksheet, table, header_row, body_last_row, start_column)
    add_conditional_formats(
        workbook,
        worksheet,
        table,
        header_row,
        last_row,
        start_column,
    )
    configure_table_range(
        worksheet,
        table,
        header_row,
        body_last_row,
        start_column,
        header_format,
    )


__all__ = ("render_table",)
