from __future__ import annotations

from caxton._internal.backends.openpyxl.template_workbook import (
    render_template_workbook,
)
from caxton._internal.const import _MIME_TYPE, _SEMANTIC_FEATURES
from caxton._internal.rendering import run_backend
from caxton.core.ir import SPREADSHEET_IR_VERSION, SpreadsheetIR
from caxton.core.models import DocumentKind, TemplateCompilationResult
from caxton.core.protocols import OutputSink
from caxton.core.rendering import (
    ExecutionMode,
    RenderContext,
    RendererCapabilities,
    RendererDescriptor,
    RenderResult,
    WorkbookOperation,
)


class OpenpyxlTemplateRenderer:
    """Bundled XLSX renderer dedicated to existing templates."""

    descriptor = RendererDescriptor(
        name="openpyxl-template",
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
                    "style",
                    "table",
                    "template",
                    "template_references",
                    "template_repeat",
                    "text",
                    "totals",
                    "xlsx_named_ranges",
                    "xlsx_openpyxl_hook",
                    "xlsx_pivot_rebind",
                    "xlsx_pivot_refresh",
                ),
            ),
            workbook_operations=frozenset(
                (WorkbookOperation.USE_EXISTING_TEMPLATE,),
            ),
        ),
    )

    def render(
        self,
        compilation: TemplateCompilationResult[SpreadsheetIR],
        sink: OutputSink,
        context: RenderContext,
    ) -> RenderResult:
        """Render against a copied template and commit one completed payload.

        Returns:
            Metadata for the committed XLSX artifact.
        """
        return run_backend(
            lambda: self._render(compilation, sink, context),
            message="OpenPyXL failed to render the XLSX template",
            backend=self.descriptor.name,
        )

    def _render(
        self,
        compilation: TemplateCompilationResult[SpreadsheetIR],
        sink: OutputSink,
        context: RenderContext,
    ) -> RenderResult:
        payload = render_template_workbook(compilation)
        bytes_written = sink.write(payload)
        return RenderResult(
            format=context.format,
            mime_type=_MIME_TYPE,
            renderer=self.descriptor.name,
            bytes_written=bytes_written,
            execution_mode=ExecutionMode.STANDARD,
            execution_plan="template",
        )


__all__ = ("OpenpyxlTemplateRenderer",)
