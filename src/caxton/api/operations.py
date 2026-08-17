from __future__ import annotations

from caxton._internal.operations import render_document, write_document
from caxton._internal.validation import validate_spreadsheet
from caxton.core.ir import SpreadsheetIR
from caxton.core.models import SpreadsheetDocument
from caxton.core.protocols import OutputTarget, Renderer, TemplateRenderer
from caxton.core.rendering import ExecutionMode, RenderResult


def validate(document: SpreadsheetDocument) -> None:
    """Validate spreadsheet structure without consuming row data."""
    validate_spreadsheet(document)


def render(
    document: SpreadsheetDocument,
    *,
    format: str = "xlsx",  # noqa: A002
    backend: str | None = None,
    mode: ExecutionMode | str = ExecutionMode.AUTO,
    renderer: Renderer[SpreadsheetIR] | TemplateRenderer[SpreadsheetIR] | None = None,
) -> RenderResult:
    """Render a spreadsheet document and return its artifact bytes.

    Returns:
        Rendering metadata containing the in-memory artifact.
    """
    return render_document(
        document,
        format_name=format,
        backend=backend,
        mode=mode,
        renderer=renderer,
    )


def write(  # noqa: WPS211
    document: SpreadsheetDocument,
    target: OutputTarget,
    *,
    format: str | None = None,  # noqa: A002
    backend: str | None = None,
    mode: ExecutionMode | str = ExecutionMode.AUTO,
    renderer: Renderer[SpreadsheetIR] | TemplateRenderer[SpreadsheetIR] | None = None,
) -> RenderResult:
    """Render a spreadsheet document into a path or binary buffer.

    Returns:
        Metadata describing the artifact. Buffer writes retain inspectable data.
    """
    return write_document(
        document,
        target,
        format_name=format,
        backend=backend,
        mode=mode,
        renderer=renderer,
    )


__all__ = ("render", "validate", "write")
