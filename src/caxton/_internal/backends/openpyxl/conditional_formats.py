from __future__ import annotations

from openpyxl.formatting.rule import Rule
from openpyxl.styles.differential import (
    DifferentialStyle,
)
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from caxton._internal.backends.openpyxl.styles import native_style
from caxton._internal.formulas import lower_excel_formula
from caxton.core.ir import SpreadsheetTableIR


def add_conditional_formats(  # noqa: WPS211
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    header_row: int,
    last_row: int,
    start_column: int,
) -> None:
    """Materialize compiled conditional-format rules."""
    if last_row == header_row:
        return
    start = f"{get_column_letter(start_column)}{header_row + 1}"
    end = f"{get_column_letter(start_column + len(table.columns) - 1)}{last_row}"
    for item in table.rules:
        font, fill, border, _ = native_style(item.style)
        rule = Rule(
            type="expression",
            dxf=DifferentialStyle(font=font, fill=fill, border=border),
            formula=[
                lower_excel_formula(
                    item.condition,
                    current_row=header_row + 1,
                ).removeprefix("="),
            ],
        )
        worksheet.conditional_formatting.add(f"{start}:{end}", rule)


__all__ = ("add_conditional_formats",)
