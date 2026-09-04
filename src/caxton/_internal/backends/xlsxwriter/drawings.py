"""Render Spreadsheet IR images and charts with XlsxWriter."""

from __future__ import annotations

from io import BytesIO

import xlsxwriter  # type: ignore[import-untyped]
from xlsxwriter.image import Image as XlsxImage  # type: ignore[import-untyped]
from xlsxwriter.worksheet import Worksheet  # type: ignore[import-untyped]

from caxton._internal.backends._xlsx_values import validate_xlsx_text
from caxton._internal.backends.xlsxwriter.styles import style_format
from caxton._internal.const import _CHART_TYPES
from caxton.core.errors import RenderError
from caxton.core.ir import (
    CellRange,
    SpreadsheetChartIR,
    SpreadsheetImageIR,
    SpreadsheetTextIR,
)


def render_text(
    workbook: xlsxwriter.Workbook,
    worksheet: Worksheet,
    text: SpreadsheetTextIR,
) -> None:
    """Render a text block into a worksheet."""
    row = text.anchor.row - 1
    column = text.anchor.column - 1
    cell_format = style_format(workbook, text.style)
    literal = validate_xlsx_text(text.text, role="title")
    if text.span > 1:
        worksheet.merge_range(
            row,
            column,
            row,
            column + text.span - 1,
            literal,
            cell_format,
        )
        return
    worksheet.write_string(row, column, literal, cell_format)


def render_image(worksheet: Worksheet, picture: SpreadsheetImageIR) -> None:
    """Render an image block into a worksheet.

    Image sources are read here, at rendering time, so a path that has moved
    since the document was described fails with the path in the error context.

    Raises:
        RenderError: If the image source cannot be read.
    """
    source = picture.source
    filename = source if isinstance(source, str) else f"{picture.name or 'image'}.png"
    options: dict[str, object] = {}
    if isinstance(source, bytes):
        options["image_data"] = BytesIO(source)
    if picture.description is not None:
        options["description"] = picture.description
    try:
        natural = _natural_size(source)
        if natural is not None:
            options["x_scale"] = picture.width / natural[0]
            options["y_scale"] = picture.height / natural[1]
        worksheet.insert_image(
            picture.anchor.row - 1,
            picture.anchor.column - 1,
            filename,
            options,
        )
    except OSError as error:
        message = "Image source could not be read"
        raise RenderError(
            message,
            context=_unreadable_image_context(picture, error),
        ) from error


def _unreadable_image_context(
    picture: SpreadsheetImageIR,
    error: OSError,
) -> dict[str, object]:
    context: dict[str, object] = {"exception_type": type(error).__name__}
    if isinstance(picture.source, str):
        context["source"] = picture.source
    if picture.name is not None:
        context["image"] = picture.name
    return context


def _natural_size(source: str | bytes) -> tuple[float, float] | None:
    probe = XlsxImage(BytesIO(source) if isinstance(source, bytes) else source)
    width = float(probe.width)
    height = float(probe.height)
    return (width, height) if width and height else None


def render_chart(
    workbook: xlsxwriter.Workbook,
    worksheet: Worksheet,
    chart: SpreadsheetChartIR,
) -> None:
    """Render a chart block into a worksheet.

    Raises:
        ValueError: If XlsxWriter rejects the compiled chart kind.
    """
    native = workbook.add_chart({"type": _CHART_TYPES[chart.kind]})
    if native is None:
        message = f"XlsxWriter rejected chart kind {chart.kind.value!r}"
        raise ValueError(message)
    for series in chart.series:
        native.add_series(
            {
                "name": series.name,
                "categories": _range_reference(chart.sheet_name, series.categories),
                "values": _range_reference(chart.sheet_name, series.values),
            },
        )
    if chart.title is not None:
        native.set_title({"name": chart.title})
    native.set_size({"width": chart.width, "height": chart.height})
    worksheet.insert_chart(
        chart.anchor.row - 1,
        chart.anchor.column - 1,
        native,
    )


def _range_reference(
    sheet_name: str,
    cell_range: CellRange | None,
) -> list[object] | None:
    if cell_range is None:
        return None
    return [
        sheet_name,
        cell_range.start.row - 1,
        cell_range.start.column - 1,
        cell_range.end.row - 1,
        cell_range.end.column - 1,
    ]


__all__ = ("render_chart", "render_image", "render_text")
