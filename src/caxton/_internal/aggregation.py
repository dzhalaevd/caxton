from __future__ import annotations

import dataclasses
import decimal
import hashlib
from collections.abc import Mapping, Sequence
from typing import Any, TypeAlias, cast

from caxton._internal.semantic import SemanticRowEvaluator
from caxton.core._values import normalize_cell_value
from caxton.core.errors import (
    AggregateEvaluationError,
    CaxtonError,
    GroupingError,
    MatrixConflictError,
)
from caxton.core.formatting import Alignment, DisplayFormat, StyleInput
from caxton.core.models import (
    AggregateExpr,
    Column,
    GroupOrder,
    Matrix,
    SpreadsheetTable,
)
from caxton.core.protocols import DataSource
from caxton.core.types import SemanticType
from caxton.core.values import CellValue


@dataclasses.dataclass(frozen=True, slots=True)
class RelativeMerge:
    """A vertical merge expressed in zero-based table data-row offsets."""

    column_offset: int
    start_row: int
    end_row: int


@dataclasses.dataclass(frozen=True, slots=True)
class PreparedColumn:
    """Renderer-neutral metadata for one prepared tabular column."""

    id: str
    title: str
    semantic_type: SemanticType
    alignment: Alignment | None = None
    width_hint: float | None = None
    display_format: DisplayFormat | None = None
    style_ref: StyleInput | None = None
    auto_width: bool = False
    matrix_key: tuple[CellValue, ...] | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class PreparedTabularData:
    """Buffered output of grouped-table or matrix semantic execution."""

    columns: Sequence[Column | PreparedColumn]
    rows: Sequence[Sequence[CellValue]]
    merges: Sequence[RelativeMerge] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "columns", tuple(self.columns))
        object.__setattr__(self, "rows", tuple(tuple(row) for row in self.rows))
        object.__setattr__(self, "merges", tuple(self.merges))


@dataclasses.dataclass(frozen=True, slots=True)
class _InputRow:
    index: int
    raw: object
    values: Mapping[str, CellValue] | None = None


DimensionToken: TypeAlias = tuple[str, object]
GroupKey: TypeAlias = tuple[CellValue, ...]
TokenKey: TypeAlias = tuple[DimensionToken, ...]
PreparedRows: TypeAlias = tuple[tuple[CellValue, ...], ...]
AggregateRowsResult: TypeAlias = tuple[PreparedRows, tuple[TokenKey, ...]]


@dataclasses.dataclass(slots=True)
class _Bucket:
    key: CellValue
    token: DimensionToken
    rows: list[_InputRow]


@dataclasses.dataclass(frozen=True, slots=True)
class _Scope:
    keys: GroupKey
    tokens: TokenKey
    rows: Sequence[_InputRow]


@dataclasses.dataclass(frozen=True, slots=True)
class _MatrixRecord:
    row_key: GroupKey
    row_token: TokenKey
    column_key: GroupKey
    column_token: TokenKey
    row: _InputRow


def table_needs_preparation(table: SpreadsheetTable) -> bool:
    """Return whether a table needs grouped/aggregate buffering."""
    return any(
        column.grouping is not None or isinstance(column.source, AggregateExpr)
        for column in table.columns
    )


def prepare_table(
    table: SpreadsheetTable,
    evaluator: SemanticRowEvaluator,
    *,
    path: str = "table",
) -> PreparedTabularData:
    """Execute grouping and aggregation with exactly one source pass.

    Returns:
        Buffered renderer-neutral rows and relative merge ranges.
    """
    aggregate_columns = tuple(
        column for column in table.columns if isinstance(column.source, AggregateExpr)
    )
    group_columns = tuple(
        column for column in table.columns if column.grouping is not None
    )
    base_columns = tuple(
        column
        for column in table.columns
        if column.excel_formula is None and not isinstance(column.source, AggregateExpr)
    )
    inputs = _read_rows(table.data.source, base_columns, evaluator)
    scopes = _group_scopes(inputs, group_columns, path=path)
    if aggregate_columns:
        output, key_tokens = _aggregate_rows(
            table,
            scopes,
            group_columns,
            base_columns,
            evaluator,
            path=path,
        )
    else:
        ordered = [row for scope in scopes for row in scope.rows]
        output = tuple(
            tuple(
                None
                if column.excel_formula is not None
                else _row_values(row)[column.id]
                for column in table.columns
            )
            for row in ordered
        )
        key_tokens = tuple(
            tuple(
                _dimension_token(_row_values(row)[column.id])
                for column in group_columns
            )
            for row in ordered
        )
    return PreparedTabularData(
        columns=table.columns,
        rows=output,
        merges=_resolve_merges(key_tokens, group_columns, table.columns),
    )


