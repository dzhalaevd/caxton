from __future__ import annotations

from formata._internal.operations import render_document, write_document
from formata._internal.validation import validate_spreadsheet
from formata.core.ir import SpreadsheetIR
from formata.core.models import SpreadsheetDocument
from formata.core.protocols import OutputTarget, Renderer
from formata.core.rendering import ExecutionMode, RenderResult


def validate(document: SpreadsheetDocument) -> None:
    """Validate spreadsheet structure without consuming row data."""
    validate_spreadsheet(document)


def render(
    document: SpreadsheetDocument,
    *,
    format: str = "xlsx",  # noqa: A002
    backend: str | None = None,
    mode: ExecutionMode | str = ExecutionMode.AUTO,
    renderer: Renderer[SpreadsheetIR] | None = None,
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
    renderer: Renderer[SpreadsheetIR] | None = None,
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
