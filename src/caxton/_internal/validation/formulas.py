"""Validate spreadsheet formula references, rows, and dependency cycles."""

from __future__ import annotations

from collections.abc import Iterator
from functools import singledispatch

from caxton.core.errors import ColumnNotFoundError, Notification
from caxton.core.models import (
    CellReference,
    Formula,
    FormulaBinary,
    RangeReference,
    SpreadsheetDocument,
    SpreadsheetTable,
    Worksheet,
    iter_tables,
)
from caxton.core.protocols import DataSourceInfo

from .cycles import report_reference_cycles

FormulaNode = tuple[int, int, str]


def validate_formula_references(
    document: SpreadsheetDocument,
    notification: Notification,
) -> None:
    worksheets = {worksheet.name: worksheet for worksheet in document.worksheets}
    tables = {
        table.name: (worksheet, table)
        for worksheet in document.worksheets
        for table in iter_tables(worksheet.blocks)
        if table.name is not None
    }
    table_keys = {
        table: (worksheet_index, table_index)
        for worksheet_index, worksheet in enumerate(document.worksheets)
        for table_index, table in enumerate(iter_tables(worksheet.blocks))
    }
    dependencies: dict[FormulaNode, dict[FormulaNode, None]] = {}
    paths: dict[FormulaNode, str] = {}
    for worksheet_index, worksheet in enumerate(document.worksheets):
        for table_index, table in enumerate(iter_tables(worksheet.blocks)):
            table_path = f'worksheet["{worksheet.name}"].table[{table_index}]'
            for column in table.columns:
                if column.excel_formula is None:
                    continue
                formula_path = f'{table_path}.column["{column.id}"].formula'
                node = (worksheet_index, table_index, column.id)
                dependencies[node] = {}
                paths[node] = formula_path
                _validate_formula(
                    column.excel_formula,
                    node=node,
                    path=formula_path,
                    worksheet=worksheet,
                    table=table,
                    worksheets=worksheets,
                    tables=tables,
                    table_keys=table_keys,
                    dependencies=dependencies,
                    notification=notification,
                )
            for rule_index, rule in enumerate(table.rules):
                _validate_formula(
                    rule.condition,
                    node=None,
                    path=f"{table_path}.rule[{rule_index}].condition",
                    worksheet=worksheet,
                    table=table,
                    worksheets=worksheets,
                    tables=tables,
                    table_keys=table_keys,
                    dependencies=dependencies,
                    notification=notification,
                )
    report_reference_cycles(
        dependencies,
        paths,
        {node: node[2] for node in dependencies},
        notification,
    )


def _validate_formula(  # noqa: WPS211
    formula: Formula,
    *,
    node: FormulaNode | None,
    path: str,
    worksheet: Worksheet,
    table: SpreadsheetTable,
    worksheets: dict[str, Worksheet],
    tables: dict[str, tuple[Worksheet, SpreadsheetTable]],
    table_keys: dict[SpreadsheetTable, tuple[int, int]],
    dependencies: dict[FormulaNode, dict[FormulaNode, None]],
    notification: Notification,
) -> None:
    for reference in _formula_references(formula):
        target = _resolve_formula_table(
            reference,
            worksheet=worksheet,
            table=table,
            worksheets=worksheets,
            tables=tables,
            path=path,
            notification=notification,
        )
        if target is None:
            continue
        _, target_table = target
        target_column = next(
            (item for item in target_table.columns if item.id == reference.column_id),
            None,
        )
        if target_column is None:
            notification.add(
                ColumnNotFoundError(column=reference.column_id, path=path),
            )
            continue
        _validate_reference_row(
            reference,
            table=target_table,
            path=path,
            notification=notification,
        )
        if node is not None and target_column.excel_formula is not None:
            target_key = table_keys[target_table]
            target_node = (*target_key, target_column.id)
            dependencies[node][target_node] = None


def _validate_reference_row(
    reference: CellReference | RangeReference,
    *,
    table: SpreadsheetTable,
    path: str,
    notification: Notification,
) -> None:
    if not isinstance(reference, CellReference) or reference.row_index is None:
        return
    source = table.data.source
    row_count = source.row_count if isinstance(source, DataSourceInfo) else None
    if row_count is None or reference.row_index < row_count:
        return
    notification.add(
        f"Semantic row {reference.row_index} was not found in table {table.name!r}",
        path=path,
        code="row_not_found",
        context={
            "table": table.name,
            "column": reference.column_id,
            "row": reference.row_index,
            "row_count": row_count,
        },
    )


def _resolve_formula_table(  # noqa: WPS211
    reference: CellReference | RangeReference,
    *,
    worksheet: Worksheet,
    table: SpreadsheetTable,
    worksheets: dict[str, Worksheet],
    tables: dict[str, tuple[Worksheet, SpreadsheetTable]],
    path: str,
    notification: Notification,
) -> tuple[Worksheet, SpreadsheetTable] | None:
    if reference.table_name is None:
        return worksheet, table
    if reference.sheet_name is not None:
        return _resolve_sheet_table(
            reference,
            worksheets=worksheets,
            path=path,
            notification=notification,
        )
    target = tables.get(reference.table_name)
    if target is not None:
        return target
    notification.add(
        f"Table {reference.table_name!r} was not found",
        path=path,
        code="table_not_found",
        context={"table": reference.table_name},
    )
    return None


def _resolve_sheet_table(
    reference: CellReference | RangeReference,
    *,
    worksheets: dict[str, Worksheet],
    path: str,
    notification: Notification,
) -> tuple[Worksheet, SpreadsheetTable] | None:
    assert reference.sheet_name is not None  # noqa: S101
    assert reference.table_name is not None  # noqa: S101
    target_worksheet = worksheets.get(reference.sheet_name)
    if target_worksheet is None:
        notification.add(
            f"Worksheet {reference.sheet_name!r} was not found",
            path=path,
            code="worksheet_not_found",
            context={"worksheet": reference.sheet_name},
        )
        return None
    for candidate in iter_tables(target_worksheet.blocks):
        if candidate.name == reference.table_name:
            return target_worksheet, candidate
    notification.add(
        f"Table {reference.table_name!r} was not found in worksheet "
        f"{reference.sheet_name!r}",
        path=path,
        code="table_not_found",
        context={
            "table": reference.table_name,
            "worksheet": reference.sheet_name,
        },
    )
    return None


@singledispatch
def _formula_references(_formula: Formula) -> Iterator[CellReference | RangeReference]:
    return iter(())


@_formula_references.register
def _formula_binary_references(
    formula: FormulaBinary,
) -> Iterator[CellReference | RangeReference]:
    yield from _formula_references(formula.left)
    yield from _formula_references(formula.right)


@_formula_references.register
def _cell_formula_reference(
    formula: CellReference,
) -> Iterator[CellReference | RangeReference]:
    yield formula


@_formula_references.register
def _range_formula_reference(
    formula: RangeReference,
) -> Iterator[CellReference | RangeReference]:
    yield formula


__all__ = ("validate_formula_references",)
