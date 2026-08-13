from __future__ import annotations

import dataclasses

from caxton.core.errors import CaxtonTypeError, CaxtonValueError


@dataclasses.dataclass(frozen=True, slots=True)
class DecimalFormat:
    """Display preferences for decimal values."""

    places: int = 2
    grouping: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.places, bool) or not isinstance(self.places, int):
            message = "Decimal places must be an integer"
            raise CaxtonTypeError(message)
        if self.places < 0:
            message = "Decimal places cannot be negative"
            raise CaxtonValueError(message)


@dataclasses.dataclass(frozen=True, slots=True)
class MoneyFormat:
    """Display preferences for monetary values."""

    currency: str | None = None
    places: int = 2
    grouping: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.places, bool) or not isinstance(self.places, int):
            message = "Money places must be an integer"
            raise CaxtonTypeError(message)
        if self.places < 0:
            message = "Money places cannot be negative"
            raise CaxtonValueError(message)
        if self.currency is not None and (
            not isinstance(self.currency, str) or not self.currency.strip()
        ):
            message = "Currency cannot be empty"
            raise CaxtonValueError(message)


@dataclasses.dataclass(frozen=True, slots=True)
class DateFormat:
    """Semantic date display variant."""

    variant: str = "iso"

    def __post_init__(self) -> None:
        if self.variant not in {"iso", "short", "long"}:
            message = f"Unsupported date format {self.variant!r}"
            raise CaxtonValueError(message)


@dataclasses.dataclass(frozen=True, slots=True)
class TimeFormat:
    """Semantic time display variant."""

    seconds: bool = True
    clock: int = 24

    def __post_init__(self) -> None:
        if self.clock not in {12, 24}:
            message = "Time clock must be 12 or 24"
            raise CaxtonValueError(message)


@dataclasses.dataclass(frozen=True, slots=True)
class PercentageFormat:
    """Percentage display preferences."""

    places: int = 2
    grouping: bool = False

    def __post_init__(self) -> None:
        _validate_places(self.places, "Percentage")


@dataclasses.dataclass(frozen=True, slots=True)
class CustomFormat:
    """Named semantic format with an XLSX-compatible fallback pattern."""

    name: str
    pattern: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            message = "Custom format name cannot be empty"
            raise CaxtonValueError(message)
        if not isinstance(self.pattern, str) or not self.pattern:
            message = "Custom format pattern cannot be empty"
            raise CaxtonValueError(message)


DisplayFormat = (
    DecimalFormat
    | MoneyFormat
    | DateFormat
    | TimeFormat
    | PercentageFormat
    | CustomFormat
)


def decimal_format(*, places: int = 2, grouping: bool = False) -> DecimalFormat:
    return DecimalFormat(places=places, grouping=grouping)


def money_format(
    *,
    currency: str | None = None,
    places: int = 2,
    grouping: bool = True,
) -> MoneyFormat:
    return MoneyFormat(currency=currency, places=places, grouping=grouping)


def date_format(*, variant: str = "iso") -> DateFormat:
    return DateFormat(variant=variant)


def time_format(*, seconds: bool = True, clock: int = 24) -> TimeFormat:
    return TimeFormat(seconds=seconds, clock=clock)


def percentage_format(*, places: int = 2, grouping: bool = False) -> PercentageFormat:
    return PercentageFormat(places=places, grouping=grouping)


def custom_format(name: str, pattern: str) -> CustomFormat:
    return CustomFormat(name=name, pattern=pattern)


def _validate_places(value: int, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        message = f"{label} places must be an integer"
        raise CaxtonTypeError(message)
    if value < 0:
        message = f"{label} places cannot be negative"
        raise CaxtonValueError(message)


__all__ = (
    "CustomFormat",
    "DateFormat",
    "DecimalFormat",
    "DisplayFormat",
    "MoneyFormat",
    "PercentageFormat",
    "TimeFormat",
    "custom_format",
    "date_format",
    "decimal_format",
    "money_format",
    "percentage_format",
    "time_format",
)
