from __future__ import annotations

import dataclasses
from io import BytesIO
from pathlib import Path
from typing import ClassVar

import xlsxwriter  # type: ignore[import-untyped]
from xlsxwriter.format import Format  # type: ignore[import-untyped]
from xlsxwriter.image import Image as XlsxImage  # type: ignore[import-untyped]
from xlsxwriter.worksheet import Worksheet  # type: ignore[import-untyped]

from formata._internal.backends._xlsx_formats import number_format
from formata._internal.const import (
    _AGGREGATES,
    _BORDER_STYLES,
    _CHART_TYPES,
    _MIME_TYPE,
    _SEMANTIC_FEATURES,
)
from formata._internal.formulas import lower_excel_formula
from formata._internal.rendering import run_backend
from formata._internal.sinks import BufferSink, FileSink, MemorySink
from formata.core.errors import UnsupportedFeatureError
from formata.core.formatting import Style
from formata.core.ir import (
    SPREADSHEET_IR_VERSION,
    CellRange,
    SpreadsheetChartIR,
    SpreadsheetColumnIR,
    SpreadsheetImageIR,
    SpreadsheetIR,
    SpreadsheetTableIR,
    SpreadsheetTextIR,
    SpreadsheetWorksheetIR,
)
from formata.core.models import AggregateFunction, DocumentKind
from formata.core.protocols import OutputSink
from formata.core.rendering import (
    ExecutionMode,
    ExecutionRequirements,
    RenderContext,
    RendererCapabilities,
    RendererDescriptor,
    RenderResult,
    WorkbookOperation,
)
from formata.core.types import Link


class XlsxWriterRenderer:
    """Default renderer for creating a new XLSX workbook from Spreadsheet IR."""

    descriptor = RendererDescriptor(
        name="xlsxwriter",
        version="1.0",
        formats=frozenset(("xlsx",)),
        mime_types=frozenset((_MIME_TYPE,)),
        extensions=frozenset((".xlsx",)),
        capabilities=RendererCapabilities(
            ir_versions={
                DocumentKind.SPREADSHEET: frozenset((SPREADSHEET_IR_VERSION,)),
            },
            features=_SEMANTIC_FEATURES
            | frozenset(
                (
                    "alignment",
                    "autofilter",
                    "auto_width",
                    "chart",
                    "column_width",
                    "conditional_format",
                    "display_format",
                    "explicit_anchor",
                    "flow_layout",
                    "formula",
                    "freeze_panes",
                    "image",
                    "native_table",
                    "spacer",
                    "stack",
                    "table",
                    "text",
                    "style",
                    "totals",
                ),
            ),
            workbook_operations=frozenset(
                (WorkbookOperation.CREATE_NEW_WORKBOOK,),
            ),
            execution_modes=frozenset(
                (ExecutionMode.STANDARD, ExecutionMode.STREAM),
            ),
        ),
    )

    def render(
        self,
        document: SpreadsheetIR,
        sink: OutputSink,
        context: RenderContext,
    ) -> RenderResult:
        """Create a new XLSX workbook and write it to the supplied sink.

        Returns:
            Metadata describing the written artifact.
        """
        return run_backend(
            lambda: self._render(document, sink, context),
            message="XlsxWriter failed to render the spreadsheet",
            backend=self.descriptor.name,
        )

    def _render(
        self,
        document: SpreadsheetIR,
        sink: OutputSink,
        context: RenderContext,
    ) -> RenderResult:
        plan = _select_execution_plan(context.execution)
        destination = _WorkbookDestination.for_sink(sink)
        try:
            workbook = xlsxwriter.Workbook(destination.target, plan.workbook_options)
            _populate_workbook(workbook, document)
            workbook.close()
            bytes_written = destination.finish()
        except BaseException:
            destination.abort()
            raise
        return RenderResult(
            format=context.format,
            mime_type=_MIME_TYPE,
            renderer=self.descriptor.name,
            bytes_written=bytes_written,
            execution_mode=plan.mode,
            execution_plan=plan.name,
        )


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
        _render_text(workbook, worksheet, text)
    for table in worksheet_ir.tables:
        _render_table(workbook, worksheet, table)
    for picture in worksheet_ir.images:
        _render_image(worksheet, picture)
    for chart in worksheet_ir.charts:
        _render_chart(workbook, worksheet, chart)


def _populate_workbook(
    workbook: xlsxwriter.Workbook,
    document: SpreadsheetIR,
) -> None:
    for worksheet_ir in document.worksheets:
        _populate_worksheet(workbook, worksheet_ir)


