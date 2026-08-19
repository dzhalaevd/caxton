from __future__ import annotations

import dataclasses
from typing import ClassVar

from .base import SemanticType


@dataclasses.dataclass(frozen=True, slots=True)
class Boolean(SemanticType):
    name: ClassVar[str] = "boolean"
