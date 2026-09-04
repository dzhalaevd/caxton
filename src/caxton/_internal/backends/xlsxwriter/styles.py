"""Translate backend-neutral styles into XlsxWriter formats."""

from __future__ import annotations

import dataclasses

import xlsxwriter  # type: ignore[import-untyped]
from xlsxwriter.format import Format  # type: ignore[import-untyped]

from caxton._internal.backends._xlsx_formats import display_number_format, number_format
from caxton._internal.const import _BORDER_STYLES
from caxton.core.formatting import Style
from caxton.core.ir import SpreadsheetColumnIR
from caxton.core.types import Link


def column_format(
    workbook: xlsxwriter.Workbook,
    column: SpreadsheetColumnIR,
) -> Format:
    """Create the native format for a spreadsheet column.

    Returns:
        A workbook-owned XlsxWriter format.
    """
    properties = style_properties(column.style)
    properties["num_format"] = number_format(column)
    if isinstance(column.semantic_type, Link):
        properties.update({"font_color": "blue", "underline": 1})
    return workbook.add_format(properties)


def style_format(workbook: xlsxwriter.Workbook, style: Style) -> Format:
    """Create a native format from backend-neutral style intent.

    Returns:
        A workbook-owned XlsxWriter format.
    """
    properties = style_properties(style)
    if style.display_format is not None:
        properties["num_format"] = display_number_format(style.display_format)
    return workbook.add_format(properties)


def footer_format(
    workbook: xlsxwriter.Workbook,
    style: Style,
    column: SpreadsheetColumnIR,
) -> Format:
    """Create a footer format with the effective display pattern.

    Returns:
        A workbook-owned XlsxWriter format.
    """
    properties = style_properties(style)
    effective = dataclasses.replace(
        column,
        display_format=style.display_format or column.display_format,
    )
    properties["num_format"] = number_format(effective)
    return workbook.add_format(properties)


def style_properties(style: Style) -> dict[str, object]:
    """Lower backend-neutral style intent to XlsxWriter properties.

    Returns:
        Native format properties accepted by XlsxWriter.
    """
    properties: dict[str, object] = {}
    _add_font(properties, style)
    _add_fill(properties, style)
    _add_alignment(properties, style)
    _add_border(properties, style)
    return properties


def _add_font(properties: dict[str, object], style: Style) -> None:
    if style.font is None:
        return
    font = style.font
    optional = {
        "font_name": font.name,
        "font_size": font.size,
        "bold": font.bold,
        "italic": font.italic,
        "font_color": font.color,
    }
    properties.update(
        {key: value for key, value in optional.items() if value is not None},
    )
    if font.underline is not None:
        properties["underline"] = 1 if font.underline else 0


def _add_fill(properties: dict[str, object], style: Style) -> None:
    if style.fill is not None:
        properties.update({"bg_color": style.fill.color, "pattern": 1})


def _add_alignment(properties: dict[str, object], style: Style) -> None:
    if style.alignment is None:
        return
    alignment = style.alignment
    if alignment.horizontal is not None:
        properties["align"] = alignment.horizontal.value
    if alignment.vertical is not None:
        properties["valign"] = alignment.vertical.value
    if alignment.wrap_text is not None:
        properties["text_wrap"] = alignment.wrap_text


def _add_border(properties: dict[str, object], style: Style) -> None:
    if style.border is None:
        return
    for side in ("top", "right", "bottom", "left"):
        line = getattr(style.border, side)
        if line is not None:
            properties[side] = _BORDER_STYLES[line.style]
            if line.color is not None:
                properties[f"{side}_color"] = line.color


__all__ = ("column_format", "footer_format", "style_format")
