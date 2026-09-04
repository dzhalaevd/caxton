from __future__ import annotations

from collections.abc import Sequence

from caxton._internal.shape import table_needs_preparation
from caxton.core.formatting import DocumentTheme, Style, StyleInput
from caxton.core.ir import SPREADSHEET_IR_VERSION
from caxton.core.models import (
    AggregateExpr,
    Chart,
    Column,
    DocumentKind,
    Image,
    Matrix,
    Spacer,
    SpreadsheetBlock,
    SpreadsheetDocument,
    SpreadsheetTable,
    Stack,
    TemplateRepeat,
    Title,
    iter_blocks,
    iter_tables,
)
from caxton.core.protocols import DataSourceInfo, Repeatability
from caxton.core.rendering import (
    DataSourceRequirements,
    ExecutionMode,
    ExecutionRequirements,
    RequiredCapabilities,
    WorkbookOperation,
)
from caxton.core.types import BUILTIN_SEMANTIC_TYPES, SemanticType


def analyze_spreadsheet_requirements(  # noqa: C901, WPS213
    document: SpreadsheetDocument,
    *,
    mode: ExecutionMode | str = ExecutionMode.AUTO,
) -> RequiredCapabilities:
    """Discover renderer features without evaluating table rows.

    Returns:
        The immutable capability requirements for this document.
    """
    features: set[str] = set()
    data_sources: list[DataSourceRequirements] = []
    has_named_tables = False
    requires_buffering = False
    append_only = bool(document.worksheets)
    if document.theme != DocumentTheme():
        features.add("style")
        for style in (
            document.theme.default,
            document.theme.header,
            document.theme.total,
        ):
            features.update(_resolved_style_features(style))
    for worksheet_index, worksheet in enumerate(document.worksheets):
        if worksheet.freeze is not None:
            features.add("freeze_panes")
        blocks = tuple(iter_blocks(worksheet.blocks))
        features.update(_block_features(blocks))
        append_only = (
            append_only
            and len(blocks) == 1
            and isinstance(blocks[0], SpreadsheetTable)
            and not table_needs_preparation(blocks[0])
        )
        tables = tuple(iter_tables(worksheet.blocks))
        for table_index, table in enumerate(tables):
            features.add("table")
            if table.name is not None:
                features.add("native_table")
                has_named_tables = True
            if table.anchor is not None:
                features.add("explicit_anchor")
            if table.style is not None or table.header_style is not None:
                features.add("style")
                features.update(_style_features(table.style, document))
                features.update(_style_features(table.header_style, document))
            if table.footer is not None:
                features.update(("style", "totals"))
                features.update(_style_features(table.footer.style, document))
            if table.rules:
                features.update(("conditional_format", "formula", "style"))
            if table.autofilter:
                features.add("autofilter")
            if table.freeze_header:
                features.add("freeze_panes")
            if table.auto_width:
                features.add("auto_width")
            if any(
                isinstance(column.source, AggregateExpr) for column in table.columns
            ):
                features.add("aggregation")
            if table_needs_preparation(table):
                requires_buffering = True
            if any(column.grouping is not None for column in table.columns):
                features.add("grouping")
            if any(
                column.grouping is not None and column.grouping.merge
                for column in table.columns
            ):
                features.add("merge_cells")
            for column in table.columns:
                features.update(_column_features(column, document))
            data_sources.append(
                _source_requirements(
                    table.data.source,
                    worksheet_index=worksheet_index,
                    table_index=table_index,
                ),
            )
        matrices = tuple(block for block in blocks if isinstance(block, Matrix))
        for matrix_index, block in enumerate(matrices):
            requires_buffering = True
            features.update(("matrix", "table"))
            if block.anchor is not None:
                features.add("explicit_anchor")
            if block.style is not None or block.header_style is not None:
                features.add("style")
                features.update(_style_features(block.style, document))
                features.update(_style_features(block.header_style, document))
            if isinstance(block.value.source, AggregateExpr):
                features.add("aggregation")
            for column in (
                *block.row_dimensions,
                *block.column_dimensions,
                block.value,
            ):
                features.update(_column_features(column, document))
            data_sources.append(
                _source_requirements(
                    block.source,
                    worksheet_index=worksheet_index,
                    table_index=len(tables) + matrix_index,
                ),
            )
    if document.template is not None:
        features.update(("template", "template_references"))
        if any(
            table.into is not None
            for worksheet in document.worksheets
            for table in iter_tables(worksheet.blocks)
        ):
            features.add("xlsx_named_ranges")
        if any(
            isinstance(table.into, TemplateRepeat)
            for worksheet in document.worksheets
            for table in iter_tables(worksheet.blocks)
        ):
            features.add("template_repeat")
        for extension in document.template.extensions:
            features.update(extension.required_capabilities)
    return RequiredCapabilities(
        document_kind=DocumentKind.SPREADSHEET,
        ir_versions=frozenset((SPREADSHEET_IR_VERSION,)),
        features=frozenset(features),
        workbook_operation=(
            WorkbookOperation.CREATE_NEW_WORKBOOK
            if document.template is None
            else WorkbookOperation.USE_EXISTING_TEMPLATE
        ),
        execution=ExecutionRequirements(
            mode=ExecutionMode(mode),
            data_sources=tuple(data_sources),
            append_only=append_only,
            has_named_tables=has_named_tables,
            requires_buffering=requires_buffering,
        ),
    )


def _block_feature(block: SpreadsheetBlock) -> str | None:
    if isinstance(block, Title):
        return "text"
    if isinstance(block, Spacer):
        return "spacer"
    if isinstance(block, Image):
        return "image"
    if isinstance(block, Chart):
        return "chart"
    return "stack" if isinstance(block, Stack) else None


def _block_features(blocks: Sequence[SpreadsheetBlock]) -> set[str]:
    features: set[str] = set()
    for block in blocks:
        feature = _block_feature(block)
        if feature is not None:
            features.update(("flow_layout", feature))
    return features


def _source_requirements(
    source: object,
    *,
    worksheet_index: int,
    table_index: int,
) -> DataSourceRequirements:
    if isinstance(source, DataSourceInfo):
        repeatability = source.repeatability
        row_count = source.row_count
    else:
        repeatability = Repeatability.UNKNOWN
        row_count = None
    return DataSourceRequirements(
        worksheet_index=worksheet_index,
        table_index=table_index,
        repeatability=repeatability,
        row_count=row_count,
    )


def _semantic_feature(semantic_type: SemanticType) -> str:
    if isinstance(semantic_type, BUILTIN_SEMANTIC_TYPES):
        return f"semantic:{semantic_type.name}"
    return "semantic:extension"


def _column_features(  # noqa: C901
    column: Column,
    document: SpreadsheetDocument,
) -> set[str]:
    features = {_semantic_feature(column.semantic_type)}
    if column.alignment is not None:
        features.add("alignment")
    if column.width_hint is not None:
        features.add("column_width")
    if column.display_format is not None:
        features.add("display_format")
    if column.excel_formula is not None:
        features.add("formula")
    if column.style_ref is not None:
        features.add("style")
        features.update(_style_features(column.style_ref, document))
    if column.auto_width:
        features.add("auto_width")
    return features


def _style_features(
    value: StyleInput | None,
    document: SpreadsheetDocument,
) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        resolved = document.styles.styles.get(value)
        return set() if resolved is None else _resolved_style_features(resolved)
    return _resolved_style_features(value)


def _resolved_style_features(style: Style) -> set[str]:
    return {"display_format"} if style.display_format is not None else set()


__all__ = ("analyze_spreadsheet_requirements",)
