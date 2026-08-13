"""Coordinate validation, preparation, layout, and Spreadsheet IR lowering."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator, Sequence
from typing import Any

from caxton._internal.aggregation import (
    PreparedColumn,
    PreparedTabularData,
    prepare_matrix,
    prepare_table,
    table_needs_preparation,
)
from caxton._internal.block_paths import iter_blocks_with_paths
from caxton._internal.compiler.formula_resolution import (
    FormulaCatalog,
    resolve_column,
    resolve_data_range,
)
from caxton._internal.const import _TITLE_FONT_SIZES
from caxton._internal.layout import DocumentPlan, WorksheetPlan, plan_document
from caxton._internal.semantic import SemanticRowEvaluator
from caxton._internal.validation import validate_spreadsheet
from caxton.core.errors import Notification, UnsupportedFeatureError
from caxton.core.formatting import (
    CellAlignment,
    FontStyle,
    Style,
    StyleInput,
    StyleSheet,
)
from caxton.core.ir import (
    SPREADSHEET_IR_VERSION,
    CellAddress,
    CellRange,
    ResolvedCellReference,
    ResolvedFormula,
    ResolvedFormulaBinary,
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
from caxton.core.models import (
    Chart,
    Column,
    DocumentKind,
    Freeze,
    Image,
    Matrix,
    SpreadsheetBlock,
    SpreadsheetDocument,
    SpreadsheetTable,
    Title,
    Total,
    Totals,
    Worksheet,
)
from caxton.core.protocols import DataSource
from caxton.core.rendering import RendererCapabilities


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
        """Compile spreadsheet intent, buffering shape-dependent blocks.

        Returns:
            A read-only spreadsheet IR. Ordinary table rows remain lazy;
            grouped tables and matrices are consumed once and prepared.

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
            A read-only spreadsheet IR with lazy ordinary rows and buffered
            shape-dependent rows.
        """
        ir_version = _select_ir_version(capabilities)
        prepared = self._prepare_document(document)
        plan = plan_document(
            document,
            measurements={
                block: (len(item.rows), len(item.columns))
                for block, item in prepared.items()
            },
        )
        _validate_prepared_placement(plan)
        catalog = FormulaCatalog.from_document(document, plan)
        worksheets = tuple(
            self._compile_worksheet(
                worksheet,
                worksheet_plan,
                catalog,
                document,
                prepared,
            )
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

    def _prepare_document(
        self,
        document: SpreadsheetDocument,
    ) -> dict[SpreadsheetTable | Matrix, PreparedTabularData]:
        prepared: dict[SpreadsheetTable | Matrix, PreparedTabularData] = {}
        for worksheet in document.worksheets:
            for block, block_path in iter_blocks_with_paths(worksheet.blocks):
                path = f'worksheet["{worksheet.name}"].{block_path}'
                if isinstance(block, Matrix):
                    prepared[block] = prepare_matrix(
                        block,
                        self._evaluator,
                        path=path,
                    )
                elif isinstance(block, SpreadsheetTable) and table_needs_preparation(
                    block,
                ):
                    prepared[block] = prepare_table(
                        block,
                        self._evaluator,
                        path=path,
                    )
        return prepared

    def _compile_worksheet(
        self,
        worksheet: Worksheet,
        plan: WorksheetPlan,
        catalog: FormulaCatalog,
        document: SpreadsheetDocument,
        prepared: dict[SpreadsheetTable | Matrix, PreparedTabularData],
    ) -> SpreadsheetWorksheetIR:
        tables = tuple(
            self._compile_tabular(
                placement.block,
                placement.anchor,
                worksheet,
                catalog,
                document,
                prepared.get(placement.block),
            )
            for placement in plan.placements
            if isinstance(placement.block, (SpreadsheetTable, Matrix))
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

    def _compile_tabular(  # noqa: WPS211
        self,
        block: SpreadsheetTable | Matrix,
        anchor: CellAddress,
        worksheet: Worksheet,
        catalog: FormulaCatalog,
        document: SpreadsheetDocument,
        prepared: PreparedTabularData | None,
    ) -> SpreadsheetTableIR:
        if isinstance(block, Matrix):
            if prepared is None:
                message = "Matrix compilation requires prepared data"
                raise RuntimeError(message)
            return _compile_matrix(block, prepared, anchor, document)
        return self._compile_table(
            block,
            anchor,
            worksheet,
            catalog,
            document,
            prepared,
        )

    def _compile_table(  # noqa: WPS211
        self,
        table: SpreadsheetTable,
        anchor: CellAddress,
        worksheet: Worksheet,
        catalog: FormulaCatalog,
        document: SpreadsheetDocument,
        prepared: PreparedTabularData | None,
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
            rows=(
                _prepared_rows(prepared)
                if prepared is not None
                else _CompiledRows(
                    source=table.data.source,
                    columns=table.columns,
                    evaluator=self._evaluator,
                )
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
            merges=(() if prepared is None else _absolute_merges(prepared, anchor)),
        )


def _compile_matrix(
    matrix: Matrix,
    prepared: PreparedTabularData,
    anchor: CellAddress,
    document: SpreadsheetDocument,
) -> SpreadsheetTableIR:
    table_style = _resolve_style(
        matrix.style,
        document.styles,
        base=document.theme.default,
    )
    columns = tuple(
        _compile_prepared_column(column, offset, document, table_style)
        for offset, column in enumerate(prepared.columns)
    )
    return SpreadsheetTableIR(
        name=None,
        anchor=anchor,
        columns=columns,
        rows=_prepared_rows(prepared),
        header_style=_resolve_style(
            matrix.header_style,
            document.styles,
            base=document.theme.header.merged_over(table_style),
        ),
    )


def _compile_prepared_column(
    column: Column | PreparedColumn,
    offset: int,
    document: SpreadsheetDocument,
    table_style: Style,
) -> SpreadsheetColumnIR:
    title = column.display_title if isinstance(column, Column) else column.title
    style_ref = column.style_ref
    resolved_style = _resolve_style(style_ref, document.styles, base=table_style)
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
        title=title,
        semantic_type=column.semantic_type,
        alignment=(
            None
            if resolved_style.alignment is None
            else resolved_style.alignment.horizontal
        ),
        width_hint=column.width_hint,
        display_format=resolved_style.display_format,
        style=resolved_style,
        auto_width=column.auto_width,
        matrix_key=(None if isinstance(column, Column) else column.matrix_key),
    )


def _prepared_rows(prepared: PreparedTabularData) -> tuple[SpreadsheetRowIR, ...]:
    return tuple(
        SpreadsheetRowIR(index=index, values=values)
        for index, values in enumerate(prepared.rows)
    )


def _absolute_merges(
    prepared: PreparedTabularData,
    anchor: CellAddress,
) -> tuple[CellRange, ...]:
    return tuple(
        CellRange(
            start=CellAddress(
                row=anchor.row + merge.start_row + 1,
                column=anchor.column + merge.column_offset,
            ),
            end=CellAddress(
                row=anchor.row + merge.end_row + 1,
                column=anchor.column + merge.column_offset,
            ),
        )
        for merge in prepared.merges
    )


def _validate_prepared_placement(plan: DocumentPlan) -> None:
    notification = Notification()
    for worksheet in plan.worksheets:
        for overlap in worksheet.overlaps:
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
    notification.raise_if_errors("Spreadsheet structural validation failed")


def _compile_column(  # noqa: WPS211
    column: Column,
    offset: int,
    *,
    worksheet: Worksheet,
    table: SpreadsheetTable,
    anchor: CellAddress,
    catalog: FormulaCatalog,
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
    catalog: FormulaCatalog,
) -> Iterator[SpreadsheetChartIR]:
    for placement in plan.placements:
        chart = placement.block
        if isinstance(chart, Chart):
            yield _compile_chart(chart, placement.anchor, worksheet, catalog)


def _compile_chart(
    chart: Chart,
    anchor: CellAddress,
    worksheet: Worksheet,
    catalog: FormulaCatalog,
) -> SpreadsheetChartIR:
    location = catalog.locate(chart.source, current_worksheet=worksheet)
    categories = resolve_data_range(location, chart.x)
    return SpreadsheetChartIR(
        anchor=anchor,
        kind=chart.kind,
        sheet_name=location.worksheet.name,
        series=tuple(
            SpreadsheetSeriesIR(
                name=resolve_column(location, column_id).column.display_title,
                values=resolve_data_range(location, column_id),
                categories=categories,
            )
            for column_id in chart.y
        ),
        title=chart.title,
        width=chart.width,
        height=chart.height,
        name=chart.name,
    )


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