def prepare_matrix(
    matrix: Matrix,
    evaluator: SemanticRowEvaluator,
    *,
    path: str = "matrix",
) -> PreparedTabularData:
    """Pivot one matrix source with strict, first-seen dimension ordering.

    Returns:
        Dynamic columns and buffered matrix rows.
    """
    records = _matrix_records(matrix, evaluator)
    row_keys = _unique_matrix_keys(records, row=True)
    column_keys = _unique_matrix_keys(records, row=False)
    scopes: dict[tuple[TokenKey, TokenKey], list[_InputRow]] = {}
    for record in records:
        scopes.setdefault((record.row_token, record.column_token), []).append(
            record.row
        )

    used_ids = {column.id for column in matrix.row_dimensions}
    row_columns = tuple(_prepared_column(column) for column in matrix.row_dimensions)
    headers = _matrix_headers(tuple(key for key, _token in column_keys))
    value_columns = tuple(
        _matrix_value_column(matrix.value, key, token, title, used_ids)
        for (key, token), title in zip(column_keys, headers, strict=True)
    )
    output = tuple(
        (
            *row_key,
            *(
                _matrix_cell(
                    matrix,
                    scopes.get((row_token, column_token), ()),
                    column_key=column_key,
                    row_key=row_key,
                    evaluator=evaluator,
                    path=path,
                )
                for column_key, column_token in column_keys
            ),
        )
        for row_key, row_token in row_keys
    )
    return PreparedTabularData(columns=(*row_columns, *value_columns), rows=output)


def _read_rows(
    source: DataSource[Any],
    columns: Sequence[Column],
    evaluator: SemanticRowEvaluator,
) -> tuple[_InputRow, ...]:
    rows: list[_InputRow] = []
    for index, raw in evaluator.iter_source_rows(source):
        semantic = evaluator.evaluate_row(source, raw, columns, row_index=index)
        rows.append(_InputRow(index=index, raw=raw, values=semantic.values))
    return tuple(rows)


def _group_scopes(
    rows: Sequence[_InputRow],
    columns: Sequence[Column],
    *,
    path: str,
) -> tuple[_Scope, ...]:
    if not columns:
        return (_Scope((), (), rows),)
    scopes: list[_Scope] = []

    def visit(
        current: Sequence[_InputRow],
        level: int,
        keys: GroupKey,
        tokens: TokenKey,
    ) -> None:
        column = columns[level]
        for bucket in _ordered_buckets(_buckets(current, column), column, path=path):
            next_keys = (*keys, bucket.key)
            next_tokens = (*tokens, bucket.token)
            if level + 1 == len(columns):
                scopes.append(_Scope(next_keys, next_tokens, tuple(bucket.rows)))
            else:
                visit(bucket.rows, level + 1, next_keys, next_tokens)

    visit(rows, 0, (), ())
    return tuple(scopes)


def _buckets(rows: Sequence[_InputRow], column: Column) -> list[_Bucket]:
    buckets: dict[DimensionToken, _Bucket] = {}
    for row in rows:
        key = _row_values(row)[column.id]
        token = _dimension_token(key)
        bucket = buckets.get(token)
        if bucket is None:
            bucket = _Bucket(key=key, token=token, rows=[])
            buckets[token] = bucket
        bucket.rows.append(row)
    return list(buckets.values())


def _ordered_buckets(
    buckets: list[_Bucket],
    column: Column,
    *,
    path: str,
) -> list[_Bucket]:
    grouping = column.grouping
    if grouping is None or grouping.order is GroupOrder.FIRST_SEEN:
        return buckets
    non_null = [item for item in buckets if item.key is not None]
    nulls = [item for item in buckets if item.key is None]
    try:
        ordered = sorted(
            non_null,
            key=lambda item: cast("Any", item.key),
            reverse=grouping.order is GroupOrder.DESCENDING,
        )
    except TypeError as error:
        message = f"Group column {column.id!r} contains incomparable values"
        raise GroupingError(
            message,
            path=f'{path}.column["{column.id}"].grouping',
            context={
                "column": column.id,
                "order": grouping.order.value,
                "value_types": sorted({type(item.key).__name__ for item in buckets}),
            },
        ) from error
    return [*ordered, *nulls]


