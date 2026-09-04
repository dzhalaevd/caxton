from __future__ import annotations

from io import BytesIO
from typing import cast

from openpyxl import Workbook
from openpyxl.cell.cell import Cell
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from caxton._internal.backends._xlsx_values import validate_xlsx_text
from caxton._internal.backends.openpyxl.rows import set_literal_cell
from caxton._internal.backends.openpyxl.styles import apply_style
from caxton._internal.backends.openpyxl.tables import render_table
from caxton.core.ir import SpreadsheetIR, SpreadsheetTextIR, SpreadsheetWorksheetIR


def render_workbook(document: SpreadsheetIR) -> bytes:
    """Materialize Spreadsheet IR as XLSX bytes.

    Returns:
        The serialized workbook payload.
    """
    workbook = Workbook()
    for index, worksheet_ir in enumerate(document.worksheets):
        worksheet = _worksheet(workbook, worksheet_ir, first=index == 0)
        _populate_worksheet(worksheet, worksheet_ir)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _worksheet(
    workbook: Workbook,
    worksheet_ir: SpreadsheetWorksheetIR,
    *,
    first: bool,
) -> Worksheet:
    worksheet = workbook.active if first else workbook.create_sheet(worksheet_ir.name)
    if not isinstance(worksheet, Worksheet):
        message = "OpenPyXL did not provide a writable worksheet"
        raise TypeError(message)
    worksheet.title = worksheet_ir.name
    return worksheet


def _populate_worksheet(
    worksheet: Worksheet,
    worksheet_ir: SpreadsheetWorksheetIR,
) -> None:
    if worksheet_ir.freeze is not None:
        worksheet.freeze_panes = (
            f"{get_column_letter(worksheet_ir.freeze.columns + 1)}"
            f"{worksheet_ir.freeze.rows + 1}"
        )
    for text in worksheet_ir.texts:
        _render_text(worksheet, text)
    for table in worksheet_ir.tables:
        render_table(worksheet, table)


def _render_text(worksheet: Worksheet, text: SpreadsheetTextIR) -> None:
    cell = cast(
        "Cell",
        worksheet.cell(
            row=text.anchor.row,
            column=text.anchor.column,
        ),
    )
    set_literal_cell(cell, validate_xlsx_text(text.text, role="title"))
    apply_style(cell, text.style)
    if text.span > 1:
        worksheet.merge_cells(
            start_row=text.anchor.row,
            start_column=text.anchor.column,
            end_row=text.anchor.row,
            end_column=text.anchor.column + text.span - 1,
        )


__all__ = ("render_workbook",)
