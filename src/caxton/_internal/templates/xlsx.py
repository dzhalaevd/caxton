from __future__ import annotations

import dataclasses
from collections.abc import Iterator, Sequence
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from openpyxl import Workbook, load_workbook
from openpyxl.utils.cell import range_boundaries
from openpyxl.workbook.defined_name import DefinedName

from caxton._internal.backends.openpyxl.extensions import PivotBinding
from caxton._internal.compiler import SpreadsheetCompiler
from caxton.core.errors import (
    AmbiguousTemplateRefError,
    IncompatibleTemplateRefError,
    InvalidTemplateRefError,
    MissingTemplateRefError,
    TemplateError,
)
from caxton.core.ir import CellAddress, SpreadsheetIR
from caxton.core.models import (
    ColumnRef,
    SpreadsheetBlock,
    SpreadsheetDocument,
    SpreadsheetTable,
    TemplateCompilationResult,
    TemplateContext,
    TemplateRepeat,
    TemplateSpecification,
    iter_tables,
)
from caxton.core.protocols import DataSourceInfo

if TYPE_CHECKING:
    from caxton._internal.backends.openpyxl.package import PivotDescriptor


@dataclasses.dataclass(frozen=True, slots=True)
class XlsxDefinedName:
    """Read-only defined-name facts without an OpenPyXL object."""

    name: str
    scope: str | None
    destinations: Sequence[tuple[str, str]]
    valid_range: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "destinations", tuple(self.destinations))


@dataclasses.dataclass(frozen=True, slots=True)
class XlsxNamedRange:
    """Backend-local physical descriptor resolved from a generic reference."""

    reference: str
    sheet: str
    min_row: int
    min_column: int
    max_row: int
    max_column: int
    scope: str | None = None
    namespace: str = dataclasses.field(default="xlsx.named_range", init=False)

    @property
    def rows(self) -> int:
        return self.max_row - self.min_row + 1

    @property
    def columns(self) -> int:
        return self.max_column - self.min_column + 1


@dataclasses.dataclass(frozen=True, slots=True)
class XlsxTemplateContext(TemplateContext):
    """XLSX inspection result containing bytes and plain descriptors only."""

    payload: bytes = dataclasses.field(repr=False, default=b"")
    worksheets: Sequence[str] = ()
    defined_names: Sequence[XlsxDefinedName] = ()
    pivots: Sequence[PivotDescriptor] = ()

    def __post_init__(self) -> None:
        TemplateContext.__post_init__(self)
        object.__setattr__(self, "payload", bytes(self.payload))
        object.__setattr__(self, "worksheets", tuple(self.worksheets))
        object.__setattr__(self, "defined_names", tuple(self.defined_names))
        object.__setattr__(self, "pivots", tuple(self.pivots))

    @property
    def pivot_names(self) -> tuple[str, ...]:
        return tuple(pivot.name for pivot in self.pivots)


@dataclasses.dataclass(frozen=True, slots=True)
class XlsxTableTarget:
    """Resolved target for one compiled table in one worksheet IR."""

    reference: str
    worksheet_index: int
    table_index: int
    range: XlsxNamedRange
    repeat: bool = False
    namespace: str = dataclasses.field(default="xlsx.table_target", init=False)


class XlsxTemplateInspector:
    """Read an XLSX template without mutating or serializing it."""

    def inspect(self, template: TemplateSpecification) -> XlsxTemplateContext:
        if template.format != "xlsx":
            message = f"XLSX inspector cannot inspect {template.format!r}"
            raise TemplateError(message, context={"format": template.format})
        payload, source = _read_source(template.source)
        try:
            workbook = load_workbook(BytesIO(payload), data_only=False)
        except Exception as error:
            message = "Could not inspect the XLSX template"
            raise TemplateError(message, context={"source": source}) from error
        try:
            names = tuple(_defined_names(workbook))
            worksheets = tuple(worksheet.title for worksheet in workbook.worksheets)
        finally:
            workbook.close()
        from caxton._internal.backends.openpyxl.package import (  # noqa: PLC0415
            inspect_pivots,
        )

        return XlsxTemplateContext(
            format="xlsx",
            source=source,
            references=tuple(name.name for name in names),
            payload=payload,
            worksheets=worksheets,
            defined_names=names,
            pivots=inspect_pivots(payload),
        )


