from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Iterator, Sequence
from typing import TypeAlias

from caxton._internal.aggregation.execution import (
    InputRow,
    evaluate_input_row,
    execute_aggregate,
    warn_if_large_buffer,
)
from caxton._internal.aggregation.keys import (
    GroupKey,
    TokenKey,
    key_token,
    order_group_values,
)
from caxton._internal.aggregation.models import PreparedColumn, PreparedTabularData
from caxton._internal.aggregation.tables import resolve_group_merges
from caxton._internal.semantic import SemanticRowEvaluator
from caxton.core._values import normalize_cell_value
from caxton.core.errors import MatrixConflictError
from caxton.core.models import AggregateExpr, Column, Matrix
from caxton.core.values import CellValue

MatrixKeyItem: TypeAlias = tuple[GroupKey, TokenKey]
MatrixKeyBucket: TypeAlias = list[MatrixKeyItem]


@dataclasses.dataclass(frozen=True, slots=True)
class _MatrixRecord:
    row_key: GroupKey
    row_token: TokenKey
    column_key: GroupKey
    column_token: TokenKey
    row: InputRow


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
    records = _matrix_records(matrix, evaluator, path=path)
    row_keys = _unique_matrix_keys(
        records,
        row=True,
        columns=matrix.row_dimensions,
        path=path,
    )
    column_keys = _unique_matrix_keys(
        records,
        row=False,
        columns=matrix.column_dimensions,
        path=path,
    )
    scopes: dict[tuple[TokenKey, TokenKey], list[InputRow]] = {}
    for record in records:
        scopes.setdefault((record.row_token, record.column_token), []).append(
            record.row,
        )

    used_ids = {column.id for column in matrix.row_dimensions}
    row_columns = tuple(
        PreparedColumn.from_column(column) for column in matrix.row_dimensions
    )
    headers = _matrix_headers(tuple(key for key, _token in column_keys))
    value_columns = tuple(
        _matrix_value_column(matrix.value, key, token, title, used_ids)
        for (key, token), title in zip(column_keys, headers, strict=True)
    )
    output = _matrix_rows(
        matrix,
        row_keys,
        column_keys,
        scopes,
        path=path,
    )
    return PreparedTabularData(
        columns=(*row_columns, *value_columns),
        rows=output,
        row_count=len(row_keys),
        merges=resolve_group_merges(
            tuple(token for _key, token in row_keys),
            matrix.row_dimensions,
            matrix.row_dimensions,
        ),
    )


def _matrix_rows(  # noqa: WPS211
    matrix: Matrix,
    row_keys: Sequence[MatrixKeyItem],
    column_keys: Sequence[MatrixKeyItem],
    scopes: dict[tuple[TokenKey, TokenKey], list[InputRow]],
    *,
    path: str,
) -> Iterator[tuple[CellValue, ...]]:
    empty = _empty_matrix_value(matrix)
    for row_key, row_token in row_keys:
        values: list[CellValue] = []
        for column_key, column_token in column_keys:
            scope = scopes.get((row_token, column_token))
            values.append(
                empty
                if scope is None
                else _matrix_cell(
                    matrix,
                    scope,
                    column_key=column_key,
                    row_key=row_key,
                    path=path,
                ),
            )
        yield (*row_key, *values)


def _empty_matrix_value(matrix: Matrix) -> CellValue:
    source = matrix.value.source
    if isinstance(source, AggregateExpr) and source.has_default:
        return normalize_cell_value(source.default)
    return None


