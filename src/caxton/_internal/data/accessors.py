from __future__ import annotations

import inspect
from collections.abc import Mapping

from caxton.core.errors import FieldAccessError, MissingFieldError


class MappingRowAccessor:
    """Read fields using exact mapping key semantics."""

    def __call__(self, row: Mapping[str, object], field: str) -> object:
        try:
            return row[field]
        except KeyError as error:
            raise _missing_field(row, field) from error
        except Exception as error:
            raise _field_access(row, field, error) from error


class AttributeRowAccessor:
    """Read exact attributes without masking descriptor failures."""

    def __call__(self, row: object, field: str) -> object:
        try:
            return getattr(row, field)
        except AttributeError as error:
            if _has_static_attribute(row, field):
                raise _field_access(row, field, error) from error
            raise _missing_field(row, field) from error
        except Exception as error:
            raise _field_access(row, field, error) from error


class DefaultRowAccessor:
    """Select exact mapping or attribute semantics for each row."""

    def __init__(self) -> None:
        self._mapping = MappingRowAccessor()
        self._attribute = AttributeRowAccessor()

    def __call__(self, row: object, field: str) -> object:
        if isinstance(row, Mapping):
            return self._mapping(row, field)
        return self._attribute(row, field)


def _has_static_attribute(row: object, field: str) -> bool:
    try:
        inspect.getattr_static(row, field)
    except AttributeError:
        return False
    return True


def _missing_field(row: object, field: str) -> MissingFieldError:
    return MissingFieldError(
        field=field,
        row_type=type(row).__name__,
    )


def _field_access(
    row: object,
    field: str,
    error: Exception,
) -> FieldAccessError:
    return FieldAccessError(
        field=field,
        row_type=type(row).__name__,
        context={"exception_type": type(error).__name__},
    )
