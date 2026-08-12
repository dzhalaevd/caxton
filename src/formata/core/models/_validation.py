from __future__ import annotations

from formata.core.errors import FormataTypeError, FormataValueError


def require_name(value: object, label: str) -> None:
    """Validate a required, non-empty name.

    Raises:
        FormataTypeError: If the value is not a string.
        FormataValueError: If the value is blank.
    """
    if not isinstance(value, str):
        message = f"{label} must be a string"
        raise FormataTypeError(message)
    if not value.strip():
        message = f"{label} cannot be empty"
        raise FormataValueError(message)


def require_optional_name(value: object | None, label: str) -> None:
    """Validate a name that may be omitted."""
    if value is None:
        return
    require_name(value, label)


def require_positive(value: object, label: str) -> None:
    """Validate a positive whole number.

    Raises:
        FormataValueError: If the value is not positive.
    """
    number = _require_integer(value, label)
    if number < 1:
        message = f"{label} must be positive"
        raise FormataValueError(message)


def require_non_negative(value: object, label: str) -> None:
    """Validate a non-negative whole number.

    Raises:
        FormataValueError: If the value is negative.
    """
    number = _require_integer(value, label)
    if number < 0:
        message = f"{label} cannot be negative"
        raise FormataValueError(message)


def _require_integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        message = f"{label} must be an integer"
        raise FormataTypeError(message)
    return value


__all__ = (
    "require_name",
    "require_non_negative",
    "require_optional_name",
    "require_positive",
)
