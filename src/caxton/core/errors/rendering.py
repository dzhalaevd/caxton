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
