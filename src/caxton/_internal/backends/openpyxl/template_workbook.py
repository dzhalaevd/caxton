from __future__ import annotations

import dataclasses
from copy import copy
from io import BytesIO
from typing import Any, cast

from openpyxl import load_workbook
from openpyxl.cell.cell import Cell
from openpyxl.formula.translate import Translator
from openpyxl.utils import get_column_letter, quote_sheetname, range_boundaries
from openpyxl.worksheet.cell_range import CellRange as NativeCellRange
from openpyxl.worksheet.worksheet import Worksheet

from caxton._internal.backends.openpyxl.extensions import (
    OpenpyxlHookContext,
    OpenpyxlHookExtension,
    PivotBinding,
)
from caxton._internal.backends.openpyxl.package import (
    PivotPatch,
    PivotPostProcessor,
    XlsxPackage,
    run_postprocessors,
)
from caxton._internal.backends.openpyxl.tables import render_table
from caxton._internal.backends.openpyxl.workbook import _render_text
from caxton._internal.formulas import lower_excel_formula
from caxton._internal.templates import (
    XlsxNamedRange,
    XlsxTableTarget,
    XlsxTemplateContext,
)
from caxton.core.errors import IncompatibleTemplateRefError, TemplateError
from caxton.core.ir import SpreadsheetIR, SpreadsheetTableIR
from caxton.core.models import ColumnRef, TemplateCompilationResult
from caxton.core.types import Link


@dataclasses.dataclass(frozen=True, slots=True)
class _CellTemplate:
    row: int
    column: int
    value: object
    style: object
    hyperlink: object
    comment: object


@dataclasses.dataclass(frozen=True, slots=True)
class _Insertion:
    after_row: int
    amount: int


@dataclasses.dataclass(frozen=True, slots=True)
class _GeneratedRange:
    sheet: str
    cell_range: str
    data_only: bool = False


def render_template_workbook(
    compilation: TemplateCompilationResult[SpreadsheetIR],
) -> bytes:
    """Render into a private template copy.

    Returns:
        The complete post-processed XLSX payload.

    Raises:
        TemplateError: If the compilation has an incompatible context.
    """
    context = compilation.context
    if not isinstance(context, XlsxTemplateContext):
        message = "OpenPyXL template renderer requires an XLSX template context"
        raise TemplateError(message)
    workbook = load_workbook(BytesIO(context.payload), data_only=False)
    targets = {
        (target.worksheet_index, target.table_index): target
        for item in compilation.targets
        for target in (cast("XlsxTableTarget", item),)
    }
    insertions: dict[str, list[_Insertion]] = {}
    generated_ranges: dict[str, _GeneratedRange] = {}
    for worksheet_index, worksheet_ir in enumerate(compilation.document.worksheets):
        worksheet = workbook[worksheet_ir.name]
        _render_worksheet(
            workbook,
            worksheet,
            worksheet_ir,
            worksheet_index,
            targets,
            insertions,
            generated_ranges,
        )
    _run_hooks(workbook, compilation)
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    return _postprocess_pivots(buffer.getvalue(), compilation, generated_ranges)


def _render_worksheet(  # noqa: C901, WPS211
    workbook: Any,
    worksheet: Worksheet,
    worksheet_ir: Any,
    worksheet_index: int,
    targets: dict[tuple[int, int], XlsxTableTarget],
    insertions: dict[str, list[_Insertion]],
    generated_ranges: dict[str, _GeneratedRange],
) -> None:
    if worksheet_ir.freeze is not None:
        worksheet.freeze_panes = (
            f"{get_column_letter(worksheet_ir.freeze.columns + 1)}"
            f"{worksheet_ir.freeze.rows + 1}"
        )
    for text in worksheet_ir.texts:
        _render_text(worksheet, text)
    sheet_insertions = insertions.setdefault(worksheet.title, [])
    for table_index, table in enumerate(worksheet_ir.tables):
        target = targets.get((worksheet_index, table_index))
        if target is None:
            render_table(worksheet, table)
            if table.name is not None and table.name in worksheet.tables:
                generated_ranges[table.name.casefold()] = _GeneratedRange(
                    sheet=worksheet.title,
                    cell_range=worksheet.tables[table.name].ref,
                )
            continue
        shifted = _shift_target(target, sheet_insertions)
        if target.repeat:
            inserted, end_row = _render_repeated_table(worksheet, table, shifted)
            if inserted.amount:
                sheet_insertions.append(inserted)
                _shift_defined_names(
                    workbook,
                    worksheet.title,
                    inserted.after_row,
                    inserted.amount,
                )
        else:
            end_row = _render_named_table(worksheet, table, shifted)
        generated_ranges[target.reference.casefold()] = _GeneratedRange(
            sheet=worksheet.title,
            cell_range=_range_text(
                shifted.min_row,
                shifted.min_column,
                end_row,
                shifted.min_column + len(table.columns) - 1,
            ),
            data_only=True,
        )
        if table.name is not None:
            generated_ranges[table.name.casefold()] = generated_ranges[
                target.reference.casefold()
            ]


