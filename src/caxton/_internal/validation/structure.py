"""Validate declared block structure, names, references, and placement."""

from __future__ import annotations

from caxton._internal.block_paths import iter_blocks_with_paths
from caxton._internal.layout import plan_worksheet
from caxton._internal.normalization.coordinates import parse_cell_address
from caxton._internal.validation.expressions import validate_columns
from caxton.core.errors import (
    ColumnNotFoundError,
    Notification,
    UnsupportedFeatureError,
)
from caxton.core.models import (
    Chart,
    SpreadsheetBlock,
    SpreadsheetDocument,
    SpreadsheetTable,
    iter_tables,
)


def validate_document_shape(
    document: SpreadsheetDocument,
    notification: Notification,
) -> None:
    if not document.worksheets:
        notification.add(
            "Spreadsheet must contain at least one worksheet",
            path="spreadsheet",
            code="missing_worksheet",
        )


def validate_worksheet_names(
    document: SpreadsheetDocument,
    notification: Notification,
) -> None:
    seen: set[str] = set()
    for index, worksheet in enumerate(document.worksheets):
        normalized = worksheet.name.casefold()
        if normalized in seen:
            notification.add(
                f"Duplicate worksheet name {worksheet.name!r}",
                path=f"worksheet[{index}]",
                code="duplicate_worksheet",
                context={"worksheet": worksheet.name},
            )
        seen.add(normalized)


def validate_tables(
    document: SpreadsheetDocument,
    notification: Notification,
) -> None:
    table_names: set[str] = set()
    for worksheet in document.worksheets:
        for block, block_path in iter_blocks_with_paths(worksheet.blocks):
            path = f'worksheet["{worksheet.name}"].{block_path}'
            _validate_anchor(block, path, notification)
        for table_index, table in enumerate(iter_tables(worksheet.blocks)):
            table_path = f'worksheet["{worksheet.name}"].table[{table_index}]'
            if table.into is not None and document.template is None:
                notification.add(
                    "Template target requires a document template",
                    path=f"{table_path}.into",
                    code="template_required",
                )
            _validate_table_name(table, table_path, table_names, notification)
            validate_columns(table.columns, table_path, notification)


def validate_chart_sources(
    document: SpreadsheetDocument,
    notification: Notification,
) -> None:
    tables = {
        table.name: table
        for worksheet in document.worksheets
        for table in iter_tables(worksheet.blocks)
        if table.name is not None
    }
    for worksheet in document.worksheets:
        for block, block_path in iter_blocks_with_paths(worksheet.blocks):
            if isinstance(block, Chart):
                _validate_chart(
                    block,
                    tables,
                    path=f'worksheet["{worksheet.name}"].{block_path}',
                    notification=notification,
                )


def validate_placement(
    document: SpreadsheetDocument,
    notification: Notification,
) -> None:
    if document.template is not None:
        return
    for worksheet in document.worksheets:
        try:
            plan = plan_worksheet(worksheet)
        except (UnsupportedFeatureError, ValueError):
            continue
        for overlap in plan.overlaps:
            notification.add(
                f"Blocks {overlap.first} and {overlap.second} overlap",
                path=f'worksheet["{worksheet.name}"].{overlap.first}',
                code="block_overlap",
                context={
                    "first": overlap.first,
                    "second": overlap.second,
                    "worksheet": worksheet.name,
                },
            )


def _validate_chart(
    chart: Chart,
    tables: dict[str, SpreadsheetTable],
    *,
    path: str,
    notification: Notification,
) -> None:
    table = tables.get(chart.source.name)
    if table is None:
        notification.add(
            f"Table {chart.source.name!r} was not found",
            path=f"{path}.source",
            code="table_not_found",
            context={"table": chart.source.name},
        )
        return
    column_ids = {column.id for column in table.columns}
    for column_id in (chart.x, *chart.y):
        if column_id not in column_ids:
            notification.add(ColumnNotFoundError(column=column_id, path=path))


def _validate_table_name(
    table: SpreadsheetTable,
    path: str,
    seen: set[str],
    notification: Notification,
) -> None:
    if table.name is None:
        return
    normalized = table.name.casefold()
    if normalized in seen:
        notification.add(
            f"Duplicate table name {table.name!r}",
            path=path,
            code="duplicate_table",
            context={"table": table.name},
        )
    seen.add(normalized)


def _validate_anchor(
    block: SpreadsheetBlock,
    path: str,
    notification: Notification,
) -> None:
    if block.anchor is None:
        return
    try:
        parse_cell_address(block.anchor)
    except ValueError:
        notification.add(
            f"Invalid block anchor {block.anchor!r}",
            path=f"{path}.anchor",
            code="invalid_anchor",
            context={"anchor": block.anchor},
        )


__all__ = (
    "validate_chart_sources",
    "validate_document_shape",
    "validate_placement",
    "validate_tables",
    "validate_worksheet_names",
)
