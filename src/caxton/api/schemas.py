from __future__ import annotations

from typing import ClassVar, cast

from caxton.core._compat import Self
from caxton.core.errors import CaxtonTypeError, CaxtonValueError
from caxton.core.models import Column


class ColumnSchema:
    """Named, inheritable organization for immutable column values."""

    columns: ClassVar[tuple[Column, ...]] = ()

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        _require_schema_parent(cls)
        type.__setattr__(cls, "columns", _schema_columns(cls))

    def __new__(cls) -> Self:
        message = f"Column schema {cls.__qualname__!r} cannot be instantiated"
        raise CaxtonTypeError(message, path=_schema_path(cls))


def _require_schema_parent(schema: type[ColumnSchema]) -> None:
    if len(schema.__bases__) == 1 and issubclass(
        schema.__bases__[0],
        ColumnSchema,
    ):
        return
    message = (
        "A column schema requires exactly one schema base; "
        "use explicit tuple composition instead of mixins"
    )
    raise CaxtonTypeError(message, path=_schema_path(schema))


def _schema_columns(schema: type[ColumnSchema]) -> tuple[Column, ...]:
    namespace = vars(schema)  # noqa: WPS421
    if "columns" in namespace:
        message = "Column schema attribute 'columns' is reserved"
        raise CaxtonValueError(
            message,
            path=_column_path(schema, "columns"),
        )
    parent = cast("type[ColumnSchema]", schema.__bases__[0])
    positions = {column.id: index for index, column in enumerate(parent.columns)}
    output = list(parent.columns)
    for name, value in namespace.items():
        column = _declared_column(schema, name, value, inherited=name in positions)
        if column is None:
            continue
        position = positions.get(name)
        if position is None:
            output.append(column)
        else:
            output[position] = column
    return tuple(output)


def _declared_column(
    schema: type[ColumnSchema],
    name: str,
    value: object,
    *,
    inherited: bool,
) -> Column | None:
    if name.startswith("_"):
        return None
    if not isinstance(value, Column):
        if inherited:
            message = f"Inherited column {name!r} must be overridden by a Column"
            raise CaxtonTypeError(message, path=_column_path(schema, name))
        return None
    if name != value.id:
        message = f"Column schema attribute {name!r} must match column ID {value.id!r}"
        raise CaxtonValueError(message, path=_column_path(schema, name))
    return value


def _schema_path(schema: type[ColumnSchema]) -> str:
    return f'schema["{schema.__qualname__}"]'


def _column_path(schema: type[ColumnSchema], name: str) -> str:
    return f'{_schema_path(schema)}.column["{name}"]'


__all__ = ("ColumnSchema",)
