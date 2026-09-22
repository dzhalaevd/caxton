from __future__ import annotations

import dataclasses
import inspect
from collections import deque
from collections.abc import Iterable, Iterator, Mapping, Sized
from typing import Any, Generic, NoReturn, TypeVar, overload

from caxton.core.accessors import DefaultRowAccessor
from caxton.core.errors import (
    CaxtonTypeError,
    DataSourceConsumedError,
    UnsupportedDataSourceError,
)
from caxton.core.protocols import DataSource, Repeatability, RowAccessor

RowT = TypeVar("RowT")
MappingRowT = TypeVar("MappingRowT", bound=Mapping[str, object])

_KNOWN_CONTAINERS: tuple[type[object], ...] = (
    list,
    tuple,
    range,
    set,
    frozenset,
    deque,
)


@dataclasses.dataclass(slots=True)
class IterableDataSource(Generic[RowT]):
    """Internal lazy adapter for ordinary Python row collections."""

    _rows: Iterable[RowT]
    _accessor: RowAccessor[RowT]
    _repeatability: Repeatability
    _row_count: int | None = None
    _consumed: bool = False

    @property
    def repeatability(self) -> Repeatability:
        return self._repeatability

    @property
    def row_count(self) -> int | None:
        return self._row_count

    def iter_rows(self) -> Iterator[RowT]:
        if self._repeatability is Repeatability.ONE_SHOT:
            if self._consumed:
                message = "Data source has already been consumed"
                raise DataSourceConsumedError(message)
            self._consumed = True
        return iter(self._rows)

    def get_value(self, row: RowT, field: str) -> object:
        return self._accessor(row, field)


@overload
def coerce_data_source(
    data: DataSource[RowT], *, accessor: None = None
) -> DataSource[RowT]: ...


@overload
def coerce_data_source(
    data: DataSource[RowT], *, accessor: RowAccessor[Any]
) -> NoReturn: ...


@overload
def coerce_data_source(
    data: MappingRowT, *, accessor: RowAccessor[MappingRowT] | None = None
) -> DataSource[MappingRowT]: ...


@overload
def coerce_data_source(
    data: Iterable[RowT], *, accessor: RowAccessor[RowT] | None = None
) -> DataSource[RowT]: ...


@overload
def coerce_data_source(
    data: RowT, *, accessor: RowAccessor[RowT] | None = None
) -> DataSource[RowT]: ...


def coerce_data_source(  # noqa: C901, WPS212
    data: object,
    *,
    accessor: RowAccessor[Any] | None = None,
) -> DataSource[Any]:
    """Normalize row input without iterating it.

    Returns:
        A lazy source implementing the public protocol.

    Raises:
        CaxtonTypeError: If an accessor is supplied for an existing data source.
    """
    if isinstance(data, DataSource):
        if accessor is not None:
            message = "An accessor cannot override a ready DataSource"
            raise CaxtonTypeError(message)
        return data
    _reject_columnar_source(data)
    resolved_accessor = accessor or DefaultRowAccessor()
    if isinstance(data, Mapping):
        return _single_source(data, resolved_accessor)
    if _is_named_tuple(data) or _is_dataclass_instance(data):
        return _single_source(data, resolved_accessor)
    if _is_rejected_scalar(data):
        return _raise_unsupported(data)
    if isinstance(data, Iterable):
        return _iterable_source(data, resolved_accessor)
    if _is_attribute_object(data) or (
        accessor is not None and _is_non_builtin_object(data)
    ):
        return _single_source(data, resolved_accessor)
    return _raise_unsupported(data)


def _single_source(row: RowT, accessor: RowAccessor[RowT]) -> IterableDataSource[RowT]:
    return IterableDataSource((row,), accessor, Repeatability.REITERABLE, 1)


def _iterable_source(
    rows: Iterable[RowT],
    accessor: RowAccessor[RowT],
) -> IterableDataSource[RowT]:
    repeatability = _classify_repeatability(rows)
    row_count = (
        len(rows)
        if isinstance(rows, _KNOWN_CONTAINERS) and isinstance(rows, Sized)
        else None
    )
    return IterableDataSource(rows, accessor, repeatability, row_count)


def _classify_repeatability(rows: Iterable[object]) -> Repeatability:
    if isinstance(rows, Iterator):
        return Repeatability.ONE_SHOT
    if isinstance(rows, _KNOWN_CONTAINERS):
        return Repeatability.REITERABLE
    return Repeatability.UNKNOWN


def _reject_columnar_source(data: object) -> None:
    data_type = type(data)
    module = data_type.__module__.partition(".")[0]
    if module in {"pandas", "polars", "pyarrow"}:
        message = f"Columnar {data_type.__name__} input is not supported"
        raise UnsupportedDataSourceError(
            message,
            context={"data_type": data_type.__name__},
        )


def _is_named_tuple(data: object) -> bool:
    return isinstance(data, tuple) and hasattr(type(data), "_fields")


def _is_dataclass_instance(data: object) -> bool:
    return dataclasses.is_dataclass(data) and not isinstance(data, type)


def _is_rejected_scalar(data: object) -> bool:
    return (
        data is None
        or isinstance(data, (str, bytes, bytearray, int, float, complex, bool, type))
        or inspect.ismodule(data)
        or callable(data)
    )


def _is_attribute_object(data: object) -> bool:
    if not _is_non_builtin_object(data):
        return False
    instance_fields = getattr(data, "__dict__", {})
    if isinstance(instance_fields, Mapping) and any(
        not name.startswith("_") for name in instance_fields
    ):
        return True
    data_type = type(data)
    if _public_slots(data_type) or _public_annotations(data_type):
        return True
    return any(isinstance(value, property) for value in data_type.__dict__.values())


def _is_non_builtin_object(data: object) -> bool:
    return type(data).__module__ != "builtins"


def _public_slots(data_type: type[object]) -> tuple[str, ...]:
    slots: list[str] = []
    for class_type in data_type.__mro__:
        declared = class_type.__dict__.get("__slots__", ())
        names = (declared,) if isinstance(declared, str) else declared
        slots.extend(name for name in names if not name.startswith("_"))
    return tuple(slots)


def _public_annotations(data_type: type[object]) -> tuple[str, ...]:
    annotations: list[str] = []
    for class_type in data_type.__mro__:
        declared = inspect.get_annotations(class_type)
        annotations.extend(name for name in declared if not name.startswith("_"))
    return tuple(annotations)


def _raise_unsupported(data: object) -> NoReturn:
    data_type = type(data).__name__
    message = f"Unsupported data source: {data_type}"
    raise UnsupportedDataSourceError(
        message,
        context={"data_type": data_type},
    )


@overload
def data_source(
    data: DataSource[RowT], *, accessor: None = None
) -> DataSource[RowT]: ...


@overload
def data_source(data: DataSource[RowT], *, accessor: RowAccessor[Any]) -> NoReturn: ...


@overload
def data_source(
    data: MappingRowT, *, accessor: RowAccessor[MappingRowT] | None = None
) -> DataSource[MappingRowT]: ...


@overload
def data_source(
    data: Iterable[RowT], *, accessor: RowAccessor[RowT] | None = None
) -> DataSource[RowT]: ...


@overload
def data_source(
    data: RowT, *, accessor: RowAccessor[RowT] | None = None
) -> DataSource[RowT]: ...


def data_source(
    data: object,
    *,
    accessor: RowAccessor[Any] | None = None,
) -> DataSource[Any]:
    """Normalize explicit row-oriented input into the public protocol.

    Returns:
        A lazy source implementing the public protocol.
    """
    return coerce_data_source(data, accessor=accessor)
