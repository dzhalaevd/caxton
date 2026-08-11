from __future__ import annotations

import dataclasses
import enum
import itertools
from collections.abc import Iterable, Mapping, Sequence
from typing import Self

from formata._internal.compiler import SpreadsheetCompiler
from formata._internal.formulas import lower_excel_formula
from formata._internal.normalization import format_cell_address, parse_cell_address
from formata.core._values import freeze_mapping
from formata.core.formatting import Alignment, DisplayFormat, Style
from formata.core.ir import (
    CellAddress,
    ResolvedFormula,
    SpreadsheetColumnIR,
    SpreadsheetFooterIR,
    SpreadsheetRowIR,
    SpreadsheetTableIR,
)
from formata.core.models import AggregateFunction, Freeze, SpreadsheetDocument
from formata.core.models.common import freeze_metadata

from ._spec import SemanticTypeSpec, _inspect_semantic_type


class RowsMode(enum.StrEnum):
    """Amount of table data explicitly requested for layout inspection."""

    NONE = "none"
    SAMPLE = "sample"
    ALL = "all"


@dataclasses.dataclass(frozen=True, slots=True)
class Rows:
    """Explicit row-consumption policy for layout inspection."""

    mode: RowsMode
    limit: int | None = None

    def __post_init__(self) -> None:
        if self.mode is RowsMode.SAMPLE:
            if (
                isinstance(self.limit, bool)
                or not isinstance(self.limit, int)
                or self.limit < 1
            ):
                message = "Sample row limit must be a positive integer"
                raise ValueError(message)
            return
        if self.limit is not None:
            message = f"Row limit is not valid for {self.mode.value!r} scope"
            raise ValueError(message)

    @classmethod
    def none(cls) -> Self:
        """Create a structure-only policy that never reads table rows.

        Returns:
            A structure-only row policy.
        """
        return cls(RowsMode.NONE)

    @classmethod
    def sample(cls, limit: int) -> Self:
        """Create a policy that reads at most ``limit`` rows per table.

        Returns:
            A bounded row policy.
        """
        return cls(RowsMode.SAMPLE, limit)

    @classmethod
    def all(cls) -> Self:
        """Create a policy that explicitly consumes every table row.

        Returns:
            A full-consumption row policy.
        """
        return cls(RowsMode.ALL)


class CellKind(enum.StrEnum):
    """Semantic role of an observed layout cell."""

    HEADER = "header"
    DATA = "data"


@dataclasses.dataclass(frozen=True, slots=True)
class CellLayout:
    """One observed spreadsheet cell."""

    address: str
    value: object
    kind: CellKind
    column_id: str
    row_index: int | None = None
    formula: str | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class ColumnLayout:
    """One resolved spreadsheet column."""

    offset: int
    id: str
    title: str
    semantic_type: SemanticTypeSpec
    alignment: Alignment | None
    width: float | None
    display_format: DisplayFormat | None
    header_address: str
    formula: ResolvedFormula | None = None
    style: Style = dataclasses.field(default_factory=Style)
    auto_width: bool = False


@dataclasses.dataclass(frozen=True, slots=True)
class TotalLayout:
    column_offset: int
    function: AggregateFunction


@dataclasses.dataclass(frozen=True, slots=True)
class FooterLayout:
    label: str
    label_column_offset: int
    items: Sequence[TotalLayout]
    style: Style

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))


@dataclasses.dataclass(frozen=True, slots=True)
class ConditionalRuleLayout:
    formula: str
    style: Style


@dataclasses.dataclass(frozen=True, slots=True)
class RowLayout:
    """One evaluated semantic row in layout column order."""

    index: int
    values: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "values",
            freeze_mapping(self.values, label="Layout row values"),
        )

    def __getitem__(self, column_id: str) -> object:
        return self.values[column_id]


@dataclasses.dataclass(frozen=True, slots=True)
class TableLayout:
    """Resolved table placement and explicitly inspected rows."""

    name: str | None
    anchor: str
    columns: Sequence[ColumnLayout]
    rows: Sequence[RowLayout]
    header_style: Style = dataclasses.field(default_factory=Style)
    footer: FooterLayout | None = None
    rules: Sequence[ConditionalRuleLayout] = ()
    autofilter: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "columns", tuple(self.columns))
        object.__setattr__(self, "rows", tuple(self.rows))
        object.__setattr__(self, "rules", tuple(self.rules))

    @property
    def column_ids(self) -> tuple[str, ...]:
        """Resolved semantic column identities in physical order."""
        return tuple(column.id for column in self.columns)

    def column(self, column_id: str) -> ColumnLayout:
        """Select a resolved column by semantic identity.

        Returns:
            The selected column layout.

        Raises:
            LookupError: If no column has the requested identity.
        """
        for column in self.columns:
            if column.id == column_id:
                return column
        message = f"Column {column_id!r} was not found in table {_table_label(self)}"
        raise LookupError(message)

    def row(self, index: int) -> RowLayout:
        """Select an inspected row by its zero-based source index.

        Returns:
            The selected row layout.

        Raises:
            LookupError: If that row was not inspected.
        """
        for row in self.rows:
            if row.index == index:
                return row
        message = f"Row {index} was not inspected in table {_table_label(self)}"
        raise LookupError(message)


