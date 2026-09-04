from __future__ import annotations

import dataclasses
from typing import cast

from openpyxl.cell.cell import Cell
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from caxton._internal.backends._xlsx_formats import number_format
from caxton._internal.backends._xlsx_values import validate_xlsx_text
from caxton._internal.backends.openpyxl.rows import set_literal_cell
from caxton._internal.backends.openpyxl.styles import apply_style
from caxton._internal.const import _AGGREGATES
from caxton.core.ir import SpreadsheetTableIR


def write_footer(  # noqa: WPS211
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
    label = cast(
        "Cell",
        worksheet.cell(
            row=footer_row,
            column=start_column + footer.label_column_offset,
        ),
    )
    set_literal_cell(
        label,
        validate_xlsx_text(footer.label, role="table footer label"),
    )
    apply_style(label, footer.style)
    for item in footer.items:
        column = start_column + item.column_offset
        value: int | str = 0
        if last_row > header_row:
            letter = get_column_letter(column)
            function = _AGGREGATES[item.function]
            value = f"={function}({letter}{header_row + 1}:{letter}{last_row})"
        cell = worksheet.cell(row=footer_row, column=column, value=value)
        apply_style(cell, footer.style)
        effective = dataclasses.replace(
            table.columns[item.column_offset],
            display_format=(
                footer.style.display_format
                or table.columns[item.column_offset].display_format
            ),
        )
        cell.number_format = number_format(effective)


__all__ = ("write_footer",)
