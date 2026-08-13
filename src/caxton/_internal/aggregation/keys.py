from __future__ import annotations

import decimal
from typing import TypeAlias

from caxton.core.values import CellValue

DimensionToken: TypeAlias = tuple[str, object]
GroupKey: TypeAlias = tuple[CellValue, ...]
TokenKey: TypeAlias = tuple[DimensionToken, ...]


def dimension_token(value: CellValue) -> DimensionToken:
    """Return the stable, type-sensitive identity of one dimension value."""
    type_name = f"{type(value).__module__}.{type(value).__qualname__}"
    if isinstance(value, decimal.Decimal):
        return type_name, value.as_tuple()
    if isinstance(value, float):
        if not value:
            return type_name, value.hex().lstrip("-")
        return type_name, value.hex()
    return type_name, value


def key_token(key: GroupKey) -> TokenKey:
    """Return the strict identity of one compound dimension key."""
    return tuple(dimension_token(value) for value in key)


__all__ = ("GroupKey", "TokenKey", "dimension_token", "key_token")