class XlsxTemplateCompiler:
    """Resolve generic template targets and lower spreadsheet intent."""

    def compile(  # noqa: C901
        self,
        document: SpreadsheetDocument,
        context: XlsxTemplateContext,
    ) -> TemplateCompilationResult[SpreadsheetIR]:
        anchors: dict[SpreadsheetBlock, CellAddress] = {}
        targets: list[XlsxTableTarget] = []
        for worksheet_index, worksheet in enumerate(document.worksheets):
            if worksheet.name not in context.worksheets:
                message = f"Worksheet {worksheet.name!r} is absent from the template"
                raise IncompatibleTemplateRefError(
                    message,
                    context={"worksheet": worksheet.name},
                )
            for table_index, table in enumerate(iter_tables(worksheet.blocks)):
                if table.into is None:
                    continue
                reference, repeated = _table_reference(table)
                resolved = _resolve_named_range(context, reference, worksheet.name)
                if len(table.columns) > resolved.columns:
                    message = f"Template target {reference!r} is too narrow"
                    raise IncompatibleTemplateRefError(
                        message,
                        context={
                            "available_columns": resolved.columns,
                            "required_columns": len(table.columns),
                            "reference": reference,
                        },
                    )
                _validate_target_height(table, resolved, repeated)
                anchors[table] = CellAddress(
                    row=resolved.min_row,
                    column=resolved.min_column,
                )
                targets.append(
                    XlsxTableTarget(
                        reference=reference,
                        worksheet_index=worksheet_index,
                        table_index=table_index,
                        range=resolved,
                        repeat=repeated,
                    ),
                )
        _validate_target_overlaps(targets)
        compiled = SpreadsheetCompiler().compile_validated(
            document,
            anchor_overrides=anchors,
            check_overlaps=False,
        )
        template = document.template
        if template is None:
            message = "Template compilation requires a template"
            raise RuntimeError(message)
        _validate_extensions(document, context, template.extensions)
        return TemplateCompilationResult(
            document=compiled,
            context=context,
            targets=tuple(targets),
            extensions=template.extensions,
        )


def _read_source(source: str | bytes) -> tuple[bytes, str]:
    if isinstance(source, bytes):
        return source, "bytes"
    try:
        return Path(source).read_bytes(), source
    except OSError as error:
        message = "Could not read the template source"
        raise TemplateError(message, context={"source": source}) from error


def _defined_names(workbook: Workbook) -> Iterator[XlsxDefinedName]:
    for name in workbook.defined_names.values():
        yield _defined_name(name, None)
    for worksheet in workbook.worksheets:
        for name in worksheet.defined_names.values():
            yield _defined_name(name, worksheet.title)


def _defined_name(name: DefinedName, scope: str | None) -> XlsxDefinedName:
    valid = getattr(name, "type", None) == "RANGE"
    try:
        destinations = tuple(name.destinations) if valid else ()
    except (AttributeError, TypeError, ValueError):
        destinations = ()
        valid = False
    return XlsxDefinedName(
        name=str(name.name),
        scope=scope,
        destinations=destinations,
        valid_range=valid,
    )


def _table_reference(table: SpreadsheetTable) -> tuple[str, bool]:
    target = table.into
    if isinstance(target, TemplateRepeat):
        return target.reference.column_id, True
    if isinstance(target, ColumnRef):
        return target.column_id, False
    message = "Table target was not normalized"
    raise RuntimeError(message)


