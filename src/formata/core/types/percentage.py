from __future__ import annotations

import dataclasses
from typing import ClassVar

from .base import SemanticType


@dataclasses.dataclass(frozen=True, slots=True)
class Percentage(SemanticType):
    """Ratio stored as a fraction: 0.15 means 15 percent."""

    name: ClassVar[str] = "percentage"
