"""Shared XLSX worksheet-name validation."""

from collections.abc import Iterable

from caxton.core.errors import UnsupportedFeatureError

_MAX_WORKSHEET_NAME_LENGTH = 31
_INVALID_WORKSHEET_NAME_CHARACTERS = frozenset("[]:*?/\\")


def validate_xlsx_worksheet_names(names: Iterable[str]) -> None:
    """Reject worksheet names that cannot be represented portably in XLSX."""
    for name in names:
        _validate_xlsx_worksheet_name(name)


def _validate_xlsx_worksheet_name(name: str) -> None:
    if len(name) > _MAX_WORKSHEET_NAME_LENGTH:
        _raise_overlong_worksheet_name(name)
    invalid = next(
        (
            character
            for character in name
            if character in _INVALID_WORKSHEET_NAME_CHARACTERS
        ),
        None,
    )
    if invalid is not None:
        message = f"XLSX worksheet name contains invalid character {invalid!r}"
        raise UnsupportedFeatureError(
            message,
            context={
                "character": invalid,
                "constraint": "invalid_character",
                "worksheet": name,
            },
        )
    if name.startswith("'") or name.endswith("'"):
        message = "XLSX worksheet name cannot start or end with an apostrophe"
        raise UnsupportedFeatureError(
            message,
            context={
                "constraint": "surrounding_apostrophe",
                "worksheet": name,
            },
        )


def _raise_overlong_worksheet_name(name: str) -> None:
    message = "XLSX worksheet name exceeds the 31 character limit"
    raise UnsupportedFeatureError(
        message,
        context={
            "constraint": "maximum_length",
            "length": len(name),
            "maximum": _MAX_WORKSHEET_NAME_LENGTH,
            "worksheet": name,
        },
    )


__all__ = ("validate_xlsx_worksheet_names",)
