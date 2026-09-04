from __future__ import annotations

import dataclasses
import math
import re
from collections.abc import Iterator, Mapping
from types import MappingProxyType
from typing import TypeAlias, get_args

from caxton.core._compat import StrEnum, final
from caxton.core.errors import CaxtonTypeError, CaxtonValueError

from .alignment import Alignment
from .display import DisplayFormat

_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _color(value: str, label: str) -> str:
    if not isinstance(value, str):
        message = f"{label} must be a string"
        raise CaxtonTypeError(message)
    if not _COLOR.fullmatch(value):
        message = f"{label} must use #RRGGBB notation"
        raise CaxtonValueError(message)
    return value.upper()


@final
@dataclasses.dataclass(frozen=True, slots=True)
class FontStyle:
    """Backend-independent font presentation."""

    name: str | None = None
    size: float | None = None
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    color: str | None = None

    def __post_init__(self) -> None:
        if self.name is not None and (
            not isinstance(self.name, str) or not self.name.strip()
        ):
            message = "Font name cannot be empty"
            raise CaxtonValueError(message)
        if self.size is not None:
            if (
                isinstance(self.size, bool)
                or not isinstance(self.size, (int, float))
                or not math.isfinite(self.size)
                or self.size <= 0
            ):
                message = "Font size must be positive"
                raise CaxtonValueError(message)
            object.__setattr__(self, "size", float(self.size))
        if self.color is not None:
            object.__setattr__(self, "color", _color(self.color, "Font color"))


@final
@dataclasses.dataclass(frozen=True, slots=True)
class FillStyle:
    """Solid cell fill."""

    color: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "color", _color(self.color, "Fill color"))


class BorderLineStyle(StrEnum):
    THIN = "thin"
    MEDIUM = "medium"
    THICK = "thick"
    DASHED = "dashed"
    DOTTED = "dotted"
    DOUBLE = "double"


@final
@dataclasses.dataclass(frozen=True, slots=True)
class BorderLine:
    """One side of a backend-independent cell border."""

    style: BorderLineStyle
    color: str | None = None

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "style", BorderLineStyle(self.style))
        except ValueError as error:
            message = f"Unsupported border style {self.style!r}"
            raise CaxtonValueError(message) from error
        if self.color is not None:
            object.__setattr__(self, "color", _color(self.color, "Border color"))


BorderLineInput: TypeAlias = BorderLine | BorderLineStyle | str


def _line(value: BorderLineInput | None) -> BorderLine | None:
    if value is None or isinstance(value, BorderLine):
        return value
    return BorderLine(BorderLineStyle(value))


@final
@dataclasses.dataclass(frozen=True, slots=True)
class Borders:
    """Cell border sides."""

    top: BorderLine | None = None
    right: BorderLine | None = None
    bottom: BorderLine | None = None
    left: BorderLine | None = None

    def __post_init__(self) -> None:
        for name in ("top", "right", "bottom", "left"):
            object.__setattr__(self, name, _line(getattr(self, name)))


class VerticalAlignment(StrEnum):
    TOP = "top"
    CENTER = "center"
    BOTTOM = "bottom"


@final
@dataclasses.dataclass(frozen=True, slots=True)
class CellAlignment:
    """Horizontal, vertical, and wrapping alignment intent."""

    horizontal: Alignment | None = None
    vertical: VerticalAlignment | None = None
    wrap_text: bool | None = None

    def __post_init__(self) -> None:
        if self.horizontal is not None:
            object.__setattr__(self, "horizontal", Alignment(self.horizontal))
        if self.vertical is not None:
            object.__setattr__(self, "vertical", VerticalAlignment(self.vertical))


AlignmentInput: TypeAlias = CellAlignment | Alignment | str


def _validate_style_components(
    font: FontStyle | None,
    fill: FillStyle | None,
    border: Borders | None,
    alignment: CellAlignment | None,
    display_format: DisplayFormat | None,
) -> None:
    components = (
        (font, FontStyle, "font"),
        (fill, FillStyle, "fill"),
        (border, Borders, "border"),
        (alignment, CellAlignment, "alignment"),
    )
    for value, expected, label in components:
        if value is not None and not isinstance(value, expected):
            message = f"Style {label} has an invalid type"
            raise CaxtonTypeError(message)
    if display_format is not None and not isinstance(
        display_format,
        get_args(DisplayFormat),
    ):
        message = "Style display format has an invalid type"
        raise CaxtonTypeError(message)


