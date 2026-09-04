from __future__ import annotations

import dataclasses
from typing import ClassVar, Final

from caxton.core._compat import Self
from caxton.core.errors import CaxtonTypeError, CaxtonValueError
from caxton.core.formatting import DisplayFormat, MoneyFormat


@dataclasses.dataclass(frozen=True, slots=True)
class SemanticType:
    """Backend-independent meaning of a document value.

    The base class is abstract; every concrete type assigns its own ``name``,
    which ``__init_subclass__`` verifies at class-definition time instead of
    failing with an ``AttributeError`` at first use.

    The set is open. A subclass declares how it behaves rather than relying on
    the renderer to recognize it by name:

    - ``name`` identifies the type in diagnostics and renderer capabilities;
    - ``numeric`` marks values a totals row may aggregate;
    - :meth:`default_format` returns the presentation the type asks for when a
      column declares no explicit display format.

    A renderer that reports the ``semantic:extension`` capability renders such
    a type through its declared display format, so no renderer change is needed
    to introduce one.
    """

    name: ClassVar[str]
    numeric: ClassVar[bool] = False

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

    def default_format(self) -> DisplayFormat | None:
        """Return the presentation this type asks for by default.

        Returns:
            A backend-independent display format, or ``None`` to leave the
            choice to the renderer's own default for this type.
        """
        default: DisplayFormat | None = None
        return default


@dataclasses.dataclass(frozen=True, slots=True)
class Boolean(SemanticType):
    name: ClassVar[str] = "boolean"


@dataclasses.dataclass(frozen=True, slots=True)
class Date(SemanticType):
    name: ClassVar[str] = "date"


@dataclasses.dataclass(frozen=True, slots=True)
class DateTime(SemanticType):
    name: ClassVar[str] = "datetime"


@dataclasses.dataclass(frozen=True, slots=True)
class Decimal(SemanticType):
    name: ClassVar[str] = "decimal"
    numeric: ClassVar[bool] = True


@dataclasses.dataclass(frozen=True, slots=True)
class Duration(SemanticType):
    name: ClassVar[str] = "duration"
    numeric: ClassVar[bool] = True


@dataclasses.dataclass(frozen=True, slots=True)
class Integer(SemanticType):
    name: ClassVar[str] = "integer"
    numeric: ClassVar[bool] = True


@dataclasses.dataclass(frozen=True, slots=True)
class Link(SemanticType):
    name: ClassVar[str] = "link"


@dataclasses.dataclass(frozen=True, slots=True)
class Money(SemanticType):
    name: ClassVar[str] = "money"
    numeric: ClassVar[bool] = True

    currency: str | None = None

    def __post_init__(self) -> None:
        if self.currency is not None and (
            not isinstance(self.currency, str) or not self.currency.strip()
        ):
            message = "Currency cannot be empty"
            raise CaxtonValueError(message)

    def default_format(self) -> DisplayFormat:
        """Return the money presentation carrying this value's currency.

        Returns:
            A money format with two places and digit grouping.
        """
        return MoneyFormat(currency=self.currency, places=2, grouping=True)


@dataclasses.dataclass(frozen=True, slots=True)
class Percentage(SemanticType):
    """Ratio stored as a fraction: 0.15 means 15 percent."""

    name: ClassVar[str] = "percentage"
    numeric: ClassVar[bool] = True


@dataclasses.dataclass(frozen=True, slots=True)
class Text(SemanticType):
    name: ClassVar[str] = "text"


@dataclasses.dataclass(frozen=True, slots=True)
class Time(SemanticType):
    name: ClassVar[str] = "time"


_SemanticTypeClasses = tuple[type[SemanticType], ...]


BUILTIN_SEMANTIC_TYPES: Final[_SemanticTypeClasses] = (
    Boolean,
    Date,
    DateTime,
    Decimal,
    Duration,
    Integer,
    Link,
    Money,
    Percentage,
    Text,
    Time,
)


__all__ = (
    "BUILTIN_SEMANTIC_TYPES",
    "Boolean",
    "Date",
    "DateTime",
    "Decimal",
    "Duration",
    "Integer",
    "Link",
    "Money",
    "Percentage",
    "SemanticType",
    "Text",
    "Time",
)
