from __future__ import annotations

import enum
from collections.abc import Iterable, Iterator, Mapping
from typing import Any, Protocol, TypeAlias, TypeVar, runtime_checkable

RowT = TypeVar("RowT")
AccessorRowT_contra = TypeVar("AccessorRowT_contra", contravariant=True)


class Repeatability(enum.Enum):
    REITERABLE = enum.auto()
    ONE_SHOT = enum.auto()
    UNKNOWN = enum.auto()


@runtime_checkable
class DataSource(Protocol[RowT]):
    """Lazy row source used by semantic table data."""

    def iter_rows(self) -> Iterator[RowT]: ...

    def get_value(self, row: RowT, field: str) -> object: ...


@runtime_checkable
class DataSourceInfo(Protocol):
    """Optional execution hints exposed by a data source."""

    @property
    def repeatability(self) -> Repeatability: ...

    @property
    def row_count(self) -> int | None: ...


@runtime_checkable
class RowAccessor(Protocol[AccessorRowT_contra]):
    """Read one exact field from one row."""

    def __call__(self, row: AccessorRowT_contra, field: str) -> object: ...


RowSourceInput: TypeAlias = DataSource[Any] | Iterable[object] | Mapping[str, object]
"""Row input accepted by the public table factories.

A ready :class:`DataSource`, any iterable of rows, or one mapping row. Rows
themselves stay untyped: a row is read field by field through a
:class:`RowAccessor`, never introspected as a whole.

One bare dataclass, ``NamedTuple`` or attribute object is also accepted at
runtime as a single-row source. That shape is not expressible in a type that
still rejects scalars, so typed callers wrap it in a one-element sequence.
"""


__all__ = (
    "DataSource",
    "DataSourceInfo",
    "Repeatability",
    "RowAccessor",
    "RowSourceInput",
)