@dataclasses.dataclass(frozen=True, slots=True)
class WorksheetLayout:
    """Resolved tables and cells for one worksheet."""

    name: str
    tables: Sequence[TableLayout]
    freeze: Freeze | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tables", tuple(self.tables))

    def table(self, name: str) -> TableLayout:
        """Select a named resolved table.

        Returns:
            The selected table layout.

        Raises:
            LookupError: If no table has the requested name.
        """
        for table in self.tables:
            if table.name == name:
                return table
        message = f"Table {name!r} was not found in worksheet {self.name!r}"
        raise LookupError(message)

    def cell(self, address: str) -> CellLayout:
        """Select an observed header or inspected data cell by A1 address.

        Returns:
            The selected cell layout.

        Raises:
            LookupError: If the cell was not observed.
        """
        coordinate = parse_cell_address(address)
        canonical = format_cell_address(coordinate.row, coordinate.column)
        for cell in self._iter_cells():
            if cell.address == canonical:
                return cell
        message = f"Cell {canonical!r} was not observed in worksheet {self.name!r}"
        raise LookupError(message)

    def _iter_cells(self) -> Iterable[CellLayout]:
        for table in self.tables:
            anchor = parse_cell_address(table.anchor)
            for column in table.columns:
                yield CellLayout(
                    address=column.header_address,
                    value=column.title,
                    kind=CellKind.HEADER,
                    column_id=column.id,
                )
            for row in table.rows:
                physical_row = anchor.row + row.index + 1
                for column in table.columns:
                    physical_row = anchor.row + row.index + 1
                    yield CellLayout(
                        address=format_cell_address(
                            physical_row,
                            anchor.column + column.offset,
                        ),
                        value=row[column.id],
                        kind=CellKind.DATA,
                        column_id=column.id,
                        row_index=row.index,
                        formula=(
                            None
                            if column.formula is None
                            else lower_excel_formula(
                                column.formula,
                                current_row=physical_row,
                            )
                        ),
                    )


@dataclasses.dataclass(frozen=True, slots=True)
class SpreadsheetLayout:
    """Stable observed result of spreadsheet compilation."""

    worksheets: Sequence[WorksheetLayout]
    metadata: Mapping[str, object]
    version: int
    row_scope: Rows

    def __post_init__(self) -> None:
        object.__setattr__(self, "worksheets", tuple(self.worksheets))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def worksheet(self, name: str) -> WorksheetLayout:
        """Select a worksheet by name.

        Returns:
            The selected worksheet layout.

        Raises:
            LookupError: If no worksheet has the requested name.
        """
        for worksheet in self.worksheets:
            if worksheet.name == name:
                return worksheet
        message = f"Worksheet {name!r} was not found"
        raise LookupError(message)


def inspect_layout(
    document: SpreadsheetDocument,
    *,
    rows: Rows | None = None,
) -> SpreadsheetLayout:
    """Compile a spreadsheet into a stable, backend-independent layout view.

    Returns:
        An immutable layout view with only the explicitly requested rows.
    """
    row_scope = rows or Rows.none()
    compiled = SpreadsheetCompiler().compile(document)
    return SpreadsheetLayout(
        worksheets=tuple(
            WorksheetLayout(
                name=worksheet.name,
                tables=tuple(
                    _inspect_table(table, row_scope) for table in worksheet.tables
                ),
                freeze=worksheet.freeze,
            )
            for worksheet in compiled.worksheets
        ),
        metadata=compiled.metadata,
        version=compiled.version,
        row_scope=row_scope,
    )


def _inspect_table(table: SpreadsheetTableIR, rows: Rows) -> TableLayout:
    inspected_rows = _materialize_rows(table.rows, rows)
    return TableLayout(
        name=table.name,
        anchor=_format_coordinate(table.anchor),
        columns=tuple(
            _inspect_column(column, table.anchor) for column in table.columns
        ),
        rows=tuple(
            RowLayout(
                index=row.index,
                values={
                    column.id: value
                    for column, value in zip(
                        table.columns,
                        row.values,
                        strict=True,
                    )
                },
            )
            for row in inspected_rows
        ),
        header_style=table.header_style,
        footer=_inspect_footer(table.footer),
        rules=tuple(
            ConditionalRuleLayout(
                formula=lower_excel_formula(
                    rule.condition,
                    current_row=table.anchor.row + 1,
                ),
                style=rule.style,
            )
            for rule in table.rules
        ),
        autofilter=table.autofilter,
    )


def _inspect_column(
    column: SpreadsheetColumnIR,
    anchor: CellAddress,
) -> ColumnLayout:
    return ColumnLayout(
        offset=column.offset,
        id=column.id,
        title=column.title,
        semantic_type=_inspect_semantic_type(column.semantic_type),
        alignment=column.alignment,
        width=column.width_hint,
        display_format=column.display_format,
        header_address=format_cell_address(
            anchor.row,
            anchor.column + column.offset,
        ),
        formula=column.formula,
        style=column.style,
        auto_width=column.auto_width,
    )


def _inspect_footer(footer: SpreadsheetFooterIR | None) -> FooterLayout | None:
    if footer is None:
        return None
    return FooterLayout(
        label=footer.label,
        label_column_offset=footer.label_column_offset,
        items=tuple(
            TotalLayout(item.column_offset, item.function) for item in footer.items
        ),
        style=footer.style,
    )


def _materialize_rows(
    rows: Iterable[SpreadsheetRowIR],
    scope: Rows,
) -> tuple[SpreadsheetRowIR, ...]:
    if scope.mode is RowsMode.NONE:
        return ()
    if scope.mode is RowsMode.SAMPLE:
        return tuple(itertools.islice(rows, scope.limit))
    return tuple(rows)


def _format_coordinate(address: CellAddress) -> str:
    return format_cell_address(address.row, address.column)


def _table_label(table: TableLayout) -> str:
    return repr(table.name) if table.name is not None else "<unnamed>"


__all__ = (
    "CellKind",
    "CellLayout",
    "ColumnLayout",
    "ConditionalRuleLayout",
    "FooterLayout",
    "RowLayout",
    "Rows",
    "RowsMode",
    "SpreadsheetLayout",
    "TableLayout",
    "TotalLayout",
    "WorksheetLayout",
    "inspect_layout",
)