def _render_named_table(
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    target: XlsxNamedRange,
) -> int:
    last_row = target.min_row - 1
    for row in table.rows:
        physical_row = target.min_row + row.index
        if physical_row > target.max_row:
            message = f"Template target {target.reference!r} has too few rows"
            raise IncompatibleTemplateRefError(
                message,
                context={"available_rows": target.rows, "reference": target.reference},
            )
        _write_template_values(
            worksheet,
            table,
            row.values,
            physical_row,
            target.min_column,
        )
        last_row = physical_row
    return max(last_row, target.min_row)


def _render_repeated_table(
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    target: XlsxNamedRange,
) -> tuple[_Insertion, int]:
    rows = tuple(table.rows)
    copies = max(len(rows), 1)
    amount = (copies - 1) * target.rows
    cells = tuple(_snapshot_cells(worksheet, target))
    merges = tuple(_contained_merges(worksheet, target))
    if amount:
        _shift_downstream_merges(worksheet, target.max_row, amount)
        worksheet.insert_rows(target.max_row + 1, amount)
    for copy_index in range(1, copies):
        row_delta = copy_index * target.rows
        _copy_region(worksheet, cells, row_delta)
        for merged in merges:
            worksheet.merge_cells(
                start_row=merged.min_row + row_delta,
                start_column=merged.min_col,
                end_row=merged.max_row + row_delta,
                end_column=merged.max_col,
            )
    for row in rows:
        physical_row = target.min_row + row.index * target.rows
        _write_template_values(
            worksheet,
            table,
            row.values,
            physical_row,
            target.min_column,
        )
    last_row = target.min_row + max(len(rows) - 1, 0) * target.rows
    return _Insertion(after_row=target.max_row, amount=amount), last_row


def _snapshot_cells(
    worksheet: Worksheet,
    target: XlsxNamedRange,
) -> list[_CellTemplate]:
    output: list[_CellTemplate] = []
    for row in worksheet.iter_rows(
        min_row=target.min_row,
        max_row=target.max_row,
        min_col=target.min_column,
        max_col=target.max_column,
    ):
        for cell in row:
            native = cast("Cell", cell)
            native_style = _copy_native_style(native)
            output.append(
                _CellTemplate(
                    row=int(native.row),
                    column=int(native.column),
                    value=native.value,
                    style=native_style,
                    hyperlink=copy(native.hyperlink),
                    comment=copy(native.comment),
                ),
            )
    return output


def _copy_native_style(cell: Cell) -> object:
    return copy(cell._style)  # type: ignore[attr-defined]  # noqa: SLF001


def _copy_region(
    worksheet: Worksheet,
    cells: tuple[_CellTemplate, ...],
    row_delta: int,
) -> None:
    for source in cells:
        target = cast("Any", worksheet.cell(source.row + row_delta, source.column))
        target.value = _translated_value(source, row_delta)
        target._style = copy(source.style)  # noqa: SLF001
        target.hyperlink = copy(source.hyperlink)
        target.comment = copy(source.comment)


def _translated_value(source: _CellTemplate, row_delta: int) -> object:
    value = source.value
    if not isinstance(value, str) or not value.startswith("="):
        return value
    origin = f"{get_column_letter(source.column)}{source.row}"
    target = f"{get_column_letter(source.column)}{source.row + row_delta}"
    return Translator(value, origin=origin).translate_formula(target)


def _contained_merges(
    worksheet: Worksheet,
    target: XlsxNamedRange,
) -> list[NativeCellRange]:
    return [
        NativeCellRange(str(merged))
        for merged in worksheet.merged_cells.ranges
        if (
            merged.min_row >= target.min_row
            and merged.max_row <= target.max_row
            and merged.min_col >= target.min_column
            and merged.max_col <= target.max_column
        )
    ]


def _shift_downstream_merges(
    worksheet: Worksheet,
    after_row: int,
    amount: int,
) -> None:
    downstream = tuple(
        NativeCellRange(str(item))
        for item in worksheet.merged_cells.ranges
        if item.min_row > after_row
    )
    for merged in downstream:
        worksheet.unmerge_cells(str(merged))
    for merged in downstream:
        worksheet.merge_cells(
            start_row=merged.min_row + amount,
            start_column=merged.min_col,
            end_row=merged.max_row + amount,
            end_column=merged.max_col,
        )


def _shift_defined_names(
    workbook: Any,
    sheet_name: str,
    after_row: int,
    amount: int,
) -> None:
    names = list(workbook.defined_names.values())
    for worksheet in workbook.worksheets:
        names.extend(worksheet.defined_names.values())
    for name in names:
        if getattr(name, "type", None) != "RANGE":
            continue
        destinations = tuple(name.destinations)
        shifted = tuple(
            _shift_destination(destination, sheet_name, after_row, amount)
            for destination in destinations
        )
        name.attr_text = ",".join(
            f"{quote_sheetname(sheet)}!{coordinates}" for sheet, coordinates in shifted
        )


