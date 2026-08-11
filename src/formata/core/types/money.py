from __future__ import annotations

import dataclasses
from typing import ClassVar

from formata.core.errors import FormataValueError

from .base import SemanticType


@dataclasses.dataclass(frozen=True, slots=True)
class Money(SemanticType):
    name: ClassVar[str] = "money"

    currency: str | None = None

    def __post_init__(self) -> None:
        if self.currency is not None and (
            not isinstance(self.currency, str) or not self.currency.strip()
        ):
            message = "Currency cannot be empty"
            raise FormataValueError(message)
