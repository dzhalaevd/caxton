from __future__ import annotations

import dataclasses
from typing import ClassVar, Self

from formata.core.errors import FormataTypeError


@dataclasses.dataclass(frozen=True, slots=True)
class SemanticType:
    """Backend-independent meaning of a document value."""

    name: ClassVar[str]

    def __new__(cls, *_args: object, **_kwargs: object) -> Self:
        if cls is SemanticType:
            message = "SemanticType is abstract and cannot be instantiated"
            raise FormataTypeError(message)
        return object.__new__(cls)
