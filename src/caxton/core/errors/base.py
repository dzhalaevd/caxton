import dataclasses
from collections.abc import Mapping
from typing import Any

from caxton.core._values import freeze_mapping


@dataclasses.dataclass(eq=False)
class CaxtonError(Exception):
    """Base class for every public caxton exception."""

    message: str
    path: str | None = dataclasses.field(default=None, kw_only=True)
    context: Mapping[str, Any] = dataclasses.field(default_factory=dict, kw_only=True)

    def __post_init__(self) -> None:
        self.context = freeze_mapping(self.context, label="Error context")
        Exception.__init__(self, self.message)

    def __str__(self) -> str:
        if self.path is None:
            return self.message

        return f"{self.message}\n\nPath:\n{self.path}"


@dataclasses.dataclass(eq=False)
class CaxtonTypeError(CaxtonError, TypeError):
    """Raised when a public argument has an invalid runtime type."""


@dataclasses.dataclass(eq=False)
class CaxtonValueError(CaxtonError, ValueError):
    """Raised when a public argument value violates a local invariant."""


@dataclasses.dataclass(eq=False)
class InvalidOperationError(CaxtonError):
    """Raised when an operation is invalid for the current document state."""


@dataclasses.dataclass(eq=False)
class UnsupportedFeatureError(CaxtonError):
    """Raised when the selected target cannot represent a requested feature."""
