import dataclasses

from .base import CaxtonError


@dataclasses.dataclass(eq=False)
class RenderError(CaxtonError):
    """Raised when a document cannot be rendered."""


@dataclasses.dataclass(eq=False)
class BackendError(RenderError):
    """Wrap an implementation-specific renderer failure."""

    backend: str | None = dataclasses.field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.backend is not None:
            self.context = {
                **self.context,
                "backend": self.backend,
            }


@dataclasses.dataclass(eq=False)
class TemplateError(RenderError):
    """Base error for template inspection, resolution, and rendering."""


@dataclasses.dataclass(eq=False)
class TemplateFormatError(TemplateError):
    """Raised when a template format cannot be selected safely."""


@dataclasses.dataclass(eq=False)
class TemplateRefError(TemplateError):
    """Base error for invalid logical template targets."""


@dataclasses.dataclass(eq=False)
class MissingTemplateRefError(TemplateRefError):
    """Raised when a logical reference does not exist in the template."""


@dataclasses.dataclass(eq=False)
class AmbiguousTemplateRefError(TemplateRefError):
    """Raised when a logical reference has more than one applicable target."""


@dataclasses.dataclass(eq=False)
class InvalidTemplateRefError(TemplateRefError):
    """Raised when a template target is malformed or cannot be located."""


@dataclasses.dataclass(eq=False)
class IncompatibleTemplateRefError(TemplateRefError):
    """Raised when a target cannot accept the declared semantic content."""
