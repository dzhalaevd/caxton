from __future__ import annotations

import dataclasses

from caxton.core.errors import CaxtonError


@dataclasses.dataclass(eq=False)
class ArtifactInspectionError(CaxtonError):
    """Raised when a materialized artifact cannot be read or inspected."""


__all__ = ("ArtifactInspectionError",)