@final
@dataclasses.dataclass(frozen=True, slots=True, init=False)
class Style:
    """Backend-independent cell presentation with constructor shorthands."""

    font: FontStyle | None = None
    fill: FillStyle | None = None
    border: Borders | None = None
    alignment: CellAlignment | None = None
    display_format: DisplayFormat | None = None
    font_color: str | None = dataclasses.field(
        default=None,
        compare=False,
        repr=False,
    )
    align: AlignmentInput | None = dataclasses.field(
        default=None,
        compare=False,
        repr=False,
    )
    border_top: BorderLineInput | None = dataclasses.field(
        default=None,
        compare=False,
        repr=False,
    )
    border_right: BorderLineInput | None = dataclasses.field(
        default=None,
        compare=False,
        repr=False,
    )
    border_bottom: BorderLineInput | None = dataclasses.field(
        default=None,
        compare=False,
        repr=False,
    )
    border_left: BorderLineInput | None = dataclasses.field(
        default=None,
        compare=False,
        repr=False,
    )

    def __init__(  # noqa: WPS211, WPS213
        self,
        *,
        font: FontStyle | None = None,
        fill: FillStyle | str | None = None,
        border: Borders | None = None,
        alignment: CellAlignment | None = None,
        display_format: DisplayFormat | None = None,
        font_color: str | None = None,
        align: AlignmentInput | None = None,
        border_top: BorderLineInput | None = None,
        border_right: BorderLineInput | None = None,
        border_bottom: BorderLineInput | None = None,
        border_left: BorderLineInput | None = None,
    ) -> None:
        if font_color is not None:
            font = _merge_font(font, FontStyle(color=_color(font_color, "Font color")))
        if align is not None:
            shorthand_alignment = (
                align
                if isinstance(align, CellAlignment)
                else CellAlignment(horizontal=Alignment(align))
            )
            alignment = _merge_alignment(alignment, shorthand_alignment)
        shorthand_border = Borders(
            top=_line(border_top),
            right=_line(border_right),
            bottom=_line(border_bottom),
            left=_line(border_left),
        )
        if any(dataclasses.astuple(shorthand_border)):
            border = _merge_borders(border, shorthand_border)
        normalized_fill = FillStyle(fill) if isinstance(fill, str) else fill
        _validate_style_components(
            font,
            normalized_fill,
            border,
            alignment,
            display_format,
        )
        object.__setattr__(self, "font", font)
        object.__setattr__(
            self,
            "fill",
            normalized_fill,
        )
        object.__setattr__(self, "border", border)
        object.__setattr__(self, "alignment", alignment)
        object.__setattr__(self, "display_format", display_format)
        object.__setattr__(
            self,
            "font_color",
            None if font_color is None else _color(font_color, "Font color"),
        )
        object.__setattr__(self, "align", align)
        object.__setattr__(self, "border_top", border_top)
        object.__setattr__(self, "border_right", border_right)
        object.__setattr__(self, "border_bottom", border_bottom)
        object.__setattr__(self, "border_left", border_left)

    def merged_over(self, base: Style | None) -> Style:
        """Return this style layered over ``base``."""
        if base is None:
            return self
        return Style(
            font=_merge_font(base.font, self.font),
            fill=self.fill if self.fill is not None else base.fill,
            border=_merge_borders(base.border, self.border),
            alignment=_merge_alignment(base.alignment, self.alignment),
            display_format=(
                self.display_format
                if self.display_format is not None
                else base.display_format
            ),
        )


StyleInput: TypeAlias = Style | str


@final
@dataclasses.dataclass(frozen=True, slots=True)
class StyleSheet(Mapping[str, Style]):
    """Immutable mapping of reusable style names to styles."""

    styles: Mapping[str, Style]

    def __post_init__(self) -> None:
        copied: dict[str, Style] = {}
        for name, style in self.styles.items():
            if not isinstance(name, str) or not name.strip():
                message = "Style name cannot be empty"
                raise CaxtonValueError(message)
            if not isinstance(style, Style):
                message = f"Style {name!r} must be a Style"
                raise CaxtonTypeError(message)
            copied[name] = style
        object.__setattr__(self, "styles", MappingProxyType(copied))

    def __getitem__(self, name: str) -> Style:
        return self.styles[name]

    def __iter__(self) -> Iterator[str]:
        return iter(self.styles)

    def __len__(self) -> int:
        return len(self.styles)

    def __hash__(self) -> int:
        return hash(frozenset(self.styles.items()))


@final
@dataclasses.dataclass(frozen=True, slots=True)
class DocumentTheme:
    """Document defaults, inherited in default → table/column → role order."""

    default: Style = Style()
    header: Style = Style(font=FontStyle(bold=True))
    total: Style = Style(font=FontStyle(bold=True))


def _merge_font(base: FontStyle | None, override: FontStyle | None) -> FontStyle | None:
    if override is None:
        return base
    if base is None:
        return override
    return FontStyle(
        name=override.name if override.name is not None else base.name,
        size=override.size if override.size is not None else base.size,
        bold=override.bold if override.bold is not None else base.bold,
        italic=override.italic if override.italic is not None else base.italic,
        underline=(
            override.underline if override.underline is not None else base.underline
        ),
        color=override.color if override.color is not None else base.color,
    )


def _merge_borders(base: Borders | None, override: Borders | None) -> Borders | None:
    if override is None:
        return base
    if base is None:
        return override
    return Borders(
        top=override.top if override.top is not None else base.top,
        right=override.right if override.right is not None else base.right,
        bottom=override.bottom if override.bottom is not None else base.bottom,
        left=override.left if override.left is not None else base.left,
    )


def _merge_alignment(
    base: CellAlignment | None,
    override: CellAlignment | None,
) -> CellAlignment | None:
    if override is None:
        return base
    if base is None:
        return override
    return CellAlignment(
        horizontal=(
            override.horizontal if override.horizontal is not None else base.horizontal
        ),
        vertical=(
            override.vertical if override.vertical is not None else base.vertical
        ),
        wrap_text=(
            override.wrap_text if override.wrap_text is not None else base.wrap_text
        ),
    )


__all__ = (
    "BorderLine",
    "BorderLineStyle",
    "Borders",
    "CellAlignment",
    "DocumentTheme",
    "FillStyle",
    "FontStyle",
    "Style",
    "StyleInput",
    "StyleSheet",
    "VerticalAlignment",
)
