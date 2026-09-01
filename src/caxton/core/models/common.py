from __future__ import annotations

from collections.abc import Mapping

from caxton.core._compat import StrEnum
from caxton.core._values import freeze_mapping
from caxton.core.errors import CaxtonTypeError, CaxtonValueError


class DocumentKind(StrEnum):
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
        CaxtonTypeError: If metadata contains an unsupported value type.
        CaxtonValueError: If metadata contains a recursive container.
    """
    try:
        return freeze_mapping(metadata, label="Metadata")
    except TypeError as error:
        raise CaxtonTypeError(str(error)) from error
    except ValueError as error:
        raise CaxtonValueError(str(error)) from error


__all__ = ("DocumentKind", "DocumentMetadata")
