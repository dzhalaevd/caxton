from __future__ import annotations

import base64
import dataclasses
import datetime as dt
import decimal
import enum
import json
import math
import uuid
from collections.abc import Mapping, Sequence, Set as AbstractSet
from typing import Any, cast

SNAPSHOT_SCHEMA = "caxton.testing.snapshot/v1"


def canonical_snapshot(value: object) -> str:
    """Serialize a testing value as deterministic, human-readable JSON.

    Unsupported runtime objects raise ``TypeError``; recursive containers raise
    ``ValueError``.

    Returns:
        Canonical JSON ending with one newline.
    """
    payload = {
        "$schema": SNAPSHOT_SCHEMA,
        "value": _normalize(value, active=set()),
    }
    return f"{json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)}\n"


def _normalize(value: object, *, active: set[int]) -> object:
    if value is None or isinstance(value, _SCALAR_TYPES):
        return _normalize_scalar(value, active=active)
    if isinstance(value, _TEMPORAL_TYPES):
        return _normalize_temporal(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _normalize_dataclass(value, active=active)
    if isinstance(value, (Mapping, AbstractSet, Sequence)):
        return _normalize_collection(value, active=active)
    message = f"Unsupported snapshot value: {type(value).__name__}"
    raise TypeError(message)


_SCALAR_TYPES = (bool, int, float, str, bytes, decimal.Decimal, enum.Enum, uuid.UUID)
_TEMPORAL_TYPES = (dt.datetime, dt.date, dt.time, dt.timedelta)


def _normalize_scalar(value: object, *, active: set[int]) -> object:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return _normalize_float(value)
    if isinstance(value, enum.Enum):
        return _normalize(value.value, active=active)
    return _normalize_tagged_scalar(value)


def _normalize_tagged_scalar(value: object) -> object:
    if isinstance(value, bytes):
        encoded = base64.b64encode(value).decode("ascii")
        return {"$bytes": encoded}
    if isinstance(value, decimal.Decimal):
        return {"$decimal": str(value)}
    return {"$uuid": str(value)}


def _normalize_temporal(value: object) -> object:
    if isinstance(value, dt.datetime):
        return {"$datetime": value.isoformat()}
    if isinstance(value, dt.date):
        return {"$date": value.isoformat()}
    if isinstance(value, dt.time):
        return {"$time": value.isoformat()}
    duration = cast("dt.timedelta", value)
    return {"$timedelta_microseconds": _timedelta_microseconds(duration)}


def _normalize_collection(value: object, *, active: set[int]) -> object:
    if isinstance(value, Mapping):
        return _normalize_mapping(value, active=active)
    if isinstance(value, AbstractSet):
        return _normalize_set(value, active=active)
    return _normalize_sequence(cast("Sequence[object]", value), active=active)


def _normalize_float(value: float) -> object:
    if math.isnan(value):
        return {"$float": "nan"}
    if math.isinf(value):
        return {"$float": "infinity" if value > 0 else "-infinity"}
    return value


def _normalize_dataclass(value: object, *, active: set[int]) -> object:
    identity = _enter(value, active)
    try:
        dataclass_value = cast("Any", value)
        result: dict[str, object] = {"$type": type(value).__name__}
        result.update(
            {
                field.name: _normalize(
                    getattr(dataclass_value, field.name),
                    active=active,
                )
                for field in dataclasses.fields(dataclass_value)
            },
        )
        return result
    finally:
        active.remove(identity)


def _normalize_mapping(
    value: Mapping[object, object],
    *,
    active: set[int],
) -> object:
    identity = _enter(value, active)
    try:
        if all(isinstance(key, str) for key in value):
            return {
                str(key): _normalize(item, active=active) for key, item in value.items()
            }
        items = [
            [_normalize(key, active=active), _normalize(item, active=active)]
            for key, item in value.items()
        ]
        return {"$mapping": sorted(items, key=_sort_key)}
    finally:
        active.remove(identity)


def _normalize_set(value: AbstractSet[object], *, active: set[int]) -> object:
    identity = _enter(value, active)
    try:
        items = [_normalize(item, active=active) for item in value]
        return {"$set": sorted(items, key=_sort_key)}
    finally:
        active.remove(identity)


def _normalize_sequence(value: Sequence[object], *, active: set[int]) -> object:
    identity = _enter(value, active)
    try:
        return [_normalize(item, active=active) for item in value]
    finally:
        active.remove(identity)


def _enter(value: object, active: set[int]) -> int:
    identity = id(value)
    if identity in active:
        message = "Snapshot values cannot contain recursive containers"
        raise ValueError(message)
    active.add(identity)
    return identity


def _sort_key(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _timedelta_microseconds(value: dt.timedelta) -> int:
    return (
        value.days * 24 * 60 * 60 * 1_000_000
        + value.seconds * 1_000_000
        + value.microseconds
    )


__all__ = ("SNAPSHOT_SCHEMA", "canonical_snapshot")