def _resolve_named_range(  # noqa: C901, WPS238
    context: XlsxTemplateContext,
    reference: str,
    worksheet: str,
) -> XlsxNamedRange:
    matching = tuple(
        item
        for item in context.defined_names
        if item.name.casefold() == reference.casefold()
    )
    local = tuple(item for item in matching if item.scope == worksheet)
    applicable = local or tuple(item for item in matching if item.scope is None)
    if not applicable:
        message = f"Template reference {reference!r} was not found"
        raise MissingTemplateRefError(
            message,
            context={"reference": reference, "worksheet": worksheet},
        )
    if len(applicable) != 1 or len(applicable[0].destinations) != 1:
        message = f"Template reference {reference!r} is ambiguous"
        raise AmbiguousTemplateRefError(
            message,
            context={"reference": reference, "worksheet": worksheet},
        )
    selected = applicable[0]
    if not selected.valid_range:
        message = f"Template reference {reference!r} is not a cell range"
        raise InvalidTemplateRefError(message, context={"reference": reference})
    target_sheet, coordinates = selected.destinations[0]
    if target_sheet != worksheet:
        message = f"Template reference {reference!r} targets another worksheet"
        raise IncompatibleTemplateRefError(
            message,
            context={
                "declared_worksheet": worksheet,
                "reference": reference,
                "target_worksheet": target_sheet,
            },
        )
    try:
        min_column, min_row, max_column, max_row = range_boundaries(coordinates)
    except (TypeError, ValueError) as error:
        message = f"Template reference {reference!r} has an invalid range"
        raise InvalidTemplateRefError(message) from error
    if min_column is None or min_row is None or max_column is None or max_row is None:
        message = f"Template reference {reference!r} is not a rectangular range"
        raise InvalidTemplateRefError(message)
    return XlsxNamedRange(
        reference=reference,
        sheet=target_sheet,
        min_row=min_row,
        min_column=min_column,
        max_row=max_row,
        max_column=max_column,
        scope=selected.scope,
    )


def _validate_extensions(  # noqa: C901, WPS238
    document: SpreadsheetDocument,
    context: XlsxTemplateContext,
    extensions: Sequence[object],
) -> None:
    tables = tuple(
        table
        for worksheet in document.worksheets
        for table in iter_tables(worksheet.blocks)
    )
    for extension in extensions:
        if not isinstance(extension, PivotBinding):
            continue
        matching = tuple(
            pivot
            for pivot in context.pivots
            if pivot.name.casefold() == extension.target.casefold()
        )
        if not matching:
            message = f"Pivot target {extension.target!r} was not found"
            raise MissingTemplateRefError(
                message,
                context={"pivot": extension.target},
            )
        if len(matching) > 1:
            message = f"Pivot target {extension.target!r} is ambiguous"
            raise AmbiguousTemplateRefError(message)
        if matching[0].cache_definition_part is None:
            message = f"Pivot target {extension.target!r} has no cache definition"
            raise InvalidTemplateRefError(message)
        if not _has_pivot_source(tables, extension):
            source = _pivot_source_name(extension)
            message = f"Pivot source {source!r} was not found"
            raise MissingTemplateRefError(message, context={"source": source})


def _has_pivot_source(
    tables: Sequence[SpreadsheetTable],
    binding: PivotBinding,
) -> bool:
    source = _pivot_source_name(binding).casefold()
    return any(
        (table.name is not None and table.name.casefold() == source)
        or (table.into is not None and _table_reference(table)[0].casefold() == source)
        for table in tables
    )


def _pivot_source_name(binding: PivotBinding) -> str:
    source = binding.source
    return source.column_id if isinstance(source, ColumnRef) else source.name


def _validate_target_height(
    table: SpreadsheetTable,
    target: XlsxNamedRange,
    repeated: bool,
) -> None:
    source = table.data.source
    row_count = source.row_count if isinstance(source, DataSourceInfo) else None
    if repeated or row_count is None or row_count <= target.rows:
        return
    message = f"Template target {target.reference!r} has too few rows"
    raise IncompatibleTemplateRefError(
        message,
        context={
            "available_rows": target.rows,
            "reference": target.reference,
            "required_rows": row_count,
        },
    )


def _validate_target_overlaps(targets: Sequence[XlsxTableTarget]) -> None:
    for index, first in enumerate(targets):
        for second in targets[index + 1 :]:
            if _targets_intersect(first.range, second.range):
                message = (
                    f"Template targets {first.reference!r} and "
                    f"{second.reference!r} overlap"
                )
                raise IncompatibleTemplateRefError(message)


def _targets_intersect(first: XlsxNamedRange, second: XlsxNamedRange) -> bool:
    rows_intersect = first.min_row <= second.max_row and second.min_row <= first.max_row
    columns_intersect = (
        first.min_column <= second.max_column and second.min_column <= first.max_column
    )
    return first.sheet == second.sheet and rows_intersect and columns_intersect


__all__ = (
    "XlsxDefinedName",
    "XlsxNamedRange",
    "XlsxTableTarget",
    "XlsxTemplateCompiler",
    "XlsxTemplateContext",
    "XlsxTemplateInspector",
)
