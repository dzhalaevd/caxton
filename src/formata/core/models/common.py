from __future__ import annotations

import enum
from collections.abc import Mapping

from formata.core._values import freeze_mapping
from formata.core.errors import FormataTypeError, FormataValueError


class DocumentKind(enum.StrEnum):
    SPREADSHEET = "spreadsheet"
    FLOW = "flow"
    TABULAR = "tabular"
    FIXED_LAYOUT = "fixed_layout"


DocumentMetadata = Mapping[str, object]


def freeze_metadata(metadata: Mapping[str, object]) -> DocumentMetadata:
    """Take a defensive, read-only snapshot of document metadata.

    Returns:
        An immutable copy of the supplied mapping.

    Raises:
        FormataTypeError: If metadata contains an unsupported value type.
        FormataValueError: If metadata contains a recursive container.
    """
    try:
        return freeze_mapping(metadata, label="Metadata")
    except TypeError as error:
        raise FormataTypeError(str(error)) from error
    except ValueError as error:
        raise FormataValueError(str(error)) from error


__all__ = ("DocumentKind", "DocumentMetadata")
