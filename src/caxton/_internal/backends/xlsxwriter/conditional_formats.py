from __future__ import annotations

import xlsxwriter  # type: ignore[import-untyped]
from xlsxwriter.worksheet import Worksheet  # type: ignore[import-untyped]

from caxton._internal.backends.xlsxwriter.styles import style_format
from caxton._internal.formulas import lower_excel_formula
from caxton.core.ir import SpreadsheetTableIR


def add_conditional_formats(  # noqa: WPS211
    workbook: xlsxwriter.Workbook,
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    header_row: int,
    last_row: int,
    start_column: int,
) -> None:
    """Materialize compiled conditional-format rules."""
    if last_row == header_row:
        return
    end_column = start_column + len(table.columns) - 1
    for rule in table.rules:
        formula = lower_excel_formula(
            rule.condition,
            current_row=header_row + 2,
        ).removeprefix("=")
        worksheet.conditional_format(
            header_row + 1,
            start_column,
            last_row,
            end_column,
            {
                "type": "formula",
                "criteria": formula,
                "format": style_format(workbook, rule.style),
            },
        )


__all__ = ("add_conditional_formats",)
