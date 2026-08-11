from __future__ import annotations

import dataclasses
import datetime as dt
import decimal
import enum
import uuid
from collections.abc import Mapping, Sequence, Set as AbstractSet
from types import MappingProxyType
from typing import Any, cast

from formata.core.values import CellValue

_IMMUTABLE_LEAVES = (
    bool,
    bytes,
    complex,
    dt.date,
    dt.datetime,
    dt.time,
    dt.timedelta,
    decimal.Decimal,
    enum.Enum,
    float,
    int,
    str,
    uuid.UUID,
)
_CELL_VALUES = (
    bool,
    bytes,
    dt.date,
    dt.datetime,
    dt.time,
    dt.timedelta,
    decimal.Decimal,
    float,
    int,
    str,
)


def freeze_value(value: object, *, label: str = "Value") -> object:
    """Return an immutable snapshot from the supported value vocabulary.

    Returns:
        A recursively immutable value.

    """
    return _freeze_value(value, label=label, active=set())


def freeze_mapping(
    value: Mapping[str, object],
    *,
    label: str = "Mapping",
) -> Mapping[str, object]:
    """Return an immutable snapshot of a string-keyed mapping.

    Returns:
        A recursively immutable mapping.

    Raises:
        TypeError: If the frozen value is not a mapping.
    """
    frozen = freeze_value(value, label=label)
    if not isinstance(frozen, Mapping):
        message = f"{label} must be a mapping"
        raise TypeError(message)
    return frozen


def normalize_cell_value(value: object) -> CellValue:
    """Validate and snapshot one renderer-safe scalar cell value.

    Returns:
        A renderer-safe immutable scalar.

    Raises:
        TypeError: If a container or unsupported object is supplied.
    """
    if value is None or isinstance(value, _CELL_VALUES):
        return value
    message = f"Unsupported cell value: {type(value).__name__}"
    raise TypeError(message)


def _freeze_value(
    value: object,
    *,
    label: str,
    active: set[int],
) -> object:
    if value is None or isinstance(value, _IMMUTABLE_LEAVES):
        return value
    if isinstance(value, Mapping):
        return _freeze_mapping(value, label=label, active=active)
    if isinstance(value, AbstractSet) and not isinstance(value, (str, bytes)):
        return _freeze_set(value, label=label, active=active)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return _freeze_sequence(value, label=label, active=active)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _freeze_dataclass(value, label=label, active=active)
    message = f"{label} contains unsupported value {type(value).__name__}"
    raise TypeError(message)


def _freeze_mapping(
    value: Mapping[object, object],
    *,
    label: str,
    active: set[int],
) -> Mapping[object, object]:
    identity = _enter(value, active)
    try:
        frozen: dict[object, object] = {}
        for key, item in value.items():
            frozen_key = _freeze_value(key, label=f"{label} key", active=active)
            try:
                hash(frozen_key)
            except TypeError as error:
                message = f"{label} contains an unhashable key"
                raise TypeError(message) from error
            frozen[frozen_key] = _freeze_value(item, label=label, active=active)
        return MappingProxyType(frozen)
    finally:
        active.remove(identity)


def _freeze_sequence(
    value: Sequence[object],
    *,
    label: str,
    active: set[int],
) -> tuple[object, ...]:
    identity = _enter(value, active)
    try:
        return tuple(_freeze_value(item, label=label, active=active) for item in value)
    finally:
        active.remove(identity)


def _freeze_set(
    value: AbstractSet[object],
    *,
    label: str,
    active: set[int],
) -> frozenset[object]:
    identity = _enter(value, active)
    try:
        return frozenset(
            _freeze_value(item, label=label, active=active) for item in value
        )
    finally:
        active.remove(identity)


def _freeze_dataclass(
    value: object,
    *,
    label: str,
    active: set[int],
) -> object:
    dataclass_type = cast("Any", type(value))
    parameters = dataclass_type.__dataclass_params__
    if not parameters.frozen:
        message = f"{label} contains mutable dataclass {type(value).__name__}"
        raise TypeError(message)
    identity = _enter(value, active)
    try:
        dataclass_value = cast("Any", value)
        changes = {
            field.name: _freeze_value(
                getattr(dataclass_value, field.name),
                label=label,
                active=active,
            )
            for field in dataclasses.fields(dataclass_value)
            if field.init
        }
        return dataclasses.replace(dataclass_value, **changes)
    finally:
        active.remove(identity)


def _enter(value: object, active: set[int]) -> int:
    identity = id(value)
    if identity in active:
        message = "Immutable values cannot contain recursive containers"
        raise ValueError(message)
    active.add(identity)
    return identity


__all__ = ("freeze_mapping", "freeze_value", "normalize_cell_value")