def _render_text(
    workbook: xlsxwriter.Workbook,
    worksheet: Worksheet,
    text: SpreadsheetTextIR,
) -> None:
    row = text.anchor.row - 1
    column = text.anchor.column - 1
    cell_format = _style_format(workbook, text.style)
    if text.span > 1:
        worksheet.merge_range(
            row,
            column,
            row,
            column + text.span - 1,
            text.text,
            cell_format,
        )
        return
    worksheet.write(row, column, text.text, cell_format)


def _render_image(worksheet: Worksheet, picture: SpreadsheetImageIR) -> None:
    source = picture.source
    filename = source if isinstance(source, str) else f"{picture.name or 'image'}.png"
    options: dict[str, object] = {}
    if isinstance(source, bytes):
        options["image_data"] = BytesIO(source)
    if picture.description is not None:
        options["description"] = picture.description
    natural = _natural_size(source)
    if natural is not None:
        options["x_scale"] = picture.width / natural[0]
        options["y_scale"] = picture.height / natural[1]
    worksheet.insert_image(
        picture.anchor.row - 1,
        picture.anchor.column - 1,
        filename,
        options,
    )


def _natural_size(source: str | bytes) -> tuple[float, float] | None:
    probe = XlsxImage(BytesIO(source) if isinstance(source, bytes) else source)
    width = float(probe.width)
    height = float(probe.height)
    return (width, height) if width and height else None


def _render_chart(
    workbook: xlsxwriter.Workbook,
    worksheet: Worksheet,
    chart: SpreadsheetChartIR,
) -> None:
    native = workbook.add_chart({"type": _CHART_TYPES[chart.kind]})
    if native is None:
        message = f"XlsxWriter rejected chart kind {chart.kind.value!r}"
        raise ValueError(message)
    for series in chart.series:
        native.add_series(
            {
                "name": series.name,
                "categories": _range_reference(chart.sheet_name, series.categories),
                "values": _range_reference(chart.sheet_name, series.values),
            },
        )
    if chart.title is not None:
        native.set_title({"name": chart.title})
    native.set_size({"width": chart.width, "height": chart.height})
    worksheet.insert_chart(
        chart.anchor.row - 1,
        chart.anchor.column - 1,
        native,
    )


def _range_reference(
    sheet_name: str,
    cell_range: CellRange | None,
) -> list[object] | None:
    if cell_range is None:
        return None
    return [
        sheet_name,
        cell_range.start.row - 1,
        cell_range.start.column - 1,
        cell_range.end.row - 1,
        cell_range.end.column - 1,
    ]


@dataclasses.dataclass(frozen=True, slots=True)
class StandardExecutionPlan:
    """XLSX plan for features that require ordinary workbook behavior."""

    name: ClassVar[str] = "standard"
    mode: ClassVar[ExecutionMode] = ExecutionMode.STANDARD
    data_passes: ClassVar[int] = 1

    @property
    def workbook_options(self) -> dict[str, bool]:
        """Isolated XlsxWriter options for this invocation."""
        return {}


@dataclasses.dataclass(frozen=True, slots=True)
class ConstantMemoryExecutionPlan:
    """Append-only XLSX plan that retains only the current worksheet row."""

    name: ClassVar[str] = "constant_memory"
    mode: ClassVar[ExecutionMode] = ExecutionMode.STREAM
    data_passes: ClassVar[int] = 1

    @property
    def workbook_options(self) -> dict[str, bool]:
        """Isolated XlsxWriter options for this invocation."""
        return {"constant_memory": True}


ExecutionPlan = StandardExecutionPlan | ConstantMemoryExecutionPlan


@dataclasses.dataclass(slots=True)
class _WorkbookDestination:
    target: object
    sink: OutputSink
    start_position: int = 0
    staged_buffer: BytesIO | None = None
    staged_file: Path | None = None

    @classmethod
    def for_sink(cls, sink: OutputSink) -> _WorkbookDestination:
        if isinstance(sink, FileSink):
            staged_file = sink.create_staging_path()
            return cls(
                target=str(staged_file),
                sink=sink,
                staged_file=staged_file,
            )
        if isinstance(sink, MemorySink):
            return cls(
                target=sink.buffer,
                sink=sink,
                start_position=sink.buffer.tell(),
            )
        if isinstance(sink, BufferSink) and sink.seekable_buffer is not None:
            target = sink.seekable_buffer
            return cls(
                target=target,
                sink=sink,
                start_position=target.tell(),
            )
        buffer = BytesIO()
        return cls(target=buffer, sink=sink, staged_buffer=buffer)

    def finish(self) -> int:
        if self.staged_file is not None and isinstance(self.sink, FileSink):
            return self.sink.commit_staged(self.staged_file)
        if self.staged_buffer is not None:
            return self.sink.write(self.staged_buffer.getvalue())
        if isinstance(self.sink, MemorySink):
            return len(self.sink.getvalue()) - self.start_position
        if isinstance(self.sink, BufferSink):
            target = self.sink.seekable_buffer
            if target is not None:
                return target.tell() - self.start_position
        message = "Direct XLSX destination did not expose its written size"
        raise RuntimeError(message)

    def abort(self) -> None:
        """Discard any uncommitted file staging owned by the destination."""
        if self.staged_file is not None and isinstance(self.sink, FileSink):
            self.sink.discard_staged(self.staged_file)


