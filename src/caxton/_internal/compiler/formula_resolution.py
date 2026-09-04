"""Resolve semantic formula references against placed spreadsheet tables."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator

from caxton._internal.layout import DocumentPlan, WorksheetPlan
from caxton.core.errors import UnsupportedFeatureError
from caxton.core.ir import (
    CellAddress,
    CellRange,
    ResolvedCellReference,
    ResolvedFormula,
    ResolvedFormulaBinary,
    ResolvedFormulaLiteral,
    ResolvedRangeReference,
)
from caxton.core.models import (
    CellReference,
    Column,
    Formula,
    FormulaBinary,
    FormulaLiteral,
    RangeReference,
    SpreadsheetDocument,
    SpreadsheetTable,
    TableReference,
    Worksheet,
)
from caxton.core.protocols import DataSourceInfo


@dataclasses.dataclass(frozen=True, slots=True)
class TableLocation:
    worksheet: Worksheet
    table: SpreadsheetTable
    anchor: CellAddress


@dataclasses.dataclass(frozen=True, slots=True)
class ColumnLocation:
    column: Column
    offset: int


@dataclasses.dataclass(frozen=True, slots=True)
class FormulaCatalog:
    by_name: dict[str, TableLocation]
    by_sheet_and_name: dict[tuple[str, str], TableLocation]

    @classmethod
    def from_document(
        cls,
        document: SpreadsheetDocument,
        plan: DocumentPlan,
    ) -> FormulaCatalog:
        locations = tuple(
            TableLocation(worksheet=worksheet, table=table, anchor=anchor)
            for worksheet, worksheet_plan in zip(
                document.worksheets,
                plan.worksheets,
                strict=True,
            )
            for table, anchor in _placed_tables(worksheet_plan)
            if table.name is not None
        )
        return cls(
            by_name={_location_name(location): location for location in locations},
            by_sheet_and_name={
                (location.worksheet.name, _location_name(location)): location
                for location in locations
            },
        )

    def locate(
        self,
        reference: TableReference,
        *,
        current_worksheet: Worksheet,
    ) -> TableLocation:
        """Resolve a semantic table reference into its placed table.

        Returns:
            The resolved table location.

        Raises:
            UnsupportedFeatureError: If the referenced table does not exist.
        """
        key = reference.sheet_name or current_worksheet.name
        location = self.by_sheet_and_name.get((key, reference.name))
        if location is None and reference.sheet_name is None:
            location = self.by_name.get(reference.name)
        if location is None:
            message = f"Table {reference.name!r} was not found"
            raise UnsupportedFeatureError(
                message,
                context={"table": reference.name, "reason": "table_not_found"},
            )
        return location

    def resolve_formula(  # noqa: WPS211
        self,
        formula: Formula,
        *,
        current_worksheet: Worksheet,
        current_table: SpreadsheetTable,
        current_anchor: CellAddress,
    ) -> ResolvedFormula:
        if isinstance(formula, FormulaLiteral):
            return ResolvedFormulaLiteral(formula.value)
        if isinstance(formula, FormulaBinary):
            return ResolvedFormulaBinary(
                formula.operator,
                self.resolve_formula(
                    formula.left,
                    current_worksheet=current_worksheet,
                    current_table=current_table,
                    current_anchor=current_anchor,
                ),
                self.resolve_formula(
                    formula.right,
                    current_worksheet=current_worksheet,
                    current_table=current_table,
                    current_anchor=current_anchor,
                ),
            )
        if isinstance(formula, CellReference):
            location = self._location(
                formula,
                current_worksheet=current_worksheet,
                current_table=current_table,
                current_anchor=current_anchor,
            )
            column = resolve_column(location, formula.column_id)
            return ResolvedCellReference(
                column=location.anchor.column + column.offset,
                row=(
                    None
                    if formula.row_index is None
                    else location.anchor.row + formula.row_index + 1
                ),
                sheet_name=(
                    location.worksheet.name
                    if formula.sheet_name is not None
                    or location.worksheet.name != current_worksheet.name
                    else None
                ),
                column_absolute=formula.column_absolute,
                row_absolute=formula.row_absolute,
            )
        if isinstance(formula, RangeReference):
            location = self._location(
                formula,
                current_worksheet=current_worksheet,
                current_table=current_table,
                current_anchor=current_anchor,
            )
            column = resolve_column(location, formula.column_id)
            row_count = _known_row_count(location.table)
            physical_column = location.anchor.column + column.offset
            return ResolvedRangeReference(
                sheet_name=location.worksheet.name,
                start=CellAddress(location.anchor.row + 1, physical_column),
                end=CellAddress(location.anchor.row + row_count, physical_column),
                table_name=formula.table_name,
                column_title=column.column.display_title,
                column_absolute=formula.column_absolute,
                row_absolute=formula.row_absolute,
            )
        message = f"Unsupported formula node: {type(formula).__name__}"
        raise TypeError(message)

    def _location(
        self,
        reference: CellReference | RangeReference,
        *,
        current_worksheet: Worksheet,
        current_table: SpreadsheetTable,
        current_anchor: CellAddress,
    ) -> TableLocation:
        if reference.table_name is None:
            return TableLocation(current_worksheet, current_table, current_anchor)
        if reference.sheet_name is not None:
            return self.by_sheet_and_name[reference.sheet_name, reference.table_name]
        return self.by_name[reference.table_name]


def _location_name(location: TableLocation) -> str:
    name = location.table.name
    if name is None:
        message = "Formula catalog location must have a table name"
        raise RuntimeError(message)
    return name


def resolve_column(location: TableLocation, column_id: str) -> ColumnLocation:
    for offset, column in enumerate(location.table.columns):
        if column.id == column_id:
            return ColumnLocation(column=column, offset=offset)
    message = f"Column {column_id!r} was not found"
    raise LookupError(message)


def resolve_data_range(location: TableLocation, column_id: str) -> CellRange:
    offset = resolve_column(location, column_id).offset
    physical_column = location.anchor.column + offset
    row_count = _known_row_count(location.table)
    return CellRange(
        start=CellAddress(location.anchor.row + 1, physical_column),
        end=CellAddress(location.anchor.row + row_count, physical_column),
    )


def _known_row_count(table: SpreadsheetTable) -> int:
    source = table.data.source
    row_count = source.row_count if isinstance(source, DataSourceInfo) else None
    if row_count is None:
        message = f"Table {table.name!r} needs a known row count for a range reference"
        raise UnsupportedFeatureError(
            message,
            context={"table": table.name, "reason": "unknown_row_count"},
        )
    if row_count < 1:
        message = f"Table {table.name!r} has no data cells to reference"
        raise UnsupportedFeatureError(
            message,
            context={"table": table.name, "reason": "empty_range"},
        )
    return row_count


def _placed_tables(
    plan: WorksheetPlan,
) -> Iterator[tuple[SpreadsheetTable, CellAddress]]:
    for placement in plan.placements:
        block = placement.block
        if isinstance(block, SpreadsheetTable):
            yield block, placement.anchor


__all__ = (
    "FormulaCatalog",
    "resolve_column",
    "resolve_data_range",
)
