from __future__ import annotations

import dataclasses
import enum
import hashlib
import json
import types
from collections.abc import Mapping, Sequence, Set as AbstractSet

from caxton.core._compat import StrEnum
from caxton.core._values import freeze_mapping, freeze_value
from caxton.core.formatting import (
    Alignment,
    AutoWidth,
    DisplayFormat,
    DocumentTheme,
    StyleInput,
    StyleSheet,
)
from caxton.core.formatting.widths import resolve_auto_width
from caxton.core.ir import SpreadsheetBlockKind as BlockKind
from caxton.core.models import (
    AggregateExpr,
    BinaryExpression,
    CallableSource,
    CellReference,
    Chart,
    Column,
    ColumnRef,
    ColumnSource,
    FieldRef,
    FormulaBinary,
    FormulaLiteral,
    Freeze,
    Grouping,
    Image,
    LiteralExpression,
    Matrix,
    PathRef,
    RangeReference,
    RowCallable,
    Spacer,
    SpreadsheetBlock,
    SpreadsheetDocument,
    SpreadsheetTable,
    Title,
    Totals,
    TransformCallable,
    TransformExpression,
    iter_tables,
)
from caxton.core.models.common import freeze_metadata
from caxton.core.types import SemanticType


class SourceKind(StrEnum):
    """Stable kinds of semantic column source."""

    FIELD = "field"
    COLUMN = "column"
    PATH = "path"
    LITERAL = "literal"
    BINARY = "binary"
    CALLABLE = "callable"
    AGGREGATE = "aggregate"
    TRANSFORM = "transform"


class FormulaKind(StrEnum):
    """Stable kinds of artifact formula nodes."""

    LITERAL = "literal"
    BINARY = "binary"
    CELL = "cell"
    RANGE = "range"


@dataclasses.dataclass(frozen=True, slots=True)
class CallableSpec:
    """Stable identity and diagnostic name of a callable source."""

    module: str | None
    qualname: str
    identity: str


@dataclasses.dataclass(frozen=True, slots=True)
class SourceSpec:
    """Immutable syntax tree for one semantic column source."""

    kind: SourceKind
    value: object = None
    operands: Sequence[SourceSpec] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            freeze_value(self.value, label="Column source"),
        )
        object.__setattr__(self, "operands", tuple(self.operands))


@dataclasses.dataclass(frozen=True, slots=True)
class FormulaSpec:
    """Immutable syntax tree for one semantic artifact formula."""

    kind: FormulaKind
    value: object = None
    operands: Sequence[FormulaSpec] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            freeze_value(self.value, label="Formula specification"),
        )
        object.__setattr__(self, "operands", tuple(self.operands))


@dataclasses.dataclass(frozen=True, slots=True)
class SemanticTypeSpec:
    """Stable semantic type identity and type-specific parameters."""

    name: str
    parameters: Mapping[str, object] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "parameters",
            freeze_mapping(self.parameters, label="Semantic type parameters"),
        )


@dataclasses.dataclass(frozen=True, slots=True)
class ColumnSpec:
    """Stable, read-only description of one semantic column."""

    id: str
    title: str
    semantic_type: SemanticTypeSpec
    source: SourceSpec | None
    alignment: Alignment | None
    width: float | None
    display_format: DisplayFormat | None
    formula: FormulaSpec | None = None
    style: StyleInput | None = None
    auto_width: AutoWidth | None = None
    grouping: Grouping | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class MatrixSpec:
    """Stable semantic description of a declarative matrix."""

    row_dimensions: Sequence[ColumnSpec]
    column_dimensions: Sequence[ColumnSpec]
    value: ColumnSpec

    def __post_init__(self) -> None:
        object.__setattr__(self, "row_dimensions", tuple(self.row_dimensions))
        object.__setattr__(self, "column_dimensions", tuple(self.column_dimensions))


@dataclasses.dataclass(frozen=True, slots=True)
class ConditionalRuleSpec:
    """Stable conditional rule syntax and style intent."""

    condition: FormulaSpec
    style: StyleInput


