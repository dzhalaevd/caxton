from __future__ import annotations

import dataclasses
import math
from typing import Literal, get_args

from caxton.core._compat import Self, StrEnum
from caxton.core.errors import CaxtonTypeError, CaxtonValueError
from caxton.core.formatting import (
    Alignment,
    AutoWidth,
    DisplayFormat,
    MoneyFormat,
    Style,
    StyleInput,
)
from caxton.core.formatting.widths import resolve_auto_width
from caxton.core.types import Money, SemanticType

from ._validation import require_name, require_optional_name
from .expressions import ColumnSource, ColumnSourceInput, normalize_source
from .formulas import Formula, FormulaInput, as_formula

_DISPLAY_FORMATS = get_args(DisplayFormat)


class GroupOrder(StrEnum):
    """Stable ordering policy for values at one grouping level."""

    FIRST_SEEN = "first_seen"
    ASCENDING = "ascending"
    DESCENDING = "descending"


@dataclasses.dataclass(frozen=True, slots=True, init=False)
class Grouping:
    """Grouping intent attached to one semantic table column."""

    merge: bool = False
    order: GroupOrder = GroupOrder.FIRST_SEEN

    def __init__(
        self,
        merge: bool = False,
        order: GroupOrder | str = GroupOrder.FIRST_SEEN,
    ) -> None:
        if not isinstance(merge, bool):
            message = "Group merge must be a boolean"
            raise CaxtonTypeError(message)
        object.__setattr__(self, "merge", merge)
        try:
            normalized = GroupOrder(order)
        except ValueError as error:
            message = f"Unsupported group order {order!r}"
            raise CaxtonValueError(message) from error
        object.__setattr__(self, "order", normalized)


def _require_currency_is_displayable(
    column_id: str,
    semantic_type: SemanticType,
    display_format: DisplayFormat | None,
) -> None:
    if display_format is None or isinstance(display_format, MoneyFormat):
        return
    if isinstance(semantic_type, Money) and semantic_type.currency is not None:
        message = (
            f"Column {column_id!r} declares currency "
            f"{semantic_type.currency!r}, which "
            f"{type(display_format).__name__} cannot display; format it with "
            "money_format() or drop the currency"
        )
        raise CaxtonValueError(message)


