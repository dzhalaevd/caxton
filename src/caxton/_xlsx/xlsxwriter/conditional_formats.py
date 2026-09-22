from __future__ import annotations

import xlsxwriter  # type: ignore[import-untyped]
from xlsxwriter.worksheet import Worksheet  # type: ignore[import-untyped]

from caxton._spreadsheet.layout import table_data_row
from caxton._xlsx.formulas import lower_excel_formula
from caxton._xlsx.xlsxwriter.styles import style_format
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
    first_data_row = table_data_row(header_row, 0)
    end_column = start_column + len(table.columns) - 1
    for rule in table.rules:
        formula = lower_excel_formula(
            rule.condition,
            current_row=first_data_row + 1,
        ).removeprefix("=")
        worksheet.conditional_format(
            first_data_row,
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
