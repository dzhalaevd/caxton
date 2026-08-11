from __future__ import annotations

import dataclasses
from collections.abc import Iterator, Sequence
from typing import Any

from formata._internal.normalization import parse_cell_address
from formata._internal.semantic import SemanticRowEvaluator
from formata._internal.validation import validate_spreadsheet
from formata.core.errors import UnsupportedFeatureError
from formata.core.formatting import CellAlignment, Style, StyleInput, StyleSheet
from formata.core.ir import (
    SPREADSHEET_IR_VERSION,
    CellAddress,
    ResolvedCellReference,
    ResolvedFormula,
    ResolvedFormulaBinary,
    ResolvedFormulaLiteral,
    ResolvedRangeReference,
    SpreadsheetColumnIR,
    SpreadsheetConditionalRuleIR,
    SpreadsheetFooterIR,
    SpreadsheetIR,
    SpreadsheetRowIR,
    SpreadsheetTableIR,
    SpreadsheetTotalIR,
    SpreadsheetWorksheetIR,
)
from formata.core.models import (
    CellReference,
    Column,
    DocumentKind,
    Formula,
    FormulaBinary,
    FormulaLiteral,
    Freeze,
    RangeReference,
    SpreadsheetDocument,
    SpreadsheetTable,
    Total,
    Totals,
    Worksheet,
)
from formata.core.protocols import DataSource, DataSourceInfo
from formata.core.rendering import RendererCapabilities


@dataclasses.dataclass(frozen=True, slots=True)
class _CompiledRows:
    source: DataSource[Any]
    columns: Sequence[Column]
    evaluator: SemanticRowEvaluator

    def __iter__(self) -> Iterator[SpreadsheetRowIR]:
        value_columns = tuple(
            column for column in self.columns if column.excel_formula is None
        )
        for row in self.evaluator.iter_rows(self.source, value_columns):
            yield SpreadsheetRowIR(
                index=row.index,
                values=tuple(
                    None if column.excel_formula is not None else row[column.id]
                    for column in self.columns
                ),
            )


class SpreadsheetCompiler:
    """Validate and lower spreadsheet intent into versioned family IR."""

    def __init__(self, evaluator: SemanticRowEvaluator | None = None) -> None:
        self._evaluator = evaluator or SemanticRowEvaluator()

    def compile(
        self,
        document: SpreadsheetDocument,
        *,
        capabilities: RendererCapabilities | None = None,
    ) -> SpreadsheetIR:
        """Compile without consuming table row sources.

        Returns:
            A read-only spreadsheet IR with lazy table row streams.

        """
        validate_spreadsheet(document)
        return self.compile_validated(document, capabilities=capabilities)

    def compile_validated(
        self,
        document: SpreadsheetDocument,
        *,
        capabilities: RendererCapabilities | None = None,
    ) -> SpreadsheetIR:
        """Compile a document whose structural validation already succeeded.

        Returns:
            A read-only spreadsheet IR with lazy table row streams.
        """
        ir_version = _select_ir_version(capabilities)
        catalog = _FormulaCatalog.from_document(document)
        worksheets = tuple(
            self._compile_worksheet(worksheet, catalog, document)
            for worksheet in document.worksheets
        )
        return SpreadsheetIR(
            worksheets=worksheets,
            metadata=document.metadata,
            version=ir_version,
        )

    def _compile_worksheet(
        self,
        worksheet: Worksheet,
        catalog: _FormulaCatalog,
        document: SpreadsheetDocument,
    ) -> SpreadsheetWorksheetIR:
        return SpreadsheetWorksheetIR(
            name=worksheet.name,
            tables=tuple(
                self._compile_table(table, worksheet, catalog, document)
                for table in worksheet.blocks
            ),
            freeze=_compile_freeze(worksheet),
        )

    def _compile_table(
        self,
        table: SpreadsheetTable,
        worksheet: Worksheet,
        catalog: _FormulaCatalog,
        document: SpreadsheetDocument,
    ) -> SpreadsheetTableIR:
        anchor = parse_cell_address(table.anchor or "A1")
        table_style = _resolve_style(
            table.style,
            document.styles,
            base=document.theme.default,
        )
        columns = tuple(
            _compile_column(
                column,
                offset,
                worksheet=worksheet,
                table=table,
                anchor=anchor,
                catalog=catalog,
                styles=document.styles,
                base_style=table_style,
                table_auto_width=table.auto_width,
            )
            for offset, column in enumerate(table.columns)
        )
        return SpreadsheetTableIR(
            name=table.name,
            anchor=anchor,
            columns=columns,
            rows=_CompiledRows(
                source=table.data.source,
                columns=table.columns,
                evaluator=self._evaluator,
            ),
            header_style=_resolve_style(
                table.header_style,
                document.styles,
                base=document.theme.header.merged_over(table_style),
            ),
            footer=_compile_footer(
                table.footer,
                table,
                document.styles,
                document.theme.total.merged_over(table_style),
            ),
            rules=tuple(
                SpreadsheetConditionalRuleIR(
                    condition=_conditional_condition(
                        catalog.resolve_formula(
                            rule.condition,
                            current_worksheet=worksheet,
                            current_table=table,
                            current_anchor=anchor,
                        ),
                    ),
                    style=_resolve_style(rule.style, document.styles),
                )
                for rule in table.rules
            ),
            autofilter=table.autofilter,
        )


