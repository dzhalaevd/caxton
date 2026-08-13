from __future__ import annotations

import dataclasses
from typing import ClassVar

from .base import SemanticType


@dataclasses.dataclass(frozen=True, slots=True)
class Duration(SemanticType):
    name: ClassVar[str] = "duration"
