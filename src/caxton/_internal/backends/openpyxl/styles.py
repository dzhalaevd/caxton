from __future__ import annotations

from typing import Literal, overload

from openpyxl.cell.cell import Cell
from openpyxl.styles import (
    Alignment as OpenpyxlAlignment,
    Border,
    Font,
    PatternFill,
    Side,
)

from caxton._internal.backends._xlsx_formats import number_format
from caxton.core.formatting import BorderLine, FontStyle, Style
from caxton.core.ir import SpreadsheetColumnIR
from caxton.core.types import Link

NativeStyle = tuple[Font, PatternFill, Border, OpenpyxlAlignment]


def style_cell(cell: Cell, column: SpreadsheetColumnIR) -> None:
    """Apply column style and value semantics to a native cell."""
    apply_style(cell, column.style)
    cell.number_format = number_format(column)
    if isinstance(column.semantic_type, Link) and cell.value is not None:
        cell.hyperlink = str(cell.value)


def apply_style(cell: Cell, style: Style) -> None:
    """Apply backend-neutral style intent to a native cell."""
    font, fill, border, alignment = native_style(style)
    cell.font = font
    cell.fill = fill
    cell.border = border
    cell.alignment = alignment


def native_style(style: Style) -> NativeStyle:
    """Lower backend-neutral style intent to OpenPyXL values.

    Returns:
        Font, fill, border, and alignment values.
    """
    font_style = style.font
    font = Font(
        name=None if font_style is None else font_style.name,
        size=None if font_style is None else font_style.size,
        bold=None if font_style is None else font_style.bold,
        italic=None if font_style is None else font_style.italic,
        underline=_underline(font_style),
        color=None if font_style is None else _argb(font_style.color),
    )
    fill = _fill(style)
    border = _border(style)
    alignment = _alignment(style)
    return font, fill, border, alignment


def _fill(style: Style) -> PatternFill:
    if style.fill is None:
        return PatternFill()
    return PatternFill(fill_type="solid", fgColor=_argb(style.fill.color))


def _border(style: Style) -> Border:
    if style.border is None:
        return Border()
    return Border(
        top=_side(style.border.top),
        right=_side(style.border.right),
        bottom=_side(style.border.bottom),
        left=_side(style.border.left),
    )


def _alignment(style: Style) -> OpenpyxlAlignment:
    alignment = style.alignment
    return OpenpyxlAlignment(
        horizontal=(
            None
            if alignment is None or alignment.horizontal is None
            else alignment.horizontal.value
        ),
        vertical=(
            None
            if alignment is None or alignment.vertical is None
            else alignment.vertical.value
        ),
        wrap_text=None if alignment is None else alignment.wrap_text,
    )


def _underline(font_style: FontStyle | None) -> Literal["single"] | None:
    if font_style is None or font_style.underline is None:
        return None
    return "single" if font_style.underline else None


def _side(line: BorderLine | None) -> Side:
    if line is None:
        return Side()
    return Side(style=line.style.value, color=_argb(line.color))


@overload
def _argb(color: str) -> str: ...


@overload
def _argb(color: None) -> None: ...


def _argb(color: str | None) -> str | None:
    return None if color is None else f"FF{color.removeprefix('#')}"


__all__ = ("apply_style", "native_style", "style_cell")