def _compile_column(  # noqa: WPS211
    column: Column,
    offset: int,
    *,
    worksheet: Worksheet,
    table: SpreadsheetTable,
    anchor: CellAddress,
    catalog: _FormulaCatalog,
    styles: StyleSheet,
    base_style: Style,
    table_auto_width: bool,
) -> SpreadsheetColumnIR:
    resolved_style = _resolve_style(column.style_ref, styles, base=base_style)
    legacy = Style(
        alignment=(
            None
            if column.alignment is None
            else CellAlignment(horizontal=column.alignment)
        ),
        display_format=column.display_format,
    )
    resolved_style = legacy.merged_over(resolved_style)
    return SpreadsheetColumnIR(
        offset=offset,
        id=column.id,
        title=column.display_title,
        semantic_type=column.semantic_type,
        alignment=(
            None
            if resolved_style.alignment is None
            else resolved_style.alignment.horizontal
        ),
        width_hint=column.width_hint,
        display_format=resolved_style.display_format,
        formula=(
            None
            if column.excel_formula is None
            else catalog.resolve_formula(
                column.excel_formula,
                current_worksheet=worksheet,
                current_table=table,
                current_anchor=anchor,
            )
        ),
        style=resolved_style,
        auto_width=(
            column.auto_width or (table_auto_width and column.width_hint is None)
        ),
    )


def _resolve_style(
    value: StyleInput | None,
    styles: StyleSheet,
    *,
    base: Style | None = None,
) -> Style:
    if value is None:
        return base or Style()
    resolved = styles[value] if isinstance(value, str) else value
    return resolved.merged_over(base)


def _conditional_condition(formula: ResolvedFormula) -> ResolvedFormula:
    if isinstance(formula, ResolvedCellReference) and formula.row is None:
        return dataclasses.replace(formula, column_absolute=True)
    if isinstance(formula, ResolvedFormulaBinary):
        return ResolvedFormulaBinary(
            formula.operator,
            _conditional_condition(formula.left),
            _conditional_condition(formula.right),
        )
    return formula


