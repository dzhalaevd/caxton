from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import Any

from caxton._internal.data import coerce_data_source
from caxton.core.formatting import DocumentTheme, Style, StyleInput, StyleSheet
from caxton.core.models import (
    DEFAULT_OBJECT_HEIGHT,
    DEFAULT_OBJECT_WIDTH,
    BlockDirection,
    Chart,
    ChartKind,
    Column,
    ConditionalRule,
    Expression,
    FieldRef,
    Freeze,
    Image,
    Matrix,
    Spacer,
    SpreadsheetBlock,
    SpreadsheetDocument,
    SpreadsheetTable,
    Stack,
    TableData,
    TableReference,
    Title,
    Total,
    Totals,
    Worksheet,
)
from caxton.core.models.columns import make_column
from caxton.core.types import Text

MatrixAxisInput = Column | Expression | Sequence[Column | Expression]
MatrixValueInput = Column | Expression


def table(  # noqa: WPS211
    rows: object,
    *columns: Column,
    name: str | None = None,
    anchor: str | None = None,
    style: StyleInput | None = None,
    header_style: StyleInput | None = None,
    footer: Totals | Sequence[Total] | None = None,
    rules: Sequence[ConditionalRule] = (),
    autofilter: bool = False,
    freeze_header: bool = False,
    auto_width: bool = False,
) -> SpreadsheetTable:
    """Create a spreadsheet table without consuming its row source.

    ``footer`` accepts either a ready ``Totals`` row or a bare sequence of
    ``Total`` aggregates.

    Returns:
        An immutable spreadsheet table specification.
    """
    source = coerce_data_source(rows)
    return SpreadsheetTable(
        data=TableData(source=source, columns=tuple(columns)),
        name=name,
        anchor=anchor,
        style=style,
        header_style=header_style,
        footer=_resolve_footer(footer),
        rules=tuple(rules),
        autofilter=autofilter,
        freeze_header=freeze_header,
        auto_width=auto_width,
    )


def matrix(  # noqa: WPS211
    rows: object,
    *,
    row: MatrixAxisInput,
    column: MatrixAxisInput,
    value: MatrixValueInput,
    anchor: str | None = None,
    style: StyleInput | None = None,
    header_style: StyleInput | None = None,
) -> Matrix:
    """Create a pivot-like matrix without pre-transforming its row source.

    Returns:
        An immutable matrix specification.
    """
    used_ids: set[str] = set()
    row_dimensions = _matrix_dimensions(row, prefix="row", used_ids=used_ids)
    column_dimensions = _matrix_dimensions(
        column,
        prefix="column",
        used_ids=used_ids,
    )
    return Matrix(
        source=coerce_data_source(rows),
        row_dimensions=row_dimensions,
        column_dimensions=column_dimensions,
        value=_matrix_value(value, used_ids),
        anchor=anchor,
        style=style,
        header_style=header_style,
    )


def _matrix_dimensions(
    value: MatrixAxisInput,
    *,
    prefix: str,
    used_ids: set[str],
) -> tuple[Column, ...]:
    items = (value,) if isinstance(value, (Column, Expression)) else tuple(value)
    output: list[Column] = []
    for index, item in enumerate(items):
        if isinstance(item, Column):
            column = item
        else:
            column = make_column(
                _unique_id(_expression_id(item, prefix, index), used_ids),
                Text(),
                item,
            )
        output.append(column)
        used_ids.add(column.id)
    return tuple(output)


def _matrix_value(value: MatrixValueInput, used_ids: set[str]) -> Column:
    if isinstance(value, Column):
        return value
    return make_column(_unique_id("value", used_ids), Text(), value)


def _expression_id(expression: Expression, prefix: str, index: int) -> str:
    return expression.name if isinstance(expression, FieldRef) else f"{prefix}_{index}"


