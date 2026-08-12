from __future__ import annotations

import dataclasses

from .base import FormataError


@dataclasses.dataclass(eq=False)
class DataSourceError(FormataError):
    """Base class for data ingestion and row evaluation failures."""


@dataclasses.dataclass(eq=False)
class UnsupportedDataSourceError(DataSourceError):
    """Raised when an input cannot be interpreted as row-oriented data."""


@dataclasses.dataclass(eq=False)
class DataSourceConsumedError(DataSourceError):
    """Raised when a one-shot source is iterated more than once."""


@dataclasses.dataclass(eq=False)
class DataSourceIterationError(DataSourceError):
    """Raised when obtaining the next row from a data source fails."""

    message: str = dataclasses.field(init=False)
    source_type: str = dataclasses.field(kw_only=True)
    row_index: int = dataclasses.field(kw_only=True)

    def __post_init__(self) -> None:
        self.message = f"Failed to read row {self.row_index} from {self.source_type}"
        self.context = {
            **self.context,
            "row_index": self.row_index,
            "source_type": self.source_type,
        }
        super().__post_init__()


@dataclasses.dataclass(eq=False)
class MissingFieldError(DataSourceError):
    """Raised when a row has no requested field."""

    message: str = dataclasses.field(init=False)
    field: str = dataclasses.field(kw_only=True)
    row_type: str = dataclasses.field(kw_only=True)
    row_index: int | None = dataclasses.field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        self.message = f"Field {self.field!r} was not found on {self.row_type}"
        self.context = {
            **self.context,
            "field": self.field,
            "row_index": self.row_index,
            "row_type": self.row_type,
        }
        super().__post_init__()


@dataclasses.dataclass(eq=False)
class DataEvaluationError(DataSourceError):
    """Base class for failures while evaluating row data."""


@dataclasses.dataclass(eq=False)
class FieldAccessError(DataEvaluationError):
    """Raised when an existing attribute fails while being read."""

    message: str = dataclasses.field(init=False)
    field: str = dataclasses.field(kw_only=True)
    row_type: str = dataclasses.field(kw_only=True)
    row_index: int | None = dataclasses.field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        self.message = f"Failed to access field {self.field!r} on {self.row_type}"
        self.context = {
            **self.context,
            "field": self.field,
            "row_index": self.row_index,
            "row_type": self.row_type,
        }
        super().__post_init__()


@dataclasses.dataclass(eq=False)
class CyclicColumnError(DataEvaluationError):
    """Raised when semantic columns reference each other in a cycle."""

    message: str = dataclasses.field(init=False)
    column: str = dataclasses.field(kw_only=True)
    row_index: int | None = dataclasses.field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        self.message = f"Cyclic reference to column {self.column!r}"
        self.context = {
            **self.context,
            "column": self.column,
            "row_index": self.row_index,
        }
        super().__post_init__()


@dataclasses.dataclass(eq=False)
class SourceEvaluationError(DataEvaluationError):
    """Raised when a callable or expression source cannot be evaluated."""

    message: str = dataclasses.field(init=False)
    column: str = dataclasses.field(kw_only=True)
    row_type: str = dataclasses.field(kw_only=True)
    row_index: int = dataclasses.field(kw_only=True)

    def __post_init__(self) -> None:
        self.message = f"Failed to evaluate source for column {self.column!r}"
        self.context = {
            **self.context,
            "column": self.column,
            "row_index": self.row_index,
            "row_type": self.row_type,
        }
        super().__post_init__()
