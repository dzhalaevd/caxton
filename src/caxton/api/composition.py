from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from caxton._internal.composition import compose_spreadsheet
from caxton.core.formatting import DocumentTheme, Style, StyleSheet
from caxton.core.models import SpreadsheetDocument, TemplateSpecification


def compose(
    sections: Mapping[str, SpreadsheetDocument],
    *,
    metadata: Mapping[str, Any] | None = None,
    styles: StyleSheet | Mapping[str, Style] | None = None,
    theme: DocumentTheme | None = None,
    template: TemplateSpecification | None = None,  # noqa: WPS125
) -> SpreadsheetDocument:
    """Compose named spreadsheet sections into one immutable document.

    Mapping order determines section and worksheet order. Output worksheet names use
    ``"<section> - <worksheet>"``. Section-local explicit worksheet references are
    updated to those final names; references outside the source section are rejected.

    Child styles, themes, and metadata are inherited when compatible. Explicit outer
    values resolve conflicts. A child document cannot own a workbook template, while
    one outer template may be applied to the composed document.

    Args:
        sections: Ordered mapping from section names to spreadsheet documents.
        metadata: Complete metadata for the result, or ``None`` to merge child values.
        styles: Final named-style overrides, or ``None`` to merge child definitions.
        theme: Final theme, or ``None`` to inherit compatible child themes.
        template: Optional template owned by the resulting workbook.

    Returns:
        A new immutable spreadsheet document.
    """
    style_sheet = None
    if isinstance(styles, StyleSheet):
        style_sheet = styles
    elif styles is not None:
        style_sheet = StyleSheet(styles)
    return compose_spreadsheet(
        sections,
        metadata=metadata,
        styles=style_sheet,
        theme=theme,
        template=template,
    )


__all__ = ("compose",)
