from __future__ import annotations

import decimal
from collections.abc import Callable, Sequence
from typing import Any, TypeAlias, TypeVar, cast

from caxton.core.errors import GroupingError
from caxton.core.models import Column, GroupOrder
from caxton.core.values import CellValue

DimensionToken: TypeAlias = tuple[str, object]
GroupKey: TypeAlias = tuple[CellValue, ...]
TokenKey: TypeAlias = tuple[DimensionToken, ...]
_Item = TypeVar("_Item")


def dimension_token(value: object) -> DimensionToken:
    """Return the stable, type-sensitive identity of one dimension value."""
    type_name = f"{type(value).__module__}.{type(value).__qualname__}"
    if isinstance(value, decimal.Decimal):
        return type_name, value.as_tuple()
    if isinstance(value, float):
        if not value:
            return type_name, value.hex().lstrip("-")
        return type_name, value.hex()
    return type_name, value


def order_group_values(
    items: Sequence[_Item],
    column: Column,
    value: Callable[[_Item], CellValue],
    *,
    path: str,
) -> list[_Item]:
    """Order dimension items with grouping's nulls-last semantics.

    Returns:
        A new list in the declared group order.

    Raises:
        GroupingError: If sorted values cannot be compared.
    """
    grouping = column.grouping
    if grouping is None or grouping.order is GroupOrder.FIRST_SEEN:
        return list(items)
    non_null = [item for item in items if value(item) is not None]
    nulls = [item for item in items if value(item) is None]
    try:
        ordered = sorted(
            non_null,
            key=lambda item: cast("Any", value(item)),
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
                "value_types": sorted({type(value(item)).__name__ for item in items}),
            },
        ) from error
    return [*ordered, *nulls]


def key_token(key: GroupKey) -> TokenKey:
    """Return the strict identity of one compound dimension key."""
    return tuple(dimension_token(value) for value in key)


__all__ = (
    "GroupKey",
    "TokenKey",
    "dimension_token",
    "key_token",
    "order_group_values",
)
