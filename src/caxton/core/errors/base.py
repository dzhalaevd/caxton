import dataclasses
from collections.abc import Mapping
from typing import Any, cast

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
        sections = [self.message]
        if self.path is not None:
            sections.append(f"Path:\n{self.path}")
        if self.context:
            sections.append(f"Context:\n{_render_context(self.context)}")
        return "\n\n".join(sections)

    def __reduce__(  # noqa: WPS603
        self,
    ) -> tuple[object, tuple[object, ...]]:
        """Preserve dataclass constructor state for copy and pickle.

        Returns:
            A reconstruction callable and its pickle-safe arguments.
        """
        arguments = {
            field.name: _pickle_safe(getattr(self, field.name))
            for field in dataclasses.fields(self)
            if field.init
        }
        return _rebuild_error, (type(self), arguments)


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


def _render_context(context: Mapping[str, Any]) -> str:
    return "\n".join(f"  {key}: {value!r}" for key, value in context.items())


def _pickle_safe(value: object) -> object:
    if isinstance(value, Mapping):
        return {_pickle_safe(key): _pickle_safe(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_pickle_safe(item) for item in value)
    if isinstance(value, frozenset):
        return frozenset(_pickle_safe(item) for item in value)
    return value


def _rebuild_error(
    error_type: type[CaxtonError],
    arguments: Mapping[str, object],
) -> CaxtonError:
    constructor = cast("Any", error_type)
    return cast("CaxtonError", constructor(**arguments))
