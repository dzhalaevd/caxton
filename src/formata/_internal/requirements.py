from __future__ import annotations

from formata.core.formatting import DocumentTheme, Style, StyleInput
from formata.core.ir import SPREADSHEET_IR_VERSION
from formata.core.models import Column, DocumentKind, SpreadsheetDocument
from formata.core.protocols import DataSourceInfo, Repeatability
from formata.core.rendering import (
    DataSourceRequirements,
    ExecutionMode,
    ExecutionRequirements,
    RequiredCapabilities,
    WorkbookOperation,
)


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
        append_only = append_only and len(worksheet.blocks) == 1
        for table_index, table in enumerate(worksheet.blocks):
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
            if table.freeze is not None:
                features.add("freeze_panes")
            if table.auto_width:
                features.add("auto_width")
            for column in table.columns:
                features.update(_column_features(column, document))
            data_sources.append(
                _source_requirements(
                    table.data.source,
                    worksheet_index=worksheet_index,
                    table_index=table_index,
                ),
            )
    return RequiredCapabilities(
        document_kind=DocumentKind.SPREADSHEET,
        ir_versions=frozenset((SPREADSHEET_IR_VERSION,)),
        features=frozenset(features),
        workbook_operation=WorkbookOperation.CREATE_NEW_WORKBOOK,
        execution=ExecutionRequirements(
            mode=ExecutionMode(mode),
            data_sources=tuple(data_sources),
            append_only=append_only,
            has_named_tables=has_named_tables,
        ),
    )


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


def _column_features(  # noqa: C901
    column: Column,
    document: SpreadsheetDocument,
) -> set[str]:
    features = {f"semantic:{column.semantic_type.name}"}
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