def _aggregate_rows(  # noqa: WPS211
    table: SpreadsheetTable,
    scopes: Sequence[_Scope],
    group_columns: Sequence[Column],
    base_columns: Sequence[Column],
    evaluator: SemanticRowEvaluator,
    *,
    path: str,
) -> AggregateRowsResult:
    if group_columns and not scopes:
        return (), ()
    output: list[tuple[CellValue, ...]] = []
    keys: list[TokenKey] = []
    for scope in scopes:
        group_values = dict(
            zip((item.id for item in group_columns), scope.keys, strict=True),
        )
        values: list[CellValue] = []
        for column in table.columns:
            if isinstance(column.source, AggregateExpr):
                values.append(
                    _execute_aggregate(
                        column.source,
                        scope.rows,
                        source=table.data.source,
                        columns=base_columns,
                        evaluator=evaluator,
                        path=f'{path}.column["{column.id}"].source',
                    ),
                )
            elif column.excel_formula is not None:
                values.append(None)
            else:
                values.append(group_values[column.id])
        output.append(tuple(values))
        keys.append(scope.tokens)
    return tuple(output), tuple(keys)


def _execute_aggregate(  # noqa: WPS211
    expression: AggregateExpr,
    rows: Sequence[_InputRow],
    *,
    source: DataSource[Any],
    columns: Sequence[Column],
    evaluator: SemanticRowEvaluator,
    path: str,
) -> CellValue:
    included = tuple(
        row
        for row in rows
        if expression.where is None
        or bool(
            evaluator.evaluate_expression(
                source,
                row.raw,
                columns,
                expression.where,
                row_index=row.index,
                values=row.values,
            ),
        )
    )
    if not included and expression.has_default:
        return normalize_cell_value(expression.default)
    inputs = tuple(
        tuple(
            evaluator.evaluate_expression(
                source,
                row.raw,
                columns,
                item,
                row_index=row.index,
                values=row.values,
            )
            for row in included
        )
        for item in expression.expressions
    )
    function_name = getattr(
        expression.function, "__name__", type(expression.function).__name__
    )
    try:
        result = expression.function(*inputs)
    except CaxtonError:
        raise
    except Exception as error:
        raise _aggregate_error(
            error,
            function_name,
            len(included),
            path,
            phase="callable",
        ) from error
    try:
        return normalize_cell_value(result)
    except Exception as error:
        raise _aggregate_error(
            error,
            function_name,
            len(included),
            path,
            phase="result_normalization",
        ) from error


def _aggregate_error(
    error: Exception,
    function_name: str,
    scope_size: int,
    path: str,
    *,
    phase: str,
) -> AggregateEvaluationError:
    message = (
        f"Aggregate {function_name!r} failed"
        if phase == "callable"
        else f"Aggregate {function_name!r} returned an unsupported result"
    )
    return AggregateEvaluationError(
        message,
        path=path,
        context={
            "exception_type": type(error).__name__,
            "function": function_name,
            "phase": phase,
            "scope_size": scope_size,
        },
    )


def _resolve_merges(
    keys: Sequence[TokenKey],
    group_columns: Sequence[Column],
    all_columns: Sequence[Column],
) -> tuple[RelativeMerge, ...]:
    merges: list[RelativeMerge] = []
    offsets = {column.id: index for index, column in enumerate(all_columns)}
    for level, column in enumerate(group_columns):
        grouping = column.grouping
        if grouping is None or not grouping.merge:
            continue
        start = 0
        while start < len(keys):
            prefix = keys[start][: level + 1]
            end = start
            while end + 1 < len(keys) and keys[end + 1][: level + 1] == prefix:
                end += 1
            if end > start:
                merges.append(RelativeMerge(offsets[column.id], start, end))
            start = end + 1
    return tuple(merges)


def _matrix_records(
    matrix: Matrix,
    evaluator: SemanticRowEvaluator,
) -> tuple[_MatrixRecord, ...]:
    records: list[_MatrixRecord] = []
    value_is_aggregate = isinstance(matrix.value.source, AggregateExpr)
    row_columns = (*matrix.row_dimensions, *matrix.column_dimensions)
    evaluated_columns = (
        row_columns if value_is_aggregate else (*row_columns, matrix.value)
    )
    for index, raw in evaluator.iter_source_rows(matrix.source):
        semantic = evaluator.evaluate_row(
            matrix.source,
            raw,
            evaluated_columns,
            row_index=index,
        )
        row_key = tuple(semantic.values[item.id] for item in matrix.row_dimensions)
        column_key = tuple(
            semantic.values[item.id] for item in matrix.column_dimensions
        )
        records.append(
            _MatrixRecord(
                row_key=row_key,
                row_token=_key_token(row_key),
                column_key=column_key,
                column_token=_key_token(column_key),
                row=_InputRow(index=index, raw=raw, values=semantic.values),
            ),
        )
    return tuple(records)


