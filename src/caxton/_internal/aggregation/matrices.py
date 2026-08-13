from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Sequence

from caxton._internal.aggregation.execution import (
    InputRow,
    execute_aggregate,
)
from caxton._internal.aggregation.keys import GroupKey, TokenKey, key_token
from caxton._internal.aggregation.models import PreparedColumn, PreparedTabularData
from caxton._internal.semantic import SemanticRowEvaluator
from caxton.core._values import normalize_cell_value
from caxton.core.errors import MatrixConflictError
from caxton.core.models import AggregateExpr, Column, Matrix
from caxton.core.values import CellValue


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
    records = _matrix_records(matrix, evaluator)
    row_keys = _unique_matrix_keys(records, row=True)
    column_keys = _unique_matrix_keys(records, row=False)
    scopes: dict[tuple[TokenKey, TokenKey], list[InputRow]] = {}
    for record in records:
        scopes.setdefault((record.row_token, record.column_token), []).append(
            record.row,
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
                row_token=key_token(row_key),
                column_key=column_key,
                column_token=key_token(column_key),
                row=InputRow(index=index, raw=raw, values=semantic.values),
            ),
        )
    return tuple(records)


def _matrix_cell(  # noqa: WPS211
    matrix: Matrix,
    scope: Sequence[InputRow],
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
        return execute_aggregate(
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
    return scope[0].values[matrix.value.id]


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
        _prepared_column(value),
        id=column_id,
        title=title,
        matrix_key=key,
    )


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


__all__ = ("prepare_matrix",)