def _compile_footer(
    footer: Totals | None,
    table: SpreadsheetTable,
    styles: StyleSheet,
    base_style: Style,
) -> SpreadsheetFooterIR | None:
    if footer is None:
        return None
    by_id = {column.id: offset for offset, column in enumerate(table.columns)}
    if footer.items:
        items = footer.items
        aggregate_ids = {item.column for item in items}
        label_id = footer.label_column or next(
            (column.id for column in table.columns if column.id not in aggregate_ids),
            table.columns[0].id,
        )
    else:
        label_id = footer.label_column or table.columns[0].id
        items = tuple(
            Total(column.id)
            for column in table.columns
            if column.id != label_id
            and column.semantic_type.name
            in {"decimal", "duration", "integer", "money", "percentage"}
        )
    return SpreadsheetFooterIR(
        label=footer.label,
        label_column_offset=by_id[label_id],
        items=tuple(
            SpreadsheetTotalIR(by_id[item.column], item.function) for item in items
        ),
        style=_resolve_style(footer.style, styles, base=base_style),
    )


def _compile_freeze(worksheet: Worksheet) -> Freeze | None:
    rows = worksheet.freeze.rows if worksheet.freeze is not None else 0
    columns = worksheet.freeze.columns if worksheet.freeze is not None else 0
    for table in worksheet.blocks:
        if table.freeze == "header":
            rows = max(rows, parse_cell_address(table.anchor or "A1").row)
    return None if rows == 0 and columns == 0 else Freeze(rows=rows, columns=columns)


@dataclasses.dataclass(frozen=True, slots=True)
class _TableLocation:
    worksheet: Worksheet
    table: SpreadsheetTable
    anchor: CellAddress


@dataclasses.dataclass(frozen=True, slots=True)
class _ColumnLocation:
    column: Column
    offset: int


@dataclasses.dataclass(frozen=True, slots=True)
class _FormulaCatalog:
    by_name: dict[str, _TableLocation]
    by_sheet_and_name: dict[tuple[str, str], _TableLocation]

    @classmethod
    def from_document(cls, document: SpreadsheetDocument) -> _FormulaCatalog:
        locations = tuple(
            _TableLocation(
                worksheet=worksheet,
                table=table,
                anchor=parse_cell_address(table.anchor or "A1"),
            )
            for worksheet in document.worksheets
            for table in worksheet.blocks
            if table.name is not None
        )
        return cls(
            by_name={location.table.name: location for location in locations},  # type: ignore[misc]
            by_sheet_and_name={
                (location.worksheet.name, location.table.name): location  # type: ignore[misc]
                for location in locations
            },
        )

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
            column = _column(location, formula.column_id)
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
            column = _column(location, formula.column_id)
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
    ) -> _TableLocation:
        if reference.table_name is None:
            return _TableLocation(current_worksheet, current_table, current_anchor)
        if reference.sheet_name is not None:
            return self.by_sheet_and_name[reference.sheet_name, reference.table_name]
        return self.by_name[reference.table_name]


def _column(location: _TableLocation, column_id: str) -> _ColumnLocation:
    for offset, column in enumerate(location.table.columns):
        if column.id == column_id:
            return _ColumnLocation(column=column, offset=offset)
    message = f"Column {column_id!r} was not found"
    raise LookupError(message)


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


def compile_spreadsheet(document: SpreadsheetDocument) -> SpreadsheetIR:
    """Compile spreadsheet intent using the default family compiler.

    Returns:
        A read-only spreadsheet IR with lazy table row streams.
    """
    return SpreadsheetCompiler().compile(document)


def _select_ir_version(capabilities: RendererCapabilities | None) -> int:
    if capabilities is None:
        return SPREADSHEET_IR_VERSION
    supported = capabilities.ir_versions.get(DocumentKind.SPREADSHEET, frozenset())
    compatible = supported & {SPREADSHEET_IR_VERSION}
    if not compatible:
        message = "Renderer does not support a compatible Spreadsheet IR version"
        raise UnsupportedFeatureError(
            message,
            context={
                "available_versions": sorted(supported),
                "required_versions": [SPREADSHEET_IR_VERSION],
            },
        )
    return max(compatible)


__all__ = ("SpreadsheetCompiler", "compile_spreadsheet")
