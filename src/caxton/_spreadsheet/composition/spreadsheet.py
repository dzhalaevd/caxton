from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from types import MappingProxyType
from typing import TypeVar

from caxton.core.errors import (
    CaxtonTypeError,
    CaxtonValueError,
    InvalidOperationError,
    UnsupportedFeatureError,
)
from caxton.core.formatting import DocumentTheme, Style, StyleSheet
from caxton.core.models import (
    CellReference,
    Chart,
    Column,
    ConditionalRule,
    Formula,
    FormulaBinary,
    FormulaLiteral,
    Image,
    Matrix,
    RangeReference,
    Spacer,
    SpreadsheetBlock,
    SpreadsheetDocument,
    SpreadsheetTable,
    Stack,
    TableReference,
    TemplateSpecification,
    Title,
    Worksheet,
)


@dataclasses.dataclass(frozen=True, slots=True)
class _SectionPlan:
    name: str
    document: SpreadsheetDocument
    worksheet_names: Mapping[str, str]


@dataclasses.dataclass(frozen=True, slots=True)
class _RebaseContext:
    section: _SectionPlan
    worksheet: str

    @property
    def path(self) -> str:
        return f"sections[{self.section.name!r}].worksheet[{self.worksheet!r}]"

    def resolve_worksheet(self, requested: str) -> str:
        resolved = self.section.worksheet_names.get(requested)
        if resolved is not None:
            return resolved
        message = (
            f"Worksheet {requested!r} is outside composed section {self.section.name!r}"
        )
        raise InvalidOperationError(
            message,
            path=self.path,
            context={
                "reason": "cross_section_reference",
                "section": self.section.name,
                "worksheet": self.worksheet,
                "requested_worksheet": requested,
            },
        )


_ReferenceT = TypeVar(
    "_ReferenceT",
    bound=CellReference | RangeReference | TableReference,
)


def compose_spreadsheet(
    sections: Mapping[str, SpreadsheetDocument],
    *,
    metadata: Mapping[str, object] | None,
    styles: StyleSheet | None,
    theme: DocumentTheme | None,
    template: TemplateSpecification | None,
) -> SpreadsheetDocument:
    """Return one spreadsheet containing every named section.

    Raises:
        CaxtonValueError: If the composition contains no worksheets.
    """
    plan = _plan_sections(_validated_sections(sections))
    worksheets = tuple(
        _compose_worksheet(section, worksheet)
        for section in plan
        for worksheet in section.document.worksheets
    )
    if not worksheets:
        message = "Spreadsheet composition requires at least one worksheet"
        raise CaxtonValueError(
            message,
            context={"reason": "empty_composition"},
        )
    return SpreadsheetDocument(
        worksheets=worksheets,
        metadata=_merge_metadata(plan, metadata),
        styles=_merge_styles(plan, styles),
        theme=_select_theme(plan, theme),
        template=template,
    )


def _validated_sections(
    sections: object,
) -> tuple[tuple[str, SpreadsheetDocument], ...]:
    if not isinstance(sections, Mapping):
        message = "Sections must be a mapping"
        raise CaxtonTypeError(
            message,
            context={"type": type(sections).__name__},
        )
    normalized: list[tuple[str, SpreadsheetDocument]] = []
    seen: dict[str, str] = {}
    for index, (section, document) in enumerate(sections.items()):
        validated = _validate_section(
            section,
            document,
            index=index,
            seen=seen,
        )
        normalized.append(validated)
    return tuple(normalized)


def _validate_section(
    section: object,
    document: object,
    *,
    index: int,
    seen: dict[str, str],
) -> tuple[str, SpreadsheetDocument]:
    name, normalized = _validate_section_name(section, index=index, seen=seen)
    child = _validate_section_document(name, document)
    seen[normalized] = name
    return name, child


def _validate_section_name(
    section: object,
    *,
    index: int,
    seen: dict[str, str],
) -> tuple[str, str]:
    if not isinstance(section, str):
        message = "Section name must be a string"
        raise CaxtonTypeError(
            message,
            path=f"sections[{index}]",
            context={"index": index, "type": type(section).__name__},
        )
    if not section.strip():
        message = "Section name cannot be empty"
        raise CaxtonValueError(
            message,
            path=f"sections[{index}]",
            context={"index": index},
        )
    normalized = section.casefold()
    owner = seen.get(normalized)
    if owner is not None:
        message = f"Duplicate section name {section!r}"
        raise InvalidOperationError(
            message,
            path=f"sections[{index}]",
            context={
                "reason": "duplicate_section",
                "section": section,
                "conflicts_with": owner,
            },
        )
    return section, normalized


