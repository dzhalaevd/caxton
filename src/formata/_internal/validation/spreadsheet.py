from __future__ import annotations

import dataclasses
from collections.abc import Iterator, Sequence
from functools import singledispatch

from formata._internal.layout import plan_worksheet
from formata._internal.normalization.coordinates import parse_cell_address
from formata.core.errors import (
    ColumnNotFoundError,
    DuplicateColumnError,
    Notification,
    UnsupportedFeatureError,
)
from formata.core.formatting import StyleInput
from formata.core.models import (
    BinaryExpression,
    CellReference,
    Chart,
    Column,
    ColumnRef,
    Expression,
    Formula,
    FormulaBinary,
    FormulaLiteral,
    RangeReference,
    SpreadsheetBlock,
    SpreadsheetDocument,
    SpreadsheetTable,
    Worksheet,
    iter_blocks,
    iter_tables,
)
from formata.core.protocols import DataSourceInfo

FormulaNode = tuple[int, int, str]


def validate_spreadsheet(document: SpreadsheetDocument) -> None:
    """Validate a spreadsheet graph without reading any data source."""
    notification = Notification()
    _validate_document_shape(document, notification)
    _validate_worksheet_names(document, notification)
    _validate_tables(document, notification)
    _validate_spreadsheet_features(document, notification)
    _validate_formula_references(document, notification)
    _validate_chart_sources(document, notification)
    _validate_placement(document, notification)
    notification.raise_if_errors("Spreadsheet structural validation failed")


def _validate_placement(
    document: SpreadsheetDocument,
    notification: Notification,
) -> None:
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


