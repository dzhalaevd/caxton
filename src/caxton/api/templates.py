from __future__ import annotations

import os
import zipfile
from collections.abc import Sequence
from io import BytesIO
from pathlib import Path

from caxton.core.errors import TemplateFormatError
from caxton.core.models import ColumnRef
from caxton.core.models.templates import (
    Extension,
    TemplateRepeat,
    TemplateSpecification,
)


def template(  # noqa: WPS125
    source: str | os.PathLike[str] | bytes,
    *,
    format: str | None = None,  # noqa: A002
    extensions: Sequence[Extension] = (),
) -> TemplateSpecification:
    """Describe an immutable document template without opening it.

    Returns:
        A format-independent template specification.

    Raises:
        TemplateFormatError: If the format is unknown or conflicts with source.
    """
    normalized = bytes(source) if isinstance(source, bytes) else os.fspath(source)
    detected = _detect_format(normalized)
    selected = format.lower().removeprefix(".") if format is not None else detected
    if selected is None:
        message = "Could not detect the template format; select it explicitly"
        raise TemplateFormatError(message)
    if detected is not None and format is not None and selected != detected:
        message = "Explicit template format conflicts with the source format"
        raise TemplateFormatError(
            message,
            context={"detected": detected, "selected": selected},
        )
    return TemplateSpecification(
        source=normalized,
        format=selected,
        extensions=tuple(extensions),
    )


def repeat(reference: ColumnRef) -> TemplateRepeat:
    """Repeat a logically referenced template region for table rows.

    Returns:
        Immutable generic repeat intent.
    """
    return TemplateRepeat(reference)


def _detect_format(source: str | bytes) -> str | None:
    if isinstance(source, str):
        suffix = Path(source).suffix.lower().removeprefix(".")
        return suffix if suffix in {"docx", "xlsx"} else None
    try:
        with zipfile.ZipFile(BytesIO(source)) as package:
            content_types = package.read("[Content_Types].xml")
    except (KeyError, OSError, zipfile.BadZipFile):
        return None
    if b"spreadsheetml.sheet" in content_types:
        return "xlsx"
    if b"wordprocessingml.document" in content_types:
        return "docx"
    return None


__all__ = ("repeat", "template")
