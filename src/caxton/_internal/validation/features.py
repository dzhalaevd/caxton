"""Validate styles, footers, grouping, aggregation, and matrix features."""

from __future__ import annotations

from caxton._internal.block_paths import iter_blocks_with_paths
from caxton._internal.validation.expressions import expression_references
from caxton.core.errors import ColumnNotFoundError, Notification
from caxton.core.formatting import StyleInput
from caxton.core.models import (
    AggregateExpr,
    Column,
    Expression,
    Matrix,
    SpreadsheetDocument,
    SpreadsheetTable,
    contains_aggregate,
    iter_tables,
)


def validate_spreadsheet_features(
    document: SpreadsheetDocument,
    notification: Notification,
) -> None:
    for worksheet in document.worksheets:
        for index, table in enumerate(iter_tables(worksheet.blocks)):
            path = f'worksheet["{worksheet.name}"].table[{index}]'
            _validate_table(table, document, path, notification)
        for block, block_path in iter_blocks_with_paths(worksheet.blocks):
            if isinstance(block, Matrix):
                _validate_matrix(
                    block,
                    document,
                    f'worksheet["{worksheet.name}"].{block_path}',
                    notification,
                )


def _validate_table(
    table: SpreadsheetTable,
    document: SpreadsheetDocument,
    path: str,
    notification: Notification,
) -> None:
    _validate_style_ref(table.style, document, f"{path}.style", notification)
    _validate_style_ref(
        table.header_style,
        document,
        f"{path}.header_style",
        notification,
    )
    for column in table.columns:
        _validate_style_ref(
            column.style_ref,
            document,
            f'{path}.column["{column.id}"].style',
            notification,
        )
    _validate_footer(table, document, path, notification)
    for rule_index, rule in enumerate(table.rules):
        _validate_style_ref(
            rule.style,
            document,
            f"{path}.rule[{rule_index}].style",
            notification,
        )
    _validate_grouping_and_aggregation(table, path, notification)


def _validate_footer(
    table: SpreadsheetTable,
    document: SpreadsheetDocument,
    path: str,
    notification: Notification,
) -> None:
    footer = table.footer
    if footer is None:
        return
    footer_path = f"{path}.footer"
    _validate_style_ref(
        footer.style,
        document,
        f"{footer_path}.style",
        notification,
    )
    column_ids = {column.id for column in table.columns}
    targets = [item.column for item in footer.items]
    _validate_footer_targets(targets, column_ids, footer_path, notification)
    _validate_footer_label(
        footer.label_column,
        targets,
        column_ids,
        footer_path,
        notification,
    )


def _validate_footer_targets(
    targets: list[str],
    column_ids: set[str],
    path: str,
    notification: Notification,
) -> None:
    for target in targets:
        if target not in column_ids:
            notification.add(  # noqa: WPS220
                ColumnNotFoundError(column=target, path=path),
            )
    if len(targets) != len(set(targets)):
        notification.add(
            "Totals footer contains duplicate target columns",
            path=path,
            code="duplicate_total",
        )


def _validate_footer_label(
    label_column: str | None,
    targets: list[str],
    column_ids: set[str],
    path: str,
    notification: Notification,
) -> None:
    if set(targets) == column_ids or (
        label_column is not None and label_column in targets
    ):
        notification.add(
            "Totals label needs a column without an aggregate",
            path=path,
            code="total_label_conflict",
        )
    if label_column is not None and label_column not in column_ids:
        notification.add(
            ColumnNotFoundError(column=label_column, path=path),
        )


def _validate_grouping_and_aggregation(
    table: SpreadsheetTable,
    path: str,
    notification: Notification,
) -> None:
    grouped = tuple(column for column in table.columns if column.grouping is not None)
    aggregates = tuple(
        column for column in table.columns if isinstance(column.source, AggregateExpr)
    )
    nested = tuple(
        column
        for column in table.columns
        if isinstance(column.source, Expression)
        and not isinstance(column.source, AggregateExpr)
        and contains_aggregate(column.source)
    )
    for column in nested:
        notification.add(
            "Aggregate expressions must be the complete Python column source",
            path=f'{path}.column["{column.id}"].source',
            code="nested_aggregate_expression",
        )
    if not grouped and not aggregates:
        return
    if table.name is not None:
        notification.add(
            "Grouped or aggregate tables cannot be native named tables",
            path=f"{path}.name",
            code="transformed_named_table",
        )
    _validate_group_columns(grouped, path, notification)
    if aggregates:
        _validate_aggregate_scope(table, path, notification)
    _validate_merged_autofilter(table, grouped, path, notification)


def _validate_group_columns(
    grouped: tuple[Column, ...],
    path: str,
    notification: Notification,
) -> None:
    for column in grouped:
        if column.excel_formula is not None:
            notification.add(
                "Formula-backed columns cannot define groups",
                path=f'{path}.column["{column.id}"].grouping',
                code="formula_group",
            )
        if isinstance(column.source, AggregateExpr):
            notification.add(
                "An aggregate column cannot also define a group",
                path=f'{path}.column["{column.id}"]',
                code="aggregate_group_conflict",
            )


def _validate_aggregate_scope(
    table: SpreadsheetTable,
    path: str,
    notification: Notification,
) -> None:
    for column in table.columns:
        if (
            column.excel_formula is None
            and column.grouping is None
            and not isinstance(column.source, AggregateExpr)
        ):
            notification.add(
                "Output column has no single value in an aggregate scope; "
                "group it, aggregate it, or inline it into an aggregate",
                path=f'{path}.column["{column.id}"]',
                code="ambiguous_aggregate_scope",
            )


def _validate_merged_autofilter(
    table: SpreadsheetTable,
    grouped: tuple[Column, ...],
    path: str,
    notification: Notification,
) -> None:
    if table.autofilter and any(
        column.grouping is not None and column.grouping.merge for column in grouped
    ):
        notification.add(
            "Autofilter is incompatible with merged group cells",
            path=f"{path}.autofilter",
            code="merged_group_autofilter",
        )


def _validate_matrix(
    matrix: Matrix,
    document: SpreadsheetDocument,
    path: str,
    notification: Notification,
) -> None:
    _validate_style_ref(matrix.style, document, f"{path}.style", notification)
    _validate_style_ref(
        matrix.header_style,
        document,
        f"{path}.header_style",
        notification,
    )
    columns = (*matrix.row_dimensions, *matrix.column_dimensions, matrix.value)
    for column in columns:
        _validate_style_ref(
            column.style_ref,
            document,
            f'{path}.column["{column.id}"].style',
            notification,
        )
        if not isinstance(column.source, Expression):
            continue
        for reference in expression_references(column.source):
            notification.add(
                "Matrix expressions cannot reference table columns",
                path=f'{path}.column["{column.id}"].source',
                code="matrix_column_reference",
                context={"column": reference},
            )


def _validate_style_ref(
    value: StyleInput | None,
    document: SpreadsheetDocument,
    path: str,
    notification: Notification,
) -> None:
    if isinstance(value, str) and value not in document.styles:
        notification.add(
            f"Style {value!r} was not found",
            path=path,
            code="style_not_found",
            context={"style": value},
        )


__all__ = ("validate_spreadsheet_features",)
