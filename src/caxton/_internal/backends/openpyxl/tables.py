from __future__ import annotations

from openpyxl.worksheet.worksheet import Worksheet

from caxton._internal.backends.openpyxl.conditional_formats import (
    add_conditional_formats,
)
from caxton._internal.backends.openpyxl.footers import write_footer
from caxton._internal.backends.openpyxl.native_tables import configure_table_range
from caxton._internal.backends.openpyxl.rows import (
    apply_auto_widths,
    apply_merges,
    write_headers,
    write_rows,
)
from caxton.core.ir import SpreadsheetTableIR


def render_table(worksheet: Worksheet, table: SpreadsheetTableIR) -> None:
    """Render one Spreadsheet IR table into a worksheet."""
    header_row = table.anchor.row
    start_column = table.anchor.column
    write_headers(worksheet, table, header_row, start_column)
    last_row, widths = write_rows(worksheet, table, header_row, start_column)
    apply_merges(worksheet, table)
    apply_auto_widths(worksheet, table, start_column, widths)
    write_footer(worksheet, table, header_row, last_row, start_column)
    add_conditional_formats(worksheet, table, header_row, last_row, start_column)
    configure_table_range(worksheet, table, header_row, last_row, start_column)


__all__ = ("render_table",)
