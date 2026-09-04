from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from typing import cast

from caxton._internal.compiler import SpreadsheetCompiler
from caxton._internal.requirements import analyze_spreadsheet_requirements
from caxton._internal.resolver import BuiltinRendererResolver, canonical_format_name
from caxton._internal.sinks import (
    BufferSink,
    BufferTransactionSink,
    FileSink,
    FileTransactionSink,
    MemorySink,
    coerce_output_sink,
)
from caxton._internal.templates import XlsxTemplateCompiler, XlsxTemplateInspector
from caxton._internal.validation import validate_spreadsheet
from caxton.core.errors import CaxtonTypeError
from caxton.core.ir import SpreadsheetIR
from caxton.core.models import SpreadsheetDocument
from caxton.core.protocols import OutputSink, OutputTarget, Renderer, TemplateRenderer
from caxton.core.rendering import (
    ExecutionMode,
    RenderContext,
    RenderResult,
    RequiredCapabilities,
)

RendererOption = Renderer[SpreadsheetIR] | TemplateRenderer[SpreadsheetIR]


def render_document(
    document: SpreadsheetDocument,
    *,
    format_name: str = "xlsx",
    backend: str | None = None,
    mode: ExecutionMode | str = ExecutionMode.AUTO,
    renderer: RendererOption | None = None,
) -> RenderResult:
    """Render a spreadsheet document into memory.

    Returns:
        A result containing the rendered artifact bytes.
    """
    sink = MemorySink()
    result = _execute(
        document,
        sink,
        format_name=format_name,
        backend=backend,
        mode=mode,
        renderer=renderer,
    )
    return dataclasses.replace(result, data=sink.getvalue())


def write_document(  # noqa: WPS211
    document: SpreadsheetDocument,
    target: OutputTarget,
    *,
    format_name: str | None = None,
    backend: str | None = None,
    mode: ExecutionMode | str = ExecutionMode.AUTO,
    renderer: RendererOption | None = None,
) -> RenderResult:
    """Render a spreadsheet document into a path or binary buffer.

    Returns:
        Metadata describing the artifact. Buffer writes retain inspectable data.
    """
    resolved_format = format_name or _infer_format(target) or "xlsx"
    sink, target_label = coerce_output_sink(target)
    transaction = _output_transaction(sink)
    try:
        result = _execute(
            document,
            transaction,
            format_name=resolved_format,
            backend=backend,
            mode=mode,
            renderer=renderer,
        )
        transaction.commit()
    except BaseException:
        transaction.abort()
        raise
    return dataclasses.replace(
        result,
        data=(
            transaction.getvalue()
            if isinstance(transaction, BufferTransactionSink)
            else None
        ),
        target=target_label,
    )


def _output_transaction(
    sink: OutputSink,
) -> FileTransactionSink | BufferTransactionSink:
    if isinstance(sink, FileSink):
        return FileTransactionSink(sink)
    if isinstance(sink, BufferSink):
        return BufferTransactionSink(sink)
    message = f"Unsupported transactional sink: {type(sink).__name__}"
    raise CaxtonTypeError(
        message,
        context={"sink_type": type(sink).__name__},
    )


def _execute(  # noqa: WPS211
    document: SpreadsheetDocument,
    sink: OutputSink,
    *,
    format_name: str,
    backend: str | None,
    mode: ExecutionMode | str,
    renderer: RendererOption | None,
) -> RenderResult:
    validate_spreadsheet(document)
    required = analyze_spreadsheet_requirements(document, mode=mode)
    if document.template is not None:
        return _execute_template(
            document,
            sink,
            required=required,
            format_name=format_name,
            backend=backend,
            renderer=renderer,
        )
    selected = BuiltinRendererResolver().select(
        required,
        format_name=format_name,
        backend=backend,
        renderer=renderer,
    )
    compiled = SpreadsheetCompiler().compile_validated(
        document,
        capabilities=selected.descriptor.capabilities,
    )
    context = RenderContext(
        format=canonical_format_name(selected, format_name),
        backend=selected.descriptor.name,
        execution=required.execution,
    )
    create_renderer = cast("Renderer[SpreadsheetIR]", selected)
    return create_renderer.render(compiled, sink, context)


def _execute_template(  # noqa: WPS211
    document: SpreadsheetDocument,
    sink: OutputSink,
    *,
    required: RequiredCapabilities,
    format_name: str,
    backend: str | None,
    renderer: RendererOption | None,
) -> RenderResult:
    template = document.template
    if template is None:
        message = "Template execution requires a template"
        raise RuntimeError(message)
    if not _template_format_matches(format_name, template.format):
        message = "Render format conflicts with the template format"
        from caxton.core.errors import TemplateFormatError  # noqa: PLC0415

        raise TemplateFormatError(
            message,
            context={"render_format": format_name, "template_format": template.format},
        )
    if template.format != "xlsx":
        message = f"No template adapter is available for {template.format!r}"
        from caxton.core.errors import UnsupportedFeatureError  # noqa: PLC0415

        raise UnsupportedFeatureError(message)
    selected = BuiltinRendererResolver().select(
        required,
        format_name=format_name,
        backend=backend,
        renderer=renderer,
    )
    inspected = XlsxTemplateInspector().inspect(template)
    compiled = XlsxTemplateCompiler().compile(document, inspected)
    context = RenderContext(
        format=canonical_format_name(selected, format_name),
        backend=selected.descriptor.name,
        execution=required.execution,
    )
    template_renderer = cast("TemplateRenderer[SpreadsheetIR]", selected)
    return template_renderer.render(compiled, sink, context)


def _template_format_matches(format_hint: str, template_format: str) -> bool:
    normalized = format_hint.lower()
    if template_format == "xlsx":
        return normalized in {
            ".xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xlsx",
        }
    return normalized.removeprefix(".") == template_format


def _infer_format(target: OutputTarget) -> str | None:
    if not isinstance(target, (str, os.PathLike)):
        return None
    suffix = Path(target).suffix
    return suffix[1:].lower() if suffix else None


__all__ = ("render_document", "write_document")