def _validate_section_document(
    section: str,
    document: object,
) -> SpreadsheetDocument:
    if not isinstance(document, SpreadsheetDocument):
        message = f"Section {section!r} must contain a spreadsheet document"
        raise CaxtonTypeError(
            message,
            path=f"sections[{section!r}]",
            context={"section": section, "type": type(document).__name__},
        )
    if document.template is not None:
        message = f"Section {section!r} cannot own a workbook template"
        raise InvalidOperationError(
            message,
            path=f"sections[{section!r}].template",
            context={
                "reason": "included_template",
                "section": section,
            },
        )
    return document


def _plan_sections(
    sections: tuple[tuple[str, SpreadsheetDocument], ...],
) -> tuple[_SectionPlan, ...]:
    owners: dict[str, tuple[str, str]] = {}
    output: list[_SectionPlan] = []
    for section, document in sections:
        if not document.worksheets:
            continue
        worksheet_names = _plan_worksheet_names(section, document, owners)
        output.append(
            _SectionPlan(
                name=section,
                document=document,
                worksheet_names=MappingProxyType(worksheet_names),
            ),
        )
    return tuple(output)


def _plan_worksheet_names(
    section: str,
    document: SpreadsheetDocument,
    owners: dict[str, tuple[str, str]],
) -> dict[str, str]:
    planned: dict[str, str] = {}
    for worksheet in document.worksheets:
        output_name = f"{section} - {worksheet.name}"
        normalized = output_name.casefold()
        owner = owners.get(normalized)
        if owner is not None:
            _raise_worksheet_name_conflict(
                output_name,
                section=section,
                local_worksheet=worksheet.name,
                owner=owner,
            )
        owners[normalized] = (section, worksheet.name)
        planned[worksheet.name] = output_name
    return planned


def _raise_worksheet_name_conflict(
    worksheet: str,
    *,
    section: str,
    local_worksheet: str,
    owner: tuple[str, str],
) -> None:
    message = f"Composed worksheet name {worksheet!r} is not unique"
    raise InvalidOperationError(
        message,
        path=f"sections[{section!r}]",
        context={
            "reason": "worksheet_name_conflict",
            "worksheet": worksheet,
            "section": section,
            "local_worksheet": local_worksheet,
            "conflicts_with_section": owner[0],
            "conflicts_with_worksheet": owner[1],
        },
    )


def _compose_worksheet(
    section: _SectionPlan,
    worksheet: Worksheet,
) -> Worksheet:
    context = _RebaseContext(section=section, worksheet=worksheet.name)
    blocks = tuple(_rebase_block(block, context=context) for block in worksheet.blocks)
    return dataclasses.replace(
        worksheet,
        name=section.worksheet_names[worksheet.name],
        blocks=blocks,
    )


def _rebase_block(
    block: SpreadsheetBlock,
    *,
    context: _RebaseContext,
) -> SpreadsheetBlock:
    if isinstance(block, SpreadsheetTable):
        return _rebase_table(block, context=context)
    if isinstance(block, Chart):
        return _rebase_chart(block, context=context)
    if isinstance(block, Stack):
        return _rebase_stack(block, context=context)
    if isinstance(block, (Matrix, Title, Spacer, Image)):
        return block
    message = f"Unsupported spreadsheet block: {type(block).__name__}"
    raise UnsupportedFeatureError(
        message,
        path=context.path,
        context={
            "reason": "unsupported_spreadsheet_block",
            "section": context.section.name,
            "worksheet": context.worksheet,
            "block_type": type(block).__name__,
        },
    )


def _rebase_chart(
    chart: Chart,
    *,
    context: _RebaseContext,
) -> Chart:
    source = _rebase_reference(chart.source, context=context)
    if source is chart.source:
        return chart
    return dataclasses.replace(chart, source=source)


def _rebase_stack(
    stack: Stack,
    *,
    context: _RebaseContext,
) -> Stack:
    items = tuple(_rebase_block(item, context=context) for item in stack.items)
    if all(left is right for left, right in zip(items, stack.items, strict=True)):
        return stack
    return dataclasses.replace(stack, items=items)


def _rebase_table(
    table: SpreadsheetTable,
    *,
    context: _RebaseContext,
) -> SpreadsheetTable:
    columns = tuple(_rebase_column(column, context=context) for column in table.columns)
    rules = tuple(_rebase_rule(rule, context=context) for rule in table.rules)
    data = table.data
    if not all(
        left is right for left, right in zip(columns, table.columns, strict=True)
    ):
        data = dataclasses.replace(table.data, columns=columns)
    if data is table.data and all(
        left is right for left, right in zip(rules, table.rules, strict=True)
    ):
        return table
    return dataclasses.replace(table, data=data, rules=rules)