@dataclasses.dataclass(frozen=True, slots=True)
class TableSpec:
    """Stable, read-only description of one semantic table."""

    name: str | None
    anchor: str | None
    columns: Sequence[ColumnSpec]
    style: StyleInput | None = None
    header_style: StyleInput | None = None
    footer: Totals | None = None
    rules: Sequence[ConditionalRuleSpec] = ()
    autofilter: bool = False
    freeze_header: bool = False
    auto_width: AutoWidth | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "columns", tuple(self.columns))
        object.__setattr__(self, "rules", tuple(self.rules))

    @property
    def column_ids(self) -> tuple[str, ...]:
        """Semantic column identities in declaration order."""
        return tuple(column.id for column in self.columns)

    def column(self, column_id: str) -> ColumnSpec:
        """Select a column by semantic identity.

        Returns:
            The selected column description.

        Raises:
            LookupError: If no column has the requested identity.
        """
        for column in self.columns:
            if column.id == column_id:
                return column
        message = f"Column {column_id!r} was not found in table {_table_label(self)}"
        raise LookupError(message)


@dataclasses.dataclass(frozen=True, slots=True)
class BlockSpec:
    """Stable, read-only description of one declared layout block."""

    kind: BlockKind
    anchor: str | None = None
    name: str | None = None
    text: str | None = None
    rows: int | None = None
    columns: int | None = None
    width: int | None = None
    height: int | None = None
    chart_kind: str | None = None
    source: str | None = None
    category: str | None = None
    values: Sequence[str] = ()
    direction: str | None = None
    gap: int | None = None
    items: Sequence[BlockSpec] = ()
    matrix: MatrixSpec | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", tuple(self.values))
        object.__setattr__(self, "items", tuple(self.items))


@dataclasses.dataclass(frozen=True, slots=True)
class WorksheetSpec:
    """Stable, read-only description of one semantic worksheet."""

    name: str
    tables: Sequence[TableSpec]
    freeze: Freeze | None = None
    blocks: Sequence[BlockSpec] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "tables", tuple(self.tables))
        object.__setattr__(self, "blocks", tuple(self.blocks))

    def table(self, name: str) -> TableSpec:
        """Select a named table.

        Returns:
            The selected table description.

        Raises:
            LookupError: If no table has the requested name.
        """
        for table in self.tables:
            if table.name == name:
                return table
        message = f"Table {name!r} was not found in worksheet {self.name!r}"
        raise LookupError(message)


@dataclasses.dataclass(frozen=True, slots=True)
class SpreadsheetSpec:
    """Stable, read-only description of a spreadsheet specification."""

    worksheets: Sequence[WorksheetSpec]
    metadata: Mapping[str, object]
    styles: StyleSheet = dataclasses.field(default_factory=lambda: StyleSheet({}))
    theme: DocumentTheme = dataclasses.field(default_factory=DocumentTheme)

    def __post_init__(self) -> None:
        object.__setattr__(self, "worksheets", tuple(self.worksheets))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def worksheet(self, name: str) -> WorksheetSpec:
        """Select a worksheet by semantic name.

        Returns:
            The selected worksheet description.

        Raises:
            LookupError: If no worksheet has the requested name.
        """
        for worksheet in self.worksheets:
            if worksheet.name == name:
                return worksheet
        message = f"Worksheet {name!r} was not found"
        raise LookupError(message)


def inspect_spec(document: SpreadsheetDocument) -> SpreadsheetSpec:
    """Describe spreadsheet intent without consuming table row sources.

    Returns:
        An immutable value view suitable for ordinary test assertions.
    """
    return SpreadsheetSpec(
        worksheets=tuple(
            WorksheetSpec(
                name=worksheet.name,
                blocks=tuple(_inspect_block(block) for block in worksheet.blocks),
                tables=tuple(
                    TableSpec(
                        name=table.name,
                        anchor=table.anchor,
                        style=table.style,
                        header_style=table.header_style,
                        footer=table.footer,
                        rules=tuple(
                            ConditionalRuleSpec(
                                condition=_inspect_formula(rule.condition),
                                style=rule.style,
                            )
                            for rule in table.rules
                        ),
                        autofilter=table.autofilter,
                        freeze_header=table.freeze_header,
                        auto_width=resolve_auto_width(table.auto_width),
                        columns=tuple(
                            _inspect_column_spec(column) for column in table.columns
                        ),
                    )
                    for table in iter_tables(worksheet.blocks)
                ),
                freeze=worksheet.freeze,
            )
            for worksheet in document.worksheets
        ),
        metadata=document.metadata,
        styles=document.styles,
        theme=document.theme,
    )


