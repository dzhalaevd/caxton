from __future__ import annotations

import dataclasses
from typing import ClassVar

from .base import SemanticType


@dataclasses.dataclass(frozen=True, slots=True)
class Decimal(SemanticType):
    name: ClassVar[str] = "decimal"