def _select_execution_plan(
    requirements: ExecutionRequirements,
) -> ExecutionPlan:
    stream_compatible = requirements.append_only and not requirements.has_named_tables
    if requirements.mode is ExecutionMode.STREAM and not stream_compatible:
        reason = (
            "native_table"
            if requirements.has_named_tables
            else "document_is_not_append_only"
        )
        message = "Streaming XLSX is incompatible with this document"
        raise UnsupportedFeatureError(
            message,
            context={"execution_mode": "stream", "reason": reason},
        )
    if requirements.mode is ExecutionMode.STREAM or (
        requirements.mode is ExecutionMode.AUTO and stream_compatible
    ):
        plan: ExecutionPlan = ConstantMemoryExecutionPlan()
    else:
        plan = StandardExecutionPlan()
    if requirements.requires_single_pass and plan.data_passes != 1:
        message = "Execution plan would make multiple passes over row data"
        raise UnsupportedFeatureError(
            message,
            context={"execution_plan": plan.name},
        )
    return plan


def _render_table(
    workbook: xlsxwriter.Workbook,
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
) -> None:
    header_row = table.anchor.row - 1
    start_column = table.anchor.column - 1
    header_format = _style_format(workbook, table.header_style)
    column_formats = tuple(_column_format(workbook, column) for column in table.columns)

    _write_headers(worksheet, table, header_row, start_column, header_format)
    last_row, widths = _write_rows(
        worksheet,
        table,
        header_row,
        start_column,
        column_formats,
    )
    _apply_auto_widths(worksheet, table, start_column, widths)
    _write_footer(workbook, worksheet, table, header_row, last_row, start_column)
    _add_conditional_formats(
        workbook,
        worksheet,
        table,
        header_row,
        last_row,
        start_column,
    )
    if table.name is not None:
        _add_native_table(
            worksheet,
            table,
            (header_row, last_row, start_column),
            header_format,
        )
    elif table.autofilter and last_row > header_row:
        worksheet.autofilter(
            header_row,
            start_column,
            last_row,
            start_column + len(table.columns) - 1,
        )


def _write_headers(
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    header_row: int,
    start_column: int,
    header_format: Format,
) -> None:
    for column in table.columns:
        physical_column = start_column + column.offset
        worksheet.write(header_row, physical_column, column.title, header_format)
        if column.width_hint is not None:
            worksheet.set_column_pixels(
                physical_column,
                physical_column,
                round(column.width_hint * 7),
            )


def _write_rows(
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    header_row: int,
    start_column: int,
    column_formats: tuple[Format, ...],
) -> tuple[int, tuple[int, ...]]:
    last_row = header_row
    widths = [len(column.title) for column in table.columns]
    for row in table.rows:
        physical_row = header_row + row.index + 1
        last_row = physical_row
        for column, value, cell_format in zip(
            table.columns,
            row.values,
            column_formats,
            strict=True,
        ):
            widths[column.offset] = max(widths[column.offset], _display_width(value))
            position = (physical_row, start_column + column.offset)
            if column.formula is not None:
                worksheet.write_formula(
                    *position,
                    lower_excel_formula(
                        column.formula,
                        current_row=physical_row + 1,
                    ),
                    cell_format,
                )
            else:
                _write_cell(
                    worksheet,
                    position,
                    value,
                    isinstance(column.semantic_type, Link),
                    cell_format,
                )
    return last_row, tuple(widths)


def _apply_auto_widths(
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    start_column: int,
    widths: tuple[int, ...],
) -> None:
    for column in table.columns:
        if column.auto_width:
            physical_column = start_column + column.offset
            worksheet.set_column(
                physical_column,
                physical_column,
                min(80, max(1, widths[column.offset] + 2)),
            )


