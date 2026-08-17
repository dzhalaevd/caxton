from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from typing import TypeAlias, cast

from caxton._internal.aggregation.execution import (
    InputRow,
    execute_aggregate,
    read_rows,
)
from caxton._internal.aggregation.keys import (
    GroupKey,
    TokenKey,
    dimension_token,
    order_group_values,
)
from caxton._internal.aggregation.models import (
    PreparedColumn,
    PreparedTabularData,
    RelativeMerge,
)
from caxton._internal.semantic import SemanticRowEvaluator
from caxton.core.errors import InvalidOperationError
from caxton.core.models import AggregateExpr, Column, Expression, SpreadsheetTable
from caxton.core.values import CellValue

PreparedRows: TypeAlias = tuple[tuple[CellValue, ...], ...]
AggregateRowsResult: TypeAlias = tuple[PreparedRows, tuple[TokenKey, ...]]


@dataclasses.dataclass(slots=True)
class _Bucket:
    key: CellValue
    token: tuple[str, object]
    rows: list[InputRow]


@dataclasses.dataclass(frozen=True, slots=True)
class _Scope:
    keys: GroupKey
    tokens: TokenKey
    rows: Sequence[InputRow]


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
    inputs = read_rows(
        table.data.source,
        base_columns,
        evaluator,
        aggregates=tuple(
            cast("AggregateExpr", column.source) for column in aggregate_columns
        ),
        path=path,
    )
    scopes = _group_scopes(inputs, group_columns, path=path)
    if aggregate_columns:
        output, key_tokens = _aggregate_rows(
            table,
            scopes,
            group_columns,
            path=path,
        )
    else:
        ordered = [row for scope in scopes for row in scope.rows]
        output = tuple(
            tuple(
                None if column.excel_formula is not None else row.values[column.id]
                for column in table.columns
            )
            for row in ordered
        )
        key_tokens = tuple(
            tuple(dimension_token(row.values[column.id]) for column in group_columns)
            for row in ordered
        )
    return PreparedTabularData(
        columns=tuple(PreparedColumn.from_column(column) for column in table.columns),
        rows=output,
        row_count=len(output),
        merges=resolve_group_merges(key_tokens, group_columns, table.columns),
    )


def _group_scopes(
    rows: Sequence[InputRow],
    columns: Sequence[Column],
    *,
    path: str,
) -> tuple[_Scope, ...]:
    if not columns:
        return (_Scope((), (), rows),)
    scopes: list[_Scope] = []

    def visit(
        current: Sequence[InputRow],
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


def _buckets(rows: Sequence[InputRow], column: Column) -> list[_Bucket]:
    buckets: dict[tuple[str, object], _Bucket] = {}
    for row in rows:
        key = row.values[column.id]
        token = dimension_token(key)
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
    return order_group_values(buckets, column, lambda item: item.key, path=path)


def _aggregate_rows(  # noqa: WPS211
    table: SpreadsheetTable,
    scopes: Sequence[_Scope],
    group_columns: Sequence[Column],
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
        filter_cache: dict[Expression | None, tuple[InputRow, ...]] = {}
        for column in table.columns:
            if isinstance(column.source, AggregateExpr):
                values.append(
                    execute_aggregate(
                        column.source,
                        scope.rows,
                        path=f'{path}.column["{column.id}"].source',
                        filter_cache=filter_cache,
                    ),
                )
            elif column.excel_formula is not None:
                values.append(None)
            else:
                values.append(_group_output_value(column, group_values, path=path))
        output.append(tuple(values))
        keys.append(scope.tokens)
    return tuple(output), tuple(keys)


def _group_output_value(
    column: Column,
    group_values: dict[str, CellValue],
    *,
    path: str,
) -> CellValue:
    try:
        return group_values[column.id]
    except KeyError as error:
        message = "Aggregate output requires every plain column to group"
        raise InvalidOperationError(
            message,
            path=f'{path}.column["{column.id}"]',
            context={"column": column.id},
        ) from error


def resolve_group_merges(
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


__all__ = ("prepare_table", "resolve_group_merges")