def _matrix_cell(  # noqa: WPS211
    matrix: Matrix,
    scope: Sequence[_InputRow],
    *,
    column_key: GroupKey,
    row_key: GroupKey,
    evaluator: SemanticRowEvaluator,
    path: str,
) -> CellValue:
    if not scope:
        source = matrix.value.source
        if isinstance(source, AggregateExpr) and source.has_default:
            return normalize_cell_value(source.default)
        return None
    if isinstance(matrix.value.source, AggregateExpr):
        return _execute_aggregate(
            matrix.value.source,
            scope,
            source=matrix.source,
            columns=(*matrix.row_dimensions, *matrix.column_dimensions),
            evaluator=evaluator,
            path=f'{path}.value["{matrix.value.id}"].source',
        )
    if len(scope) > 1:
        message = "Matrix cell contains multiple unaggregated values"
        raise MatrixConflictError(
            message,
            path=f'{path}.value["{matrix.value.id}"]',
            context={
                "column_key": column_key,
                "row_key": row_key,
                "value_count": len(scope),
            },
        )
    return _row_values(scope[0])[matrix.value.id]


def _unique_matrix_keys(
    records: Sequence[_MatrixRecord],
    *,
    row: bool,
) -> tuple[tuple[GroupKey, TokenKey], ...]:
    output: dict[TokenKey, GroupKey] = {}
    for record in records:
        key = record.row_key if row else record.column_key
        token = record.row_token if row else record.column_token
        output.setdefault(token, key)
    return tuple((key, token) for token, key in output.items())


def _dimension_token(value: CellValue) -> DimensionToken:
    type_name = f"{type(value).__module__}.{type(value).__qualname__}"
    if isinstance(value, decimal.Decimal):
        return type_name, value.as_tuple()
    if isinstance(value, float):
        return type_name, value.hex()
    return type_name, value


def _key_token(key: GroupKey) -> TokenKey:
    return tuple(_dimension_token(value) for value in key)


def _prepared_column(column: Column) -> PreparedColumn:
    return PreparedColumn(
        id=column.id,
        title=column.display_title,
        semantic_type=column.semantic_type,
        alignment=column.alignment,
        width_hint=column.width_hint,
        display_format=column.display_format,
        style_ref=column.style_ref,
        auto_width=column.auto_width,
    )


def _matrix_value_column(
    value: Column,
    key: GroupKey,
    token: TokenKey,
    title: str,
    used_ids: set[str],
) -> PreparedColumn:
    digest = hashlib.sha256(repr(token).encode("utf-8")).hexdigest()[:12]
    base = f"_matrix_{value.id}_{digest}"
    column_id = base
    suffix = 2
    while column_id in used_ids:
        column_id = f"{base}_{suffix}"
        suffix += 1
    used_ids.add(column_id)
    return dataclasses.replace(
        _prepared_column(value),
        id=column_id,
        title=title,
        matrix_key=key,
    )


def _matrix_headers(keys: Sequence[GroupKey]) -> tuple[str, ...]:
    base = tuple(_matrix_key_title(key) for key in keys)
    totals: dict[str, int] = {}
    for title in base:
        totals[title] = totals.get(title, 0) + 1
    counts: dict[str, int] = {}
    output: list[str] = []
    for title, key in zip(base, keys, strict=True):
        counts[title] = counts.get(title, 0) + 1
        if totals[title] == 1:
            output.append(title)
            continue
        type_names = "/".join(type(value).__name__ for value in key)
        output.append(f"{title} [{type_names}] #{counts[title]}")
    return tuple(output)


def _matrix_key_title(key: GroupKey) -> str:
    return " / ".join("(blank)" if value is None else str(value) for value in key)


def _row_values(row: _InputRow) -> Mapping[str, CellValue]:
    if row.values is None:
        message = "Prepared row values are unavailable"
        raise RuntimeError(message)
    return row.values


__all__ = (
    "PreparedColumn",
    "PreparedTabularData",
    "RelativeMerge",
    "prepare_matrix",
    "prepare_table",
    "table_needs_preparation",
)