def _rebase_column(
    column: Column,
    *,
    context: _RebaseContext,
) -> Column:
    if column.excel_formula is None:
        return column
    formula = _rebase_formula(
        column.excel_formula,
        context=context,
    )
    if formula is column.excel_formula:
        return column
    return dataclasses.replace(column, excel_formula=formula)


def _rebase_rule(
    rule: ConditionalRule,
    *,
    context: _RebaseContext,
) -> ConditionalRule:
    condition = _rebase_formula(
        rule.condition,
        context=context,
    )
    if condition is rule.condition:
        return rule
    return dataclasses.replace(rule, condition=condition)


def _rebase_formula(
    formula: Formula,
    *,
    context: _RebaseContext,
) -> Formula:
    if isinstance(formula, (CellReference, RangeReference)):
        return _rebase_reference(formula, context=context)
    if isinstance(formula, FormulaBinary):
        left = _rebase_formula(formula.left, context=context)
        right = _rebase_formula(formula.right, context=context)
        if left is formula.left and right is formula.right:
            return formula
        return dataclasses.replace(formula, left=left, right=right)
    if isinstance(formula, FormulaLiteral):
        return formula
    message = f"Unsupported formula node: {type(formula).__name__}"
    raise UnsupportedFeatureError(
        message,
        path=context.path,
        context={
            "reason": "unsupported_formula_node",
            "section": context.section.name,
            "worksheet": context.worksheet,
            "formula_type": type(formula).__name__,
        },
    )


def _rebase_reference(
    reference: _ReferenceT,
    *,
    context: _RebaseContext,
) -> _ReferenceT:
    if reference.sheet_name is None:
        return reference
    sheet_name = context.resolve_worksheet(reference.sheet_name)
    return dataclasses.replace(reference, sheet_name=sheet_name)


def _merge_styles(
    sections: tuple[_SectionPlan, ...],
    outer: StyleSheet | None,
) -> StyleSheet:
    merged: dict[str, Style] = {}
    owners: dict[str, str] = {}
    for section in sections:
        _merge_section_styles(section, merged, owners, outer)
    if outer is not None:
        merged.update(outer)
    return StyleSheet(merged)


def _merge_section_styles(
    section: _SectionPlan,
    merged: dict[str, Style],
    owners: dict[str, str],
    outer: StyleSheet | None,
) -> None:
    for name, style in section.document.styles.items():
        existing = merged.get(name)
        if (
            existing is not None
            and existing != style
            and (outer is None or name not in outer)
        ):
            _raise_style_conflict(
                name,
                section=section.name,
                owner=owners[name],
            )
        if existing is None:
            merged[name] = style
            owners[name] = section.name


def _raise_style_conflict(name: str, *, section: str, owner: str) -> None:
    message = f"Style {name!r} has conflicting definitions"
    raise InvalidOperationError(
        message,
        path=f"sections[{section!r}].styles[{name!r}]",
        context={
            "reason": "style_conflict",
            "style": name,
            "section": section,
            "conflicts_with": owner,
        },
    )


def _select_theme(
    sections: tuple[_SectionPlan, ...],
    outer: DocumentTheme | None,
) -> DocumentTheme:
    if outer is not None:
        return outer
    default = DocumentTheme()
    selected = default
    owner: str | None = None
    for section in sections:
        candidate = section.document.theme
        if candidate == default:
            continue
        if selected == default:
            selected = candidate
            owner = section.name
            continue
        if candidate != selected:
            _raise_theme_conflict(section.name, owner)
    return selected


def _raise_theme_conflict(section: str, owner: str | None) -> None:
    message = "Composed sections define conflicting document themes"
    raise InvalidOperationError(
        message,
        path=f"sections[{section!r}].theme",
        context={
            "reason": "theme_conflict",
            "section": section,
            "conflicts_with": owner,
        },
    )


def _merge_metadata(
    sections: tuple[_SectionPlan, ...],
    outer: Mapping[str, object] | None,
) -> Mapping[str, object]:
    if outer is not None:
        return outer
    merged: dict[str, object] = {}
    owners: dict[str, str] = {}
    for section in sections:
        for key, value in section.document.metadata.items():
            if key in merged and merged[key] != value:
                _raise_metadata_conflict(
                    key,
                    section=section.name,
                    owner=owners[key],
                )
            if key not in merged:
                merged[key] = value
                owners[key] = section.name
    return merged


def _raise_metadata_conflict(key: str, *, section: str, owner: str) -> None:
    message = f"Metadata key {key!r} has conflicting values"
    raise InvalidOperationError(
        message,
        path=f"sections[{section!r}].metadata[{key!r}]",
        context={
            "reason": "metadata_conflict",
            "key": key,
            "section": section,
            "conflicts_with": owner,
        },
    )


__all__ = ("compose_spreadsheet",)
