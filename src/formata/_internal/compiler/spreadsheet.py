from __future__ import annotations

import dataclasses
from collections.abc import Iterator, Sequence
from typing import Any

from formata._internal.const import _TITLE_FONT_SIZES
from formata._internal.layout import DocumentPlan, WorksheetPlan, plan_document
from formata._internal.semantic import SemanticRowEvaluator
from formata._internal.validation import validate_spreadsheet
from formata.core.errors import UnsupportedFeatureError
from formata.core.formatting import (
    CellAlignment,
    FontStyle,
    Style,
    StyleInput,
    StyleSheet,
)
from formata.core.ir import (
    SPREADSHEET_IR_VERSION,
    CellAddress,
    CellRange,
    ResolvedCellReference,
    ResolvedFormula,
    ResolvedFormulaBinary,
    ResolvedFormulaLiteral,
    ResolvedRangeReference,
    SpreadsheetChartIR,
    SpreadsheetColumnIR,
    SpreadsheetConditionalRuleIR,
    SpreadsheetFooterIR,
    SpreadsheetImageIR,
    SpreadsheetIR,
    SpreadsheetPlacementIR,
    SpreadsheetRowIR,
    SpreadsheetSeriesIR,
    SpreadsheetTableIR,
    SpreadsheetTextIR,
    SpreadsheetTotalIR,
    SpreadsheetWorksheetIR,
)
from formata.core.models import (
    CellReference,
    Chart,
    Column,
    DocumentKind,
    Formula,
    FormulaBinary,
    FormulaLiteral,
    Freeze,
    Image,
    RangeReference,
    SpreadsheetBlock,
    SpreadsheetDocument,
    SpreadsheetTable,
    TableReference,
    Title,
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
        plan = plan_document(document)
        catalog = _FormulaCatalog.from_document(document, plan)
        worksheets = tuple(
            self._compile_worksheet(worksheet, worksheet_plan, catalog, document)
            for worksheet, worksheet_plan in zip(
                document.worksheets,
                plan.worksheets,
                strict=True,
            )
        )
        return SpreadsheetIR(
            worksheets=worksheets,
            metadata=document.metadata,
            version=ir_version,
        )

    def _compile_worksheet(
        self,
        worksheet: Worksheet,
        plan: WorksheetPlan,
        catalog: _FormulaCatalog,
        document: SpreadsheetDocument,
    ) -> SpreadsheetWorksheetIR:
        tables = tuple(
            self._compile_table(table, anchor, worksheet, catalog, document)
            for table, anchor in _placed_tables(plan)
        )
        return SpreadsheetWorksheetIR(
            name=worksheet.name,
            tables=tables,
            freeze=_compile_freeze(worksheet, plan),
            texts=tuple(_compile_texts(plan, document)),
            images=tuple(_compile_images(plan)),
            charts=tuple(_compile_charts(plan, worksheet, catalog)),
            placements=tuple(_compile_placements(plan)),
        )

    def _compile_table(  # noqa: WPS211
        self,
        table: SpreadsheetTable,
        anchor: CellAddress,
        worksheet: Worksheet,
        catalog: _FormulaCatalog,
        document: SpreadsheetDocument,
    ) -> SpreadsheetTableIR:
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


def _compile_freeze(worksheet: Worksheet, plan: WorksheetPlan) -> Freeze | None:
    rows = worksheet.freeze.rows if worksheet.freeze is not None else 0
    columns = worksheet.freeze.columns if worksheet.freeze is not None else 0
    for placement in plan.placements:
        table = placement.block
        if isinstance(table, SpreadsheetTable) and table.freeze_header:
            rows = max(rows, placement.anchor.row)
    return None if rows == 0 and columns == 0 else Freeze(rows=rows, columns=columns)


def _placed_tables(
    plan: WorksheetPlan,
) -> Iterator[tuple[SpreadsheetTable, CellAddress]]:
    for placement in plan.placements:
        block = placement.block
        if isinstance(block, SpreadsheetTable):
            yield block, placement.anchor


def _compile_placements(plan: WorksheetPlan) -> Iterator[SpreadsheetPlacementIR]:
    for placement in plan.placements:
        yield SpreadsheetPlacementIR(
            kind=placement.kind,
            path=placement.path,
            anchor=placement.anchor,
            occupied=placement.occupied,
            name=_block_name(placement.block),
            explicit=placement.explicit,
        )


def _block_name(block: SpreadsheetBlock) -> str | None:
    if isinstance(block, (Chart, Image, SpreadsheetTable)):
        return block.name
    return None


def _compile_texts(
    plan: WorksheetPlan,
    document: SpreadsheetDocument,
) -> Iterator[SpreadsheetTextIR]:
    for placement in plan.placements:
        title = placement.block
        if isinstance(title, Title):
            yield SpreadsheetTextIR(
                anchor=placement.anchor,
                text=title.text,
                span=title.span,
                style=_resolve_style(
                    title.style,
                    document.styles,
                    base=_title_base_style(title.level, document),
                ),
            )


def _title_base_style(level: int, document: SpreadsheetDocument) -> Style:
    size = _TITLE_FONT_SIZES.get(level, 11.0)
    heading = Style(font=FontStyle(bold=True, size=size))
    return heading.merged_over(document.theme.default)


def _compile_images(plan: WorksheetPlan) -> Iterator[SpreadsheetImageIR]:
    for placement in plan.placements:
        image = placement.block
        if isinstance(image, Image):
            yield SpreadsheetImageIR(
                anchor=placement.anchor,
                source=image.source,
                width=image.width,
                height=image.height,
                name=image.name,
                description=image.description,
            )


def _compile_charts(
    plan: WorksheetPlan,
    worksheet: Worksheet,
    catalog: _FormulaCatalog,
) -> Iterator[SpreadsheetChartIR]:
    for placement in plan.placements:
        chart = placement.block
        if isinstance(chart, Chart):
            yield _compile_chart(chart, placement.anchor, worksheet, catalog)


def _compile_chart(
    chart: Chart,
    anchor: CellAddress,
    worksheet: Worksheet,
    catalog: _FormulaCatalog,
) -> SpreadsheetChartIR:
    location = catalog.locate(chart.source, current_worksheet=worksheet)
    categories = _chart_range(location, chart.x)
    return SpreadsheetChartIR(
        anchor=anchor,
        kind=chart.kind,
        sheet_name=location.worksheet.name,
        series=tuple(
            SpreadsheetSeriesIR(
                name=_column(location, column_id).column.display_title,
                values=_chart_range(location, column_id),
                categories=categories,
            )
            for column_id in chart.y
        ),
        title=chart.title,
        width=chart.width,
        height=chart.height,
        name=chart.name,
    )


def _chart_range(location: _TableLocation, column_id: str) -> CellRange:
    offset = _column(location, column_id).offset
    physical_column = location.anchor.column + offset
    row_count = _known_row_count(location.table)
    return CellRange(
        start=CellAddress(location.anchor.row + 1, physical_column),
        end=CellAddress(location.anchor.row + row_count, physical_column),
    )


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
    def from_document(
        cls,
        document: SpreadsheetDocument,
        plan: DocumentPlan,
    ) -> _FormulaCatalog:
        locations = tuple(
            _TableLocation(worksheet=worksheet, table=table, anchor=anchor)
            for worksheet, worksheet_plan in zip(
                document.worksheets,
                plan.worksheets,
                strict=True,
            )
            for table, anchor in _placed_tables(worksheet_plan)
            if table.name is not None
        )
        return cls(
            by_name={location.table.name: location for location in locations},  # type: ignore[misc]
            by_sheet_and_name={
                (location.worksheet.name, location.table.name): location  # type: ignore[misc]
                for location in locations
            },
        )

    def locate(
        self,
        reference: TableReference,
        *,
        current_worksheet: Worksheet,
    ) -> _TableLocation:
        """Resolve a semantic table reference into its placed table.

        Returns:
            The resolved table location.

        Raises:
            UnsupportedFeatureError: If the referenced table does not exist.
        """
        key = reference.sheet_name or current_worksheet.name
        location = self.by_sheet_and_name.get(
            (key, reference.name),
        ) or self.by_name.get(reference.name)
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