def _validate_chart_sources(
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
        for index, block in enumerate(iter_blocks(worksheet.blocks)):
            if isinstance(block, Chart):
                _validate_chart(
                    block,
                    tables,
                    path=f'worksheet["{worksheet.name}"].chart[{index}]',
                    notification=notification,
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


def _validate_document_shape(
    document: SpreadsheetDocument,
    notification: Notification,
) -> None:
    if not document.worksheets:
        notification.add(
            "Spreadsheet must contain at least one worksheet",
            path="spreadsheet",
            code="missing_worksheet",
        )


def _validate_worksheet_names(
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


def _validate_tables(
    document: SpreadsheetDocument,
    notification: Notification,
) -> None:
    table_names: set[str] = set()
    for worksheet in document.worksheets:
        for index, block in enumerate(iter_blocks(worksheet.blocks)):
            block_path = f'worksheet["{worksheet.name}"].block[{index}]'
            _validate_anchor(block, block_path, notification)
        for table_index, table in enumerate(iter_tables(worksheet.blocks)):
            table_path = f'worksheet["{worksheet.name}"].table[{table_index}]'
            _validate_table_name(table, table_path, table_names, notification)
            _validate_columns(table.columns, table_path, notification)


def _validate_spreadsheet_features(  # noqa: C901
    document: SpreadsheetDocument,
    notification: Notification,
) -> None:
    for worksheet in document.worksheets:
        for index, table in enumerate(iter_tables(worksheet.blocks)):
            path = f'worksheet["{worksheet.name}"].table[{index}]'
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
            if table.footer is not None:
                _validate_style_ref(
                    table.footer.style,
                    document,
                    f"{path}.footer.style",
                    notification,
                )
                column_ids = {column.id for column in table.columns}
                targets = [item.column for item in table.footer.items]
                for target in targets:
                    if target not in column_ids:
                        notification.add(  # noqa: WPS220
                            ColumnNotFoundError(
                                column=target,
                                path=f"{path}.footer",
                            ),
                        )
                if len(targets) != len(set(targets)):
                    notification.add(
                        "Totals footer contains duplicate target columns",
                        path=f"{path}.footer",
                        code="duplicate_total",
                    )
                label_column = table.footer.label_column
                if set(targets) == column_ids or (
                    label_column is not None and label_column in targets
                ):
                    notification.add(
                        "Totals label needs a column without an aggregate",
                        path=f"{path}.footer",
                        code="total_label_conflict",
                    )
                if label_column is not None and label_column not in column_ids:
                    notification.add(
                        ColumnNotFoundError(column=label_column, path=f"{path}.footer"),
                    )
            for rule_index, rule in enumerate(table.rules):
                _validate_style_ref(
                    rule.style,
                    document,
                    f"{path}.rule[{rule_index}].style",
                    notification,
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


def _validate_columns(
    columns: Sequence[Column],
    table_path: str,
    notification: Notification,
) -> None:
    if not columns:
        notification.add(
            "Table must contain at least one column",
            path=table_path,
            code="missing_column",
        )
        return
    identifiers = {column.id for column in columns}
    formula_identifiers = {
        column.id for column in columns if column.excel_formula is not None
    }
    seen: set[str] = set()
    dependencies: dict[str, tuple[str, ...]] = {}
    for column in columns:
        column_path = f'{table_path}.column["{column.id}"]'
        if column.id in seen:
            notification.add(
                DuplicateColumnError(column=column.id, path=column_path),
            )
        seen.add(column.id)
        references = tuple(_column_references(column))
        dependencies[column.id] = tuple(
            reference for reference in references if reference in identifiers
        )
        for reference in references:
            _validate_python_reference(
                reference,
                identifiers=identifiers,
                formula_identifiers=formula_identifiers,
                path=f"{column_path}.source",
                notification=notification,
            )
    _validate_cycles(dependencies, table_path, notification)


def _validate_python_reference(
    reference: str,
    *,
    identifiers: set[str],
    formula_identifiers: set[str],
    path: str,
    notification: Notification,
) -> None:
    if reference not in identifiers:
        notification.add(ColumnNotFoundError(column=reference, path=path))
        return
    if reference in formula_identifiers:
        notification.add(
            "Python expressions cannot read formula-backed columns",
            path=path,
            code="formula_in_python_expression",
            context={"column": reference},
        )


def _column_references(column: Column) -> Iterator[str]:
    if isinstance(column.source, Expression):
        yield from _expression_references(column.source)


@singledispatch
def _expression_references(_expression: Expression) -> Iterator[str]:
    return iter(())


@_expression_references.register
def _column_reference(expression: ColumnRef) -> Iterator[str]:
    yield expression.column_id


@_expression_references.register
def _binary_references(expression: BinaryExpression) -> Iterator[str]:
    yield from _expression_references(expression.left)
    yield from _expression_references(expression.right)


def _validate_cycles(
    dependencies: dict[str, tuple[str, ...]],
    table_path: str,
    notification: Notification,
) -> None:
    state = _CycleState(
        dependencies=dependencies,
        table_path=table_path,
        notification=notification,
    )
    for column_id in dependencies:
        _visit_column(column_id, state)


def _validate_formula_references(
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
        id(table): (worksheet_index, table_index)
        for worksheet_index, worksheet in enumerate(document.worksheets)
        for table_index, table in enumerate(iter_tables(worksheet.blocks))
    }
    dependencies: dict[FormulaNode, set[FormulaNode]] = {}
    paths: dict[FormulaNode, str] = {}
    for worksheet_index, worksheet in enumerate(document.worksheets):
        for table_index, table in enumerate(iter_tables(worksheet.blocks)):
            table_path = f'worksheet["{worksheet.name}"].table[{table_index}]'
            for column in table.columns:
                if column.excel_formula is None:
                    continue
                formula_path = f'{table_path}.column["{column.id}"].formula'
                node = (worksheet_index, table_index, column.id)
                dependencies[node] = set()
                paths[node] = formula_path
                _validate_column_formula(
                    column,
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
    _validate_formula_cycles(dependencies, paths, notification)


def _validate_column_formula(  # noqa: WPS211
    column: Column,
    *,
    node: FormulaNode,
    path: str,
    worksheet: Worksheet,
    table: SpreadsheetTable,
    worksheets: dict[str, Worksheet],
    tables: dict[str, tuple[Worksheet, SpreadsheetTable]],
    table_keys: dict[int, tuple[int, int]],
    dependencies: dict[FormulaNode, set[FormulaNode]],
    notification: Notification,
) -> None:
    if column.excel_formula is None:
        return
    _validate_formula(
        column.excel_formula,
        node=node,
        path=path,
        worksheet=worksheet,
        table=table,
        worksheets=worksheets,
        tables=tables,
        table_keys=table_keys,
        dependencies=dependencies,
        notification=notification,
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
    table_keys: dict[int, tuple[int, int]],
    dependencies: dict[FormulaNode, set[FormulaNode]],
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
            target_key = table_keys[id(target_table)]
            dependencies[node].add((*target_key, target_column.id))


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


def _validate_formula_cycles(
    dependencies: dict[FormulaNode, set[FormulaNode]],
    paths: dict[FormulaNode, str],
    notification: Notification,
) -> None:
    completed: set[FormulaNode] = set()
    active: set[FormulaNode] = set()

    def visit(node: FormulaNode) -> None:
        if node in completed:
            return
        if node in active:
            notification.add(
                f"Cyclic formula reference involving column {node[2]!r}",
                path=paths[node],
                code="cyclic_formula_reference",
                context={"column": node[2]},
            )
            return
        active.add(node)
        for dependency in dependencies.get(node, set()):
            visit(dependency)
        active.discard(node)
        completed.add(node)

    for node in dependencies:
        visit(node)


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
def _formula_literal_references(
    _formula: FormulaLiteral,
) -> Iterator[CellReference | RangeReference]:
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


@dataclasses.dataclass(slots=True)
class _CycleState:
    dependencies: dict[str, tuple[str, ...]]
    table_path: str
    notification: Notification
    completed: set[str] = dataclasses.field(default_factory=set)
    active: set[str] = dataclasses.field(default_factory=set)


def _visit_column(
    column_id: str,
    state: _CycleState,
) -> None:
    if column_id in state.completed:
        return
    if column_id in state.active:
        state.notification.add(
            f"Cyclic column reference involving {column_id!r}",
            path=f'{state.table_path}.column["{column_id}"].source',
            code="cyclic_column_reference",
            context={"column": column_id},
        )
        return
    state.active.add(column_id)
    for dependency in state.dependencies[column_id]:
        _visit_column(dependency, state)
    state.active.discard(column_id)
    state.completed.add(column_id)


__all__ = ("validate_spreadsheet",)
