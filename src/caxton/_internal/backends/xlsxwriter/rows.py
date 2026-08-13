"""Write Spreadsheet IR headers, rows, merges, and widths with XlsxWriter."""

from __future__ import annotations

from collections.abc import Sequence

from xlsxwriter.format import Format  # type: ignore[import-untyped]
from xlsxwriter.worksheet import Worksheet  # type: ignore[import-untyped]

from caxton._internal.formulas import lower_excel_formula
from caxton.core.ir import SpreadsheetTableIR
from caxton.core.types import Link

WrittenRows = tuple[int, tuple[int, ...], dict[tuple[int, int], object]]


def write_headers(
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    header_row: int,
    start_column: int,
    header_format: Format,
) -> None:
    """Write table headers and explicit width hints."""
    for column in table.columns:
        physical_column = start_column + column.offset
        worksheet.write(header_row, physical_column, column.title, header_format)
        if column.width_hint is not None:
            worksheet.set_column_pixels(
                physical_column,
                physical_column,
                round(column.width_hint * 7),
            )


def write_rows(
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    header_row: int,
    start_column: int,
    column_formats: tuple[Format, ...],
) -> WrittenRows:
    """Write data rows and collect width and merge metadata.

    Returns:
        The last row, observed widths, and values required by merged cells.
    """
    last_row = header_row
    widths = [len(column.title) for column in table.columns]
    merge_starts = {
        (item.start.row - 1, item.start.column - 1) for item in table.merges
    }
    merge_values: dict[tuple[int, int], object] = {}
    for row in table.rows:
        physical_row = header_row + row.index + 1
        last_row = physical_row
        _write_row(
            worksheet,
            table,
            row.values,
            physical_row,
            start_column,
            column_formats,
            widths,
            merge_starts,
            merge_values,
        )
    return last_row, tuple(widths), merge_values


def _write_row(  # noqa: WPS211
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    values: Sequence[object],
    physical_row: int,
    start_column: int,
    column_formats: tuple[Format, ...],
    widths: list[int],
    merge_starts: set[tuple[int, int]],
    merge_values: dict[tuple[int, int], object],
) -> None:
    for column, value, cell_format in zip(
        table.columns,
        values,
        column_formats,
        strict=True,
    ):
        widths[column.offset] = max(widths[column.offset], _display_width(value))
        position = (physical_row, start_column + column.offset)
        if position in merge_starts:
            merge_values[position] = value
        if column.formula is not None:
            worksheet.write_formula(
                *position,
                lower_excel_formula(column.formula, current_row=physical_row + 1),
                cell_format,
            )
            continue
        _write_cell(
            worksheet,
            position,
            value,
            isinstance(column.semantic_type, Link),
            cell_format,
        )


def apply_merges(
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    column_formats: tuple[Format, ...],
    values: dict[tuple[int, int], object],
) -> None:
    """Materialize compiled cell merges."""
    for cell_range in table.merges:
        start = (cell_range.start.row - 1, cell_range.start.column - 1)
        column_offset = cell_range.start.column - table.anchor.column
        worksheet.merge_range(
            start[0],
            start[1],
            cell_range.end.row - 1,
            cell_range.end.column - 1,
            values.get(start),
            column_formats[column_offset],
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
            physical_column = start_column + column.offset
            worksheet.set_column(
                physical_column,
                physical_column,
                min(80, max(1, widths[column.offset] + 2)),
            )


def _display_width(value: object) -> int:
    return 0 if value is None else len(str(value))


def _write_cell(
    worksheet: Worksheet,
    position: tuple[int, int],
    value: object,
    is_link: bool,
    cell_format: Format,
) -> None:
    row, column_index = position
    if is_link and value is not None:
        worksheet.write_url(row, column_index, str(value), cell_format, str(value))
        return
    worksheet.write(row, column_index, value, cell_format)


__all__ = ("apply_auto_widths", "apply_merges", "write_headers", "write_rows")
