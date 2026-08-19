"""Populate XlsxWriter workbooks from Spreadsheet IR."""

from __future__ import annotations

import xlsxwriter  # type: ignore[import-untyped]

from caxton._internal.backends.xlsxwriter.drawings import (
    render_chart,
    render_image,
    render_text,
)
from caxton._internal.backends.xlsxwriter.tables import render_table
from caxton.core.ir import SpreadsheetIR, SpreadsheetWorksheetIR


def populate_workbook(
    workbook: xlsxwriter.Workbook,
    document: SpreadsheetIR,
) -> None:
    """Populate a native workbook from Spreadsheet IR."""
    for worksheet_ir in document.worksheets:
        _populate_worksheet(workbook, worksheet_ir)


def _populate_worksheet(
    workbook: xlsxwriter.Workbook,
    worksheet_ir: SpreadsheetWorksheetIR,
) -> None:
    worksheet = workbook.add_worksheet(worksheet_ir.name)
    if worksheet_ir.freeze is not None:
        worksheet.freeze_panes(
            worksheet_ir.freeze.rows,
            worksheet_ir.freeze.columns,
        )
    for text in worksheet_ir.texts:
        render_text(workbook, worksheet, text)
    for table in worksheet_ir.tables:
        render_table(workbook, worksheet, table)
    for picture in worksheet_ir.images:
        render_image(worksheet, picture)
    for chart in worksheet_ir.charts:
        render_chart(workbook, worksheet, chart)


__all__ = ("populate_workbook",)
