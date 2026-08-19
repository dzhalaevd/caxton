from __future__ import annotations

from openpyxl.utils import get_column_letter
from openpyxl.worksheet.filters import AutoFilter
from openpyxl.worksheet.table import (
    Table,
    TableColumn,
    TableStyleInfo,
)
from openpyxl.worksheet.worksheet import Worksheet

from caxton.core.ir import SpreadsheetTableIR


def configure_table_range(
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    header_row: int,
    last_row: int,
    start_column: int,
) -> None:
    """Add a native table or plain autofilter to the rendered range."""
    if table.name is not None:
        _add_native_table(worksheet, table, header_row, last_row, start_column)
        return
    if table.autofilter and last_row > header_row:
        end_column = start_column + len(table.columns) - 1
        worksheet.auto_filter.ref = (
            f"{get_column_letter(start_column)}{header_row}:"
            f"{get_column_letter(end_column)}{last_row}"
        )


def _add_native_table(
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    header_row: int,
    last_row: int,
    start_column: int,
) -> None:
    end_column = start_column + len(table.columns) - 1
    reference = (
        f"{get_column_letter(start_column)}{header_row}:"
        f"{get_column_letter(end_column)}{last_row}"
    )
    native_table = Table(
        displayName=table.name,
        ref=reference,
        autoFilter=AutoFilter(ref=reference) if table.autofilter else None,
        tableColumns=tuple(
            TableColumn(id=index, name=column.title)
            for index, column in enumerate(table.columns, start=1)
        ),
    )
    native_table.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2",
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=True,
        showColumnStripes=False,
    )
    worksheet.add_table(native_table)


__all__ = ("configure_table_range",)
