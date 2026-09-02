"""Write Spreadsheet IR headers, rows, merges, and widths with XlsxWriter."""

from __future__ import annotations

from collections.abc import Sequence

from xlsxwriter.format import Format  # type: ignore[import-untyped]
from xlsxwriter.worksheet import Worksheet  # type: ignore[import-untyped]

from caxton._internal.backends._common import display_width, fitted_width
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
        _require_write(
            worksheet.write(
                header_row,
                physical_column,
                column.title,
                header_format,
            ),
            operation="header",
            position=(header_row, physical_column),
        )
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
        widths[column.offset] = max(widths[column.offset], display_width(value))
        position = (physical_row, start_column + column.offset)
        if position in merge_starts:
            merge_values[position] = value
        if column.formula is not None:
            _require_write(
                worksheet.write_formula(
                    *position,
                    lower_excel_formula(
                        column.formula,
                        current_row=physical_row + 1,
                    ),
                    cell_format,
                ),
                operation="formula",
                position=position,
            )
            continue
        _write_cell(
            worksheet,
            position,
            value,
            is_link=isinstance(column.semantic_type, Link),
            cell_format=cell_format,
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
        value = values.get(start)
        cell_format = column_formats[column_offset]
        _require_write(
            worksheet.merge_range(
                start[0],
                start[1],
                cell_range.end.row - 1,
                cell_range.end.column - 1,
                value,
                cell_format,
            ),
            operation="merge",
            position=start,
        )
        if isinstance(table.columns[column_offset].semantic_type, Link):
            _write_cell(
                worksheet,
                start,
                value,
                is_link=True,
                cell_format=cell_format,
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
                fitted_width(widths[column.offset], column.auto_width),
            )


def _write_cell(
    worksheet: Worksheet,
    position: tuple[int, int],
    value: object,
    *,
    is_link: bool,
    cell_format: Format,
) -> None:
    row, column_index = position
    if is_link and value is not None:
        _require_write(
            worksheet.write_url(
                row,
                column_index,
                str(value),
                cell_format,
                str(value),
            ),
            operation="URL",
            position=position,
        )
        return
    _require_write(
        worksheet.write(row, column_index, value, cell_format),
        operation="cell",
        position=position,
    )


def _require_write(
    result: int,
    *,
    operation: str,
    position: tuple[int, int],
) -> None:
    if result == 0:
        return
    message = (
        f"XlsxWriter rejected {operation} at zero-based cell {position!r} "
        f"with status {result}"
    )
    raise RuntimeError(message)


__all__ = ("apply_auto_widths", "apply_merges", "write_headers", "write_rows")
