from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from formata._internal.data import coerce_data_source
from formata.core.errors import FormataValueError
from formata.core.formatting import DocumentTheme, Style, StyleInput, StyleSheet
from formata.core.models import (
    Column,
    ConditionalRule,
    Freeze,
    SpreadsheetDocument,
    SpreadsheetTable,
    TableData,
    Total,
    Totals,
    Worksheet,
)
from formata.core.models.spreadsheet import metadata_or_empty


def table(  # noqa: WPS211
    rows: object,
    *columns: Column,
    name: str | None = None,
    anchor: str | None = None,
    style: StyleInput | None = None,
    header_style: StyleInput | None = None,
    totals: Sequence[Total] = (),
    footer: Totals | None = None,
    rules: Sequence[ConditionalRule] = (),
    autofilter: bool = False,
    freeze: str | None = None,
    auto_width: bool = False,
) -> SpreadsheetTable:
    """Create a spreadsheet table without consuming its row source.

    Returns:
        An immutable spreadsheet table specification.

    Raises:
        FormataValueError: If both footer forms are supplied.
    """
    source = coerce_data_source(rows)
    if footer is not None and totals:
        message = "Use either footer or totals, not both"
        raise FormataValueError(message)
    resolved_footer = _resolve_footer(footer, totals)
    return SpreadsheetTable(
        data=TableData(source=source, columns=tuple(columns)),
        name=name,
        anchor=anchor,
        style=style,
        header_style=header_style,
        footer=resolved_footer,
        rules=tuple(rules),
        autofilter=autofilter,
        freeze=freeze,
        auto_width=auto_width,
    )


def sheet(
    name: str,
    *blocks: SpreadsheetTable,
    freeze: Freeze | None = None,
) -> Worksheet:
    return Worksheet(name=name, blocks=tuple(blocks), freeze=freeze)


def spreadsheet(
    *worksheets: Worksheet,
    metadata: Mapping[str, Any] | None = None,
    styles: StyleSheet | Mapping[str, Style] | None = None,
    theme: DocumentTheme | None = None,
) -> SpreadsheetDocument:
    style_sheet = styles if isinstance(styles, StyleSheet) else StyleSheet(styles or {})
    return SpreadsheetDocument(
        worksheets=tuple(worksheets),
        metadata=metadata_or_empty(metadata),
        styles=style_sheet,
        theme=theme or DocumentTheme(),
    )


def _resolve_footer(
    footer: Totals | None,
    totals: Sequence[Total],
) -> Totals | None:
    if footer is not None:
        return footer
    return Totals(items=tuple(totals)) if totals else None


__all__ = ("sheet", "spreadsheet", "table")
