from __future__ import annotations

import dataclasses
from typing import ClassVar

from caxton.core._compat import Self
from caxton.core.errors import CaxtonTypeError


@dataclasses.dataclass(frozen=True, slots=True)
class SemanticType:
    """Backend-independent meaning of a document value.

    The base class is abstract; every concrete type assigns its own ``name``,
    which ``__init_subclass__`` verifies at class-definition time instead of
    failing with an ``AttributeError`` at first use.
    """

    name: ClassVar[str]

    def __init_subclass__(cls) -> None:
        if not isinstance(getattr(cls, "name", None), str):
            message = f"{cls.__name__} must declare a semantic type name"
            raise CaxtonTypeError(message)

    def __new__(cls, *_args: object, **_kwargs: object) -> Self:
        """Create a concrete semantic type.

        Returns:
            A new instance of a concrete semantic type.

        Raises:
            CaxtonTypeError: If the abstract base itself is instantiated.
        """
        if cls is SemanticType:
            message = "SemanticType is abstract and cannot be instantiated"
            raise CaxtonTypeError(message)
        return object.__new__(cls)