def _matrix_records(
    matrix: Matrix,
    evaluator: SemanticRowEvaluator,
    *,
    path: str,
) -> tuple[_MatrixRecord, ...]:
    records: list[_MatrixRecord] = []
    value_is_aggregate = isinstance(matrix.value.source, AggregateExpr)
    row_columns = (*matrix.row_dimensions, *matrix.column_dimensions)
    evaluated_columns = (
        row_columns if value_is_aggregate else (*row_columns, matrix.value)
    )
    column_catalog = {column.id: column for column in evaluated_columns}
    aggregates = (
        (matrix.value.source,) if isinstance(matrix.value.source, AggregateExpr) else ()
    )
    for index, raw in evaluator.iter_source_rows(matrix.source):
        input_row = evaluate_input_row(
            matrix.source,
            raw,
            index,
            evaluated_columns,
            aggregates,
            evaluator,
            column_catalog=column_catalog,
        )
        row_key = tuple(input_row.values[item.id] for item in matrix.row_dimensions)
        column_key = tuple(
            input_row.values[item.id] for item in matrix.column_dimensions
        )
        records.append(
            _MatrixRecord(
                row_key=row_key,
                row_token=key_token(row_key),
                column_key=column_key,
                column_token=key_token(column_key),
                row=input_row,
            ),
        )
    output = tuple(records)
    warn_if_large_buffer(len(output), path=path, reason="matrix preparation")
    return output


def _matrix_cell(  # noqa: WPS211
    matrix: Matrix,
    scope: Sequence[InputRow],
    *,
    column_key: GroupKey,
    row_key: GroupKey,
    path: str,
) -> CellValue:
    if isinstance(matrix.value.source, AggregateExpr):
        return execute_aggregate(
            matrix.value.source,
            scope,
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
    return scope[0].values[matrix.value.id]


def _unique_matrix_keys(
    records: Sequence[_MatrixRecord],
    *,
    row: bool,
    columns: Sequence[Column],
    path: str,
) -> tuple[MatrixKeyItem, ...]:
    output: dict[TokenKey, GroupKey] = {}
    for record in records:
        key = record.row_key if row else record.column_key
        token = record.row_token if row else record.column_token
        output.setdefault(token, key)
    keys = tuple((key, token) for token, key in output.items())
    return _order_matrix_keys(keys, columns, path=path)


def _order_matrix_keys(
    keys: Sequence[MatrixKeyItem],
    columns: Sequence[Column],
    *,
    path: str,
) -> tuple[MatrixKeyItem, ...]:
    output: list[MatrixKeyItem] = []

    def visit(current: Sequence[MatrixKeyItem], level: int) -> None:
        buckets: dict[object, MatrixKeyBucket] = {}
        for item in current:
            buckets.setdefault(item[1][level], []).append(item)
        ordered = order_group_values(
            tuple(buckets.values()),
            columns[level],
            lambda bucket: bucket[0][0][level],
            path=path,
        )
        for bucket in ordered:
            if level + 1 == len(columns):
                output.extend(bucket)
                continue
            visit(bucket, level + 1)

    if keys:
        visit(keys, 0)
    return tuple(output)


def _matrix_value_column(
    value: Column,
    key: GroupKey,
    token: TokenKey,
    title: str,
    used_ids: set[str],
) -> PreparedColumn:
    digest = hashlib.sha256(repr(token).encode()).hexdigest()[:12]
    base = f"_matrix_{value.id}_{digest}"
    column_id = base
    suffix = 2
    while column_id in used_ids:
        column_id = f"{base}_{suffix}"
        suffix += 1
    used_ids.add(column_id)
    return dataclasses.replace(
        PreparedColumn.from_column(value),
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
    used: set[str] = set()
    for title, key in zip(base, keys, strict=True):
        counts[title] = counts.get(title, 0) + 1
        candidate = title
        if totals[title] > 1:
            type_names = "/".join(type(value).__name__ for value in key)
            candidate = f"{title} [{type_names}] #{counts[title]}"
        suffix = 2
        unique = candidate
        while unique in used:
            unique = f"{candidate} #{suffix}"
            suffix += 1
        used.add(unique)
        output.append(unique)
    return tuple(output)


def _matrix_key_title(key: GroupKey) -> str:
    return " / ".join(_matrix_dimension_title(value) for value in key)


def _matrix_dimension_title(value: CellValue) -> str:
    if value is None:
        return "(blank)"
    rendered = str(value)
    return rendered if rendered.strip() else "(empty)"


__all__ = ("prepare_matrix",)
