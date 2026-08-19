from __future__ import annotations

from caxton._internal.backends.openpyxl.workbook import render_workbook
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


class OpenpyxlRenderer:
    """Bundled create-new XLSX renderer for the current Spreadsheet IR."""

    descriptor = RendererDescriptor(
        name="openpyxl",
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
                    "column_width",
                    "conditional_format",
                    "display_format",
                    "explicit_anchor",
                    "flow_layout",
                    "formula",
                    "grouping",
                    "freeze_panes",
                    "native_table",
                    "matrix",
                    "merge_cells",
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
        ),
    )

    def render(
        self,
        document: SpreadsheetIR,
        sink: OutputSink,
        context: RenderContext,
    ) -> RenderResult:
        """Materialize Spreadsheet IR as XLSX bytes.

        Returns:
            Metadata describing the written artifact.
        """
        return run_backend(
            lambda: self._render(document, sink, context),
            message="OpenPyXL failed to render the spreadsheet",
            backend=self.descriptor.name,
        )

    def _render(
        self,
        document: SpreadsheetIR,
        sink: OutputSink,
        context: RenderContext,
    ) -> RenderResult:
        bytes_written = sink.write(render_workbook(document))
        return RenderResult(
            format=context.format,
            mime_type=_MIME_TYPE,
            renderer=self.descriptor.name,
            bytes_written=bytes_written,
            execution_mode=ExecutionMode.STANDARD,
            execution_plan="standard",
        )


__all__ = ("OpenpyxlRenderer",)
