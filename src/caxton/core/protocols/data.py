from __future__ import annotations

import enum
from collections.abc import Iterator
from typing import Protocol, TypeVar, runtime_checkable

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


__all__ = (
    "DataSource",
    "DataSourceInfo",
    "Repeatability",
    "RowAccessor",
)