def _unique_id(candidate: str, used_ids: set[str]) -> str:
    column_id = candidate
    suffix = 2
    while column_id in used_ids:
        column_id = f"{candidate}_{suffix}"
        suffix += 1
    return column_id


def title(
    text: str,
    *,
    level: int = 1,
    span: int = 1,
    style: StyleInput | None = None,
    anchor: str | None = None,
) -> Title:
    """Create a heading block occupying one worksheet row.

    Returns:
        An immutable title block.
    """
    return Title(text=text, level=level, span=span, style=style, anchor=anchor)


def spacer(rows: int = 1, *, columns: int = 1, anchor: str | None = None) -> Spacer:
    """Create an empty layout gap of whole rows and columns.

    Returns:
        An immutable spacer block.
    """
    return Spacer(rows=rows, columns=columns, anchor=anchor)


def image(  # noqa: WPS211
    source: str | os.PathLike[str] | bytes,
    *,
    width: int = DEFAULT_OBJECT_WIDTH,
    height: int = DEFAULT_OBJECT_HEIGHT,
    name: str | None = None,
    description: str | None = None,
    anchor: str | None = None,
) -> Image:
    """Create a picture block sized in pixels instead of cell coordinates.

    Returns:
        An immutable image block.
    """
    return Image(
        source=source if isinstance(source, bytes) else os.fspath(source),
        width=width,
        height=height,
        name=name,
        description=description,
        anchor=anchor,
    )


def chart(  # noqa: WPS211
    source: TableReference,
    *,
    x: str,  # noqa: WPS111
    y: str | Sequence[str],  # noqa: WPS111
    kind: ChartKind | str = ChartKind.COLUMN,
    title: str | None = None,  # noqa: WPS442
    width: int = DEFAULT_OBJECT_WIDTH,
    height: int = DEFAULT_OBJECT_HEIGHT,
    name: str | None = None,
    anchor: str | None = None,
) -> Chart:
    """Create a chart bound to columns of one named table.

    Returns:
        An immutable chart block.
    """
    return Chart(
        source,
        x=x,
        y=y,
        kind=kind,
        title=title,
        width=width,
        height=height,
        name=name,
        anchor=anchor,
    )


def stack(
    *items: SpreadsheetBlock,
    direction: BlockDirection | str = BlockDirection.VERTICAL,
    gap: int = 0,
    anchor: str | None = None,
) -> Stack:
    """Create a flow container placing nested blocks one after another.

    Returns:
        An immutable stack block.
    """
    return Stack(
        items=tuple(items),
        direction=direction,
        gap=gap,
        anchor=anchor,
    )


def sheet(
    name: str,
    *blocks: SpreadsheetBlock,
    freeze: Freeze | None = None,
) -> Worksheet:
    """Create a worksheet from declared blocks in layout order.

    Returns:
        An immutable worksheet.
    """
    return Worksheet(name=name, blocks=tuple(blocks), freeze=freeze)


def spreadsheet(
    *worksheets: Worksheet,
    metadata: Mapping[str, Any] | None = None,
    styles: StyleSheet | Mapping[str, Style] | None = None,
    theme: DocumentTheme | None = None,
) -> SpreadsheetDocument:
    """Create a spreadsheet document from declared worksheets.

    Returns:
        An immutable spreadsheet document.
    """
    style_sheet = styles if isinstance(styles, StyleSheet) else StyleSheet(styles or {})
    return SpreadsheetDocument(
        worksheets=tuple(worksheets),
        metadata={} if metadata is None else metadata,
        styles=style_sheet,
        theme=theme or DocumentTheme(),
    )


def _resolve_footer(footer: Totals | Sequence[Total] | None) -> Totals | None:
    if footer is None or isinstance(footer, Totals):
        return footer
    return Totals(items=tuple(footer))


__all__ = (
    "MatrixAxisInput",
    "MatrixValueInput",
    "chart",
    "image",
    "matrix",
    "sheet",
    "spacer",
    "spreadsheet",
    "stack",
    "table",
    "title",
)