def _inspect_block(block: SpreadsheetBlock) -> BlockSpec:  # noqa: C901, WPS212
    if isinstance(block, SpreadsheetTable):
        return BlockSpec(BlockKind.TABLE, anchor=block.anchor, name=block.name)
    if isinstance(block, Title):
        return BlockSpec(
            BlockKind.TITLE,
            anchor=block.anchor,
            text=block.text,
            rows=1,
            columns=block.span,
        )
    if isinstance(block, Spacer):
        return BlockSpec(
            BlockKind.SPACER,
            anchor=block.anchor,
            rows=block.rows,
            columns=block.columns,
        )
    if isinstance(block, Image):
        return BlockSpec(
            BlockKind.IMAGE,
            anchor=block.anchor,
            name=block.name,
            width=block.width,
            height=block.height,
        )
    if isinstance(block, Chart):
        return _inspect_chart_block(block)
    if isinstance(block, Matrix):
        return BlockSpec(
            BlockKind.MATRIX,
            anchor=block.anchor,
            matrix=MatrixSpec(
                row_dimensions=tuple(
                    _inspect_column_spec(column) for column in block.row_dimensions
                ),
                column_dimensions=tuple(
                    _inspect_column_spec(column) for column in block.column_dimensions
                ),
                value=_inspect_column_spec(block.value),
            ),
        )
    return BlockSpec(
        BlockKind.STACK,
        anchor=block.anchor,
        direction=block.direction.value,
        gap=block.gap,
        items=tuple(_inspect_block(item) for item in block.items),
    )


def _inspect_chart_block(chart: Chart) -> BlockSpec:
    return BlockSpec(
        BlockKind.CHART,
        anchor=chart.anchor,
        name=chart.name,
        text=chart.title,
        width=chart.width,
        height=chart.height,
        chart_kind=chart.kind.value,
        source=chart.source.name,
        category=chart.x,
        values=tuple(chart.y),
    )


def _inspect_column_spec(column: Column) -> ColumnSpec:
    return ColumnSpec(
        id=column.id,
        title=column.display_title,
        semantic_type=_inspect_semantic_type(column.semantic_type),
        source=(None if column.source is None else _inspect_source(column.source)),
        formula=(
            None
            if column.excel_formula is None
            else _inspect_formula(column.excel_formula)
        ),
        alignment=column.alignment,
        width=column.width_hint,
        display_format=column.display_format,
        style=column.style_ref,
        auto_width=resolve_auto_width(column.auto_width),
        grouping=column.grouping,
    )


def _table_label(table: TableSpec) -> str:
    return repr(table.name) if table.name is not None else "<unnamed>"


def _inspect_semantic_type(semantic_type: SemanticType) -> SemanticTypeSpec:
    parameters = {
        field.name: getattr(semantic_type, field.name)
        for field in dataclasses.fields(semantic_type)
        if field.init
    }
    return SemanticTypeSpec(name=semantic_type.name, parameters=parameters)


_LEAF_SOURCE_KINDS: Mapping[type, tuple[SourceKind, str]] = {
    FieldRef: (SourceKind.FIELD, "name"),
    ColumnRef: (SourceKind.COLUMN, "column_id"),
    PathRef: (SourceKind.PATH, "segments"),
    LiteralExpression: (SourceKind.LITERAL, "value"),
}


def _inspect_source(source: ColumnSource) -> SourceSpec:
    leaf = _LEAF_SOURCE_KINDS.get(type(source))
    if leaf is not None:
        kind, attribute = leaf
        return SourceSpec(kind, getattr(source, attribute))
    if isinstance(source, BinaryExpression):
        return SourceSpec(
            SourceKind.BINARY,
            source.operator.value,
            (_inspect_source(source.left), _inspect_source(source.right)),
        )
    if isinstance(source, CallableSource):
        return SourceSpec(SourceKind.CALLABLE, _inspect_callable(source.function))
    if isinstance(source, TransformExpression):
        return SourceSpec(
            SourceKind.TRANSFORM,
            _inspect_callable(source.function),
            (_inspect_source(source.expression),),
        )
    if isinstance(source, AggregateExpr):
        return SourceSpec(
            SourceKind.AGGREGATE,
            {
                "function": _inspect_callable(source.function),
                "where": (
                    None if source.where is None else _inspect_source(source.where)
                ),
                "has_default": source.has_default,
                "default": source.default if source.has_default else None,
            },
            tuple(_inspect_source(item) for item in source.expressions),
        )
    message = f"Unsupported column source: {type(source).__name__}"
    raise TypeError(message)


def _inspect_callable(function: RowCallable | TransformCallable) -> CallableSpec:
    return CallableSpec(
        module=getattr(function, "__module__", None),
        qualname=getattr(function, "__qualname__", type(function).__name__),
        identity=_callable_identity(function),
    )