@dataclasses.dataclass(frozen=True, slots=True, eq=False, init=False)
class Column:
    """Immutable semantic column specification.

    A column defines its value either through a Python ``source`` evaluated
    before rendering or through an ``excel_formula`` retained in the artifact,
    never both and never neither. Width is declared the same way: an explicit
    ``width_hint`` or an ``auto_width`` policy, never both at once.
    """

    id: str
    semantic_type: SemanticType
    source: ColumnSource | None
    excel_formula: Formula | None = None
    title: str | None = None
    alignment: Alignment | None = None
    width_hint: float | None = None
    display_format: DisplayFormat | None = None
    style: StyleInput | None = None
    auto_width: AutoWidth | None = None
    grouping: Grouping | None = None

    def __init__(  # noqa: WPS211, WPS213, WPS238
        self,
        *,
        semantic_type: SemanticType,
        id: str | None = None,
        source: ColumnSourceInput = None,
        excel_formula: FormulaInput | None = None,
        title: str | None = None,
        alignment: Alignment | str | None = None,
        width_hint: float | None = None,
        display_format: DisplayFormat | None = None,
        style: StyleInput | None = None,
        auto_width: AutoWidth | bool | None = None,
        grouping: Grouping | None = None,
    ) -> None:
        """Construct and normalize one final semantic column.

        Exactly one of ``source`` and ``excel_formula`` is required.
        ``width_hint`` and ``auto_width`` are likewise mutually exclusive.
        String sources provide the default semantic ID; every other source
        shape and every Excel formula requires an explicit ``id``.

        Raises:
            CaxtonTypeError: If a value has an invalid runtime type.
            CaxtonValueError: If declared values violate a column invariant.
        """
        if not isinstance(semantic_type, SemanticType):
            message = "Column semantic type must be a SemanticType"
            raise CaxtonTypeError(message)
        label = _column_label(id, source)
        if source is not None and excel_formula is not None:
            message = f"{label} cannot define both a Python source and an Excel formula"
            raise CaxtonValueError(message)
        if source is None and excel_formula is None:
            message = f"{label} requires either a Python source or an Excel formula"
            raise CaxtonValueError(message)
        object.__setattr__(self, "id", _resolve_id(id, source))
        object.__setattr__(self, "semantic_type", semantic_type)
        object.__setattr__(self, "source", normalize_source(source))
        object.__setattr__(
            self,
            "excel_formula",
            None if excel_formula is None else as_formula(excel_formula),
        )
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "alignment", _normalize_alignment(alignment))
        object.__setattr__(self, "width_hint", _normalize_width_hint(width_hint))
        object.__setattr__(self, "display_format", display_format)
        object.__setattr__(self, "style", style)
        object.__setattr__(self, "auto_width", resolve_auto_width(auto_width))
        object.__setattr__(self, "grouping", grouping)
        self._validate()

    def _validate(self) -> None:  # noqa: WPS238
        require_name(self.id, "Column id")
        require_optional_name(self.title, "Column title")
        if self.display_format is not None and not isinstance(
            self.display_format,
            _DISPLAY_FORMATS,
        ):
            message = "Column display format must be a display format"
            raise CaxtonTypeError(message)
        _require_currency_is_displayable(
            self.id,
            self.semantic_type,
            self.display_format,
        )
        if self.style is not None and not isinstance(self.style, (Style, str)):
            message = "Column style must be a Style or a style name"
            raise CaxtonTypeError(message)
        if self.grouping is not None and not isinstance(self.grouping, Grouping):
            message = "Column grouping must be a Grouping"
            raise CaxtonTypeError(message)
        if self.width_hint is not None and self.auto_width is not None:
            message = (
                f"Column {self.id!r} cannot set both an explicit width "
                "and an auto-width policy"
            )
            raise CaxtonValueError(message)

    @property
    def display_title(self) -> str:
        """Explicit title, or the semantic id when no title was set."""
        return self.id if self.title is None else self.title

    def titled(self, value: str) -> Self:
        """Return a column with a different display title.

        Returns:
            A column carrying the new display title.

        """
        require_name(value, "Column title")
        return dataclasses.replace(self, title=value)

    def align(self, value: Alignment | str) -> Self:
        """Return a column with a horizontal alignment hint.

        An unsupported alignment name is rejected the same way the constructor
        rejects it.

        Returns:
            A column carrying the new alignment.
        """
        return dataclasses.replace(self, alignment=_normalize_alignment(value))

    def width(self, value: float | Literal["auto"] | AutoWidth) -> Self:
        """Return a column with fixed or content-derived width intent.

        Returns:
            A column carrying the new width intent.

        Raises:
            CaxtonTypeError: If the width is not numeric.
            CaxtonValueError: If the width is not positive and finite.
        """
        if value == "auto":
            return dataclasses.replace(
                self,
                width_hint=None,
                auto_width=AutoWidth(),
            )
        if isinstance(value, AutoWidth):
            return dataclasses.replace(self, width_hint=None, auto_width=value)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            message = "Column width must be numeric"
            raise CaxtonTypeError(message)
        if not math.isfinite(value) or value <= 0:
            message = "Column width must be positive"
            raise CaxtonValueError(message)
        return dataclasses.replace(self, width_hint=float(value), auto_width=None)

    def format(self, value: DisplayFormat) -> Self:
        """Return a column with a backend-independent display format.

        Returns:
            A column carrying the new display format.

        Raises:
            CaxtonTypeError: If the value is not a display format.
        """
        if not isinstance(value, _DISPLAY_FORMATS):
            message = "Column format must be a display format"
            raise CaxtonTypeError(message)
        return dataclasses.replace(self, display_format=value)

    def formula(self, value: FormulaInput) -> Self:
        """Return a column whose cells retain an Excel formula in the artifact.

        The Python source is replaced because a column carries either a source
        or a formula.

        Returns:
            A formula-backed column.
        """
        return dataclasses.replace(
            self,
            source=None,
            excel_formula=as_formula(value),
        )

    def styled(self, value: StyleInput) -> Self:
        """Return a column with an inline or reusable style reference.

        Returns:
            A column carrying the new style reference.

        Raises:
            CaxtonTypeError: If the value is neither a style nor a style name.
        """
        if not isinstance(value, (Style, str)):
            message = "Column style must be a Style or a style name"
            raise CaxtonTypeError(message)
        return dataclasses.replace(self, style=value)

    def grouped(
        self,
        *,
        merge: bool = False,
        order: GroupOrder | str = GroupOrder.FIRST_SEEN,
    ) -> Self:
        """Return a column that defines one hierarchical grouping level.

        Sorted groups keep ``None`` last in both ascending and descending
        order.

        Returns:
            A column carrying immutable grouping intent.
        """
        return dataclasses.replace(self, grouping=Grouping(merge=merge, order=order))


def _column_label(column_id: str | None, source: ColumnSourceInput) -> str:
    name = column_id if isinstance(column_id, str) else source
    if isinstance(name, str) and name.strip():
        return f"Column {name!r}"
    return "A column"


def _normalize_width_hint(value: float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        message = "Column width must be numeric"
        raise CaxtonTypeError(message)
    if not math.isfinite(value) or value <= 0:
        message = "Column width must be positive"
        raise CaxtonValueError(message)
    return float(value)


def _resolve_id(column_id: str | None, source: ColumnSourceInput) -> str:
    if column_id is not None:
        return column_id
    if isinstance(source, str):
        return source
    message = (
        "An explicit column ID is required because the declaration "
        "does not provide an exact field name"
    )
    raise CaxtonValueError(message)


def _normalize_alignment(value: Alignment | str | None) -> Alignment | None:
    if value is None or isinstance(value, Alignment):
        return value
    if not isinstance(value, str):
        message = "Column alignment must be a string or Alignment"
        raise CaxtonTypeError(message)
    try:
        return Alignment(value)
    except ValueError as error:
        message = f"Unsupported column alignment {value!r}"
        raise CaxtonValueError(message) from error


__all__ = ("Column", "GroupOrder", "Grouping")