def _shift_destination(
    destination: tuple[str, str],
    sheet_name: str,
    after_row: int,
    amount: int,
) -> tuple[str, str]:
    sheet, coordinates = destination
    if sheet != sheet_name:
        return destination
    min_col, min_row, max_col, max_row = range_boundaries(coordinates)
    if min_col is None or min_row is None or max_col is None or max_row is None:
        return destination
    if min_row > after_row:
        min_row += amount
        max_row += amount
    elif max_row > after_row:
        max_row += amount
    return sheet, _range_text(min_row, min_col, max_row, max_col)


def _write_template_values(  # noqa: WPS211
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    values: Any,
    physical_row: int,
    start_column: int,
) -> None:
    for column, value in zip(table.columns, values, strict=True):
        cell_value = value
        if column.formula is not None:
            cell_value = lower_excel_formula(column.formula, current_row=physical_row)
        cell = cast("Cell", worksheet.cell(physical_row, start_column + column.offset))
        cell.value = cell_value
        if isinstance(column.semantic_type, Link) and cell_value is not None:
            cell.hyperlink = str(cell_value)


def _shift_target(target: XlsxTableTarget, insertions: list[_Insertion]) -> Any:
    shift = sum(
        insertion.amount
        for insertion in insertions
        if target.range.min_row > insertion.after_row
    )
    return dataclasses.replace(
        target.range,
        min_row=target.range.min_row + shift,
        max_row=target.range.max_row + shift,
    )


def _range_text(
    min_row: int,
    min_column: int,
    max_row: int,
    max_column: int,
) -> str:
    start = f"${get_column_letter(min_column)}${min_row}"
    end = f"${get_column_letter(max_column)}${max_row}"
    return f"{start}:{end}"


def _run_hooks(workbook: Any, compilation: Any) -> None:
    default_sheet = compilation.document.worksheets[0].name
    for extension in compilation.extensions:
        if not isinstance(extension, OpenpyxlHookExtension):
            continue
        sheet_name = extension.sheet or default_sheet
        if sheet_name not in workbook.sheetnames:
            message = f"OpenPyXL hook worksheet {sheet_name!r} was not found"
            raise TemplateError(message, context={"worksheet": sheet_name})
        extension.function(
            OpenpyxlHookContext(
                native_workbook=workbook,
                native_sheet=workbook[sheet_name],
            ),
        )


def _postprocess_pivots(
    payload: bytes,
    compilation: Any,
    generated_ranges: dict[str, _GeneratedRange],
) -> bytes:
    context = cast("XlsxTemplateContext", compilation.context)
    patches = [
        _pivot_patch(context, extension, generated_ranges)
        for extension in compilation.extensions
        if isinstance(extension, PivotBinding)
    ]
    if not patches:
        return payload
    processor = PivotPostProcessor(
        source=XlsxPackage.from_bytes(context.payload),
        patches=tuple(patches),
    )
    return run_postprocessors(payload, (processor,))


def _pivot_patch(
    context: XlsxTemplateContext,
    binding: PivotBinding,
    generated_ranges: dict[str, _GeneratedRange],
) -> PivotPatch:
    source_name = (
        binding.source.column_id
        if isinstance(binding.source, ColumnRef)
        else binding.source.name
    )
    source = generated_ranges.get(str(source_name).casefold())
    if source is None:
        message = f"Pivot source {source_name!r} was not generated"
        raise TemplateError(message, context={"source": source_name})
    expected = binding.target.casefold()
    matches = [pivot for pivot in context.pivots if pivot.name.casefold() == expected]
    if len(matches) != 1:
        message = f"Pivot target {binding.target!r} was not found uniquely"
        raise TemplateError(message, context={"pivot": binding.target})
    return PivotPatch(
        descriptor=matches[0],
        sheet=source.sheet,
        cell_range=_pivot_source_range(source),
        refresh_on_open=binding.refresh_on_open,
    )


def _pivot_source_range(source: _GeneratedRange) -> str:
    if not source.data_only:
        return source.cell_range
    min_col, min_row, max_col, max_row = range_boundaries(source.cell_range)
    missing_coordinate = (
        min_col is None or min_row is None or max_col is None or max_row is None
    )
    if missing_coordinate:
        message = "Template pivot source requires a header row above its data"
        raise IncompatibleTemplateRefError(message)
    if min_row == 1:
        message = "Template pivot source requires a header row above its data"
        raise IncompatibleTemplateRefError(message)
    return _range_text(
        cast("int", min_row) - 1,
        cast("int", min_col),
        cast("int", max_row),
        cast("int", max_col),
    )


__all__ = ("render_template_workbook",)