def _inspect_formula(formula: object) -> FormulaSpec:
    if isinstance(formula, FormulaLiteral):
        return FormulaSpec(FormulaKind.LITERAL, formula.value)
    if isinstance(formula, FormulaBinary):
        return FormulaSpec(
            FormulaKind.BINARY,
            formula.operator.value,
            (_inspect_formula(formula.left), _inspect_formula(formula.right)),
        )
    if isinstance(formula, CellReference):
        return FormulaSpec(
            FormulaKind.CELL,
            {
                "column": formula.column_id,
                "table": formula.table_name,
                "sheet": formula.sheet_name,
                "row": formula.row_index,
                "column_absolute": formula.column_absolute,
                "row_absolute": formula.row_absolute,
            },
        )
    if isinstance(formula, RangeReference):
        return FormulaSpec(
            FormulaKind.RANGE,
            {
                "column": formula.column_id,
                "table": formula.table_name,
                "sheet": formula.sheet_name,
                "column_absolute": formula.column_absolute,
                "row_absolute": formula.row_absolute,
            },
        )
    message = f"Unsupported formula: {type(formula).__name__}"
    raise TypeError(message)


def _callable_identity(function: object) -> str:
    explicit = getattr(function, "__caxton_id__", None)
    if isinstance(explicit, str):
        return f"explicit:{explicit}"
    code = getattr(function, "__code__", None)
    if code is None and callable(function):
        code = getattr(function.__call__, "__code__", None)
    closure = getattr(function, "__closure__", None) or ()
    payload = {
        "code": _stable_token(code),
        "closure": tuple(_closure_value(cell) for cell in closure),
        "defaults": _stable_token(getattr(function, "__defaults__", None)),
        "kwdefaults": _stable_token(getattr(function, "__kwdefaults__", None)),
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.blake2b(serialized.encode(), digest_size=16).hexdigest()
    return f"blake2b:{digest}"


def _closure_value(cell: types.CellType) -> object:
    try:
        value = cell.cell_contents
    except ValueError:
        return ["empty-cell"]
    return _stable_token(value)


def _stable_token(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float, str, bytes)):
        return _scalar_token(value)
    if isinstance(value, (enum.Enum, types.CodeType)):
        return _special_token(value)
    if isinstance(value, (Mapping, AbstractSet, Sequence)):
        return _container_token(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return [
            "dataclass",
            _type_name(value),
            [
                [field.name, _stable_token(getattr(value, field.name))]
                for field in dataclasses.fields(value)
            ],
        ]
    return ["object", _type_name(value)]


def _scalar_token(value: object) -> object:
    if isinstance(value, float):
        return ["float", value.hex()]
    if isinstance(value, bytes):
        return ["bytes", value.hex()]
    return value


def _special_token(value: enum.Enum | types.CodeType) -> object:
    if isinstance(value, enum.Enum):
        return ["enum", _type_name(value), value.name]
    return _code_token(value)


def _container_token(
    value: Mapping[object, object] | AbstractSet[object] | Sequence[object],
) -> object:
    if isinstance(value, Mapping):
        items = [
            (_stable_token(key), _stable_token(item)) for key, item in value.items()
        ]
        return ["mapping", sorted(items, key=_serialized_token)]
    if isinstance(value, AbstractSet):
        tokens = (_stable_token(item) for item in value)
        return ["set", sorted(tokens, key=_serialized_token)]
    sequence_items = [_stable_token(item) for item in value]
    return [type(value).__name__, sequence_items]


def _code_token(code: types.CodeType) -> object:
    return [
        "code",
        code.co_argcount,
        code.co_posonlyargcount,
        code.co_kwonlyargcount,
        code.co_flags,
        code.co_code.hex(),
        code.co_names,
        code.co_varnames,
        code.co_freevars,
        code.co_cellvars,
        tuple(_stable_token(item) for item in code.co_consts),
    ]


def _serialized_token(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _type_name(value: object) -> str:
    value_type = type(value)
    return f"{value_type.__module__}.{value_type.__qualname__}"


__all__ = (
    "BlockKind",
    "BlockSpec",
    "CallableSpec",
    "ColumnSpec",
    "ConditionalRuleSpec",
    "MatrixSpec",
    "SemanticTypeSpec",
    "SourceKind",
    "SourceSpec",
    "SpreadsheetSpec",
    "TableSpec",
    "WorksheetSpec",
    "inspect_spec",
)
