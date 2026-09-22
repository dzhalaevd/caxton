"""Configure native XlsxWriter table ranges and filters."""

from __future__ import annotations

from xlsxwriter.format import Format  # type: ignore[import-untyped]
from xlsxwriter.worksheet import Worksheet  # type: ignore[import-untyped]

from caxton.core.ir import SpreadsheetTableIR


def configure_table_range(  # noqa: WPS211
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    header_row: int,
    last_row: int,
    start_column: int,
    header_format: Format,
) -> None:
    """Add a native table or plain autofilter to the rendered range."""
    if table.name is not None:
        _add_native_table(
            worksheet,
            table,
            (header_row, last_row, start_column),
            header_format,
        )
        return
    if table.autofilter and last_row > header_row:
        worksheet.autofilter(
            header_row,
            start_column,
            last_row,
            start_column + len(table.columns) - 1,
        )


def _add_native_table(
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    area: tuple[int, int, int],
    header_format: Format,
) -> None:
    header_row, last_row, start_column = area
    result = worksheet.add_table(
        header_row,
        start_column,
        last_row,
        start_column + len(table.columns) - 1,
        {
            "name": table.name,
            "style": "Table Style Medium 2",
            "autofilter": table.autofilter,
            "columns": [
                {"header": column.title, "header_format": header_format}
                for column in table.columns
            ],
        },
    )
    if result != 0:
        message = f"XlsxWriter rejected native table {table.name!r}"
        raise ValueError(message)


__all__ = ("configure_table_range",)