def _write_footer(  # noqa: WPS211
    workbook: xlsxwriter.Workbook,
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    header_row: int,
    last_row: int,
    start_column: int,
) -> None:
    footer = table.footer
    if footer is None:
        return
    footer_row = last_row + 1
    cell_format = _style_format(workbook, footer.style)
    worksheet.write(
        footer_row,
        start_column + footer.label_column_offset,
        footer.label,
        cell_format,
    )
    for item in footer.items:
        column = start_column + item.column_offset
        item_format = _footer_format(
            workbook,
            footer.style,
            table.columns[item.column_offset],
        )
        if last_row == header_row:
            worksheet.write(footer_row, column, 0, item_format)
            continue
        formula = _aggregate_formula(
            item.function,
            first_row=header_row + 2,
            last_row=last_row + 1,
            column=column + 1,
        )
        worksheet.write_formula(footer_row, column, formula, item_format)


def _add_conditional_formats(  # noqa: WPS211
    workbook: xlsxwriter.Workbook,
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    header_row: int,
    last_row: int,
    start_column: int,
) -> None:
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
                "format": _style_format(workbook, rule.style),
            },
        )


def _add_native_table(
    worksheet: Worksheet,
    table: SpreadsheetTableIR,
    area: tuple[int, int, int],
    header_format: Format,
) -> None:
    header_row, last_row, start_column = area
    if last_row == header_row:
        message = "XlsxWriter cannot create a native table without data rows"
        raise ValueError(message)
    end_column = start_column + len(table.columns) - 1
    result = worksheet.add_table(
        header_row,
        start_column,
        last_row,
        end_column,
        {
            "name": table.name,
            "style": "Table Style Medium 2",
            "autofilter": table.autofilter,
            "columns": [
                {
                    "header": column.title,
                    "header_format": header_format,
                }
                for column in table.columns
            ],
        },
    )
    if result != 0:
        message = f"XlsxWriter rejected native table {table.name!r}"
        raise ValueError(message)


def _column_format(
    workbook: xlsxwriter.Workbook,
    column: SpreadsheetColumnIR,
) -> Format:
    properties = _style_properties(column.style)
    properties["num_format"] = number_format(column)
    if isinstance(column.semantic_type, Link):
        properties.update({"font_color": "blue", "underline": 1})
    return workbook.add_format(properties)


def _style_format(workbook: xlsxwriter.Workbook, style: Style) -> Format:
    return workbook.add_format(_style_properties(style))


def _footer_format(
    workbook: xlsxwriter.Workbook,
    style: Style,
    column: SpreadsheetColumnIR,
) -> Format:
    properties = _style_properties(style)
    effective = dataclasses.replace(
        column,
        display_format=style.display_format or column.display_format,
    )
    properties["num_format"] = number_format(effective)
    return workbook.add_format(properties)


def _style_properties(style: Style) -> dict[str, object]:  # noqa: C901
    properties: dict[str, object] = {}
    if style.font is not None:
        font = style.font
        if font.name is not None:
            properties["font_name"] = font.name
        if font.size is not None:
            properties["font_size"] = font.size
        if font.bold is not None:
            properties["bold"] = font.bold
        if font.italic is not None:
            properties["italic"] = font.italic
        if font.underline is not None:
            properties["underline"] = 1 if font.underline else 0
        if font.color is not None:
            properties["font_color"] = font.color
    if style.fill is not None:
        properties.update({"bg_color": style.fill.color, "pattern": 1})
    if style.alignment is not None:
        alignment = style.alignment
        if alignment.horizontal is not None:
            properties["align"] = alignment.horizontal.value
        if alignment.vertical is not None:
            properties["valign"] = alignment.vertical.value
        if alignment.wrap_text is not None:
            properties["text_wrap"] = alignment.wrap_text
    if style.border is not None:
        for side in ("top", "right", "bottom", "left"):
            line = getattr(style.border, side)
            if line is not None:
                properties[side] = _BORDER_STYLES[line.style]
                if line.color is not None:
                    properties[f"{side}_color"] = line.color
    return properties


def _aggregate_formula(
    function: AggregateFunction,
    *,
    first_row: int,
    last_row: int,
    column: int,
) -> str:
    from formata._internal.normalization import format_cell_address  # noqa: PLC0415

    start = format_cell_address(first_row, column)
    end = format_cell_address(last_row, column)
    return f"={_AGGREGATES[function]}({start}:{end})"


def _display_width(value: object) -> int:
    if value is None:
        return 0
    return len(str(value))


def _write_cell(
    worksheet: Worksheet,
    position: tuple[int, int],
    value: object,
    is_link: bool,
    cell_format: Format,
) -> None:
    row, column_index = position
    if is_link and value is not None:
        worksheet.write_url(
            row,
            column_index,
            str(value),
            cell_format,
            str(value),
        )
        return
    worksheet.write(row, column_index, value, cell_format)


__all__ = (
    "ConstantMemoryExecutionPlan",
    "StandardExecutionPlan",
    "XlsxWriterRenderer",
)
