"""Implement the public Renderer contract with XlsxWriter."""

from __future__ import annotations

import xlsxwriter  # type: ignore[import-untyped]

from caxton._internal.backends.xlsxwriter.destination import WorkbookDestination
from caxton._internal.backends.xlsxwriter.execution import select_execution_plan
from caxton._internal.backends.xlsxwriter.workbook import populate_workbook
from caxton._internal.const import _MIME_TYPE, _SEMANTIC_FEATURES
from caxton._internal.rendering import run_backend
from caxton.core.ir import SPREADSHEET_IR_VERSION, SpreadsheetIR
from caxton.core.models import DocumentKind
from caxton.core.protocols import OutputSink
from caxton.core.rendering import (
    ExecutionMode,
    RenderContext,
    RendererCapabilities,
    RendererDescriptor,
    RenderResult,
    WorkbookOperation,
)


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
                    "aggregation",
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
                    "grouping",
                    "matrix",
                    "merge_cells",
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
        plan = select_execution_plan(context.execution)
        destination = WorkbookDestination.for_sink(sink)
        try:
            workbook = xlsxwriter.Workbook(destination.target, plan.workbook_options)
            populate_workbook(workbook, document)
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


__all__ = ("XlsxWriterRenderer",)
