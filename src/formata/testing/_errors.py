from __future__ import annotations

import dataclasses

from formata.core.errors import FormataError


@dataclasses.dataclass(eq=False)
class ArtifactInspectionError(FormataError):
    """Raised when a materialized artifact cannot be read or inspected."""


__all__ = ("ArtifactInspectionError",)
