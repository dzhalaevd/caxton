from __future__ import annotations

import dataclasses
import enum
import math
from typing import Literal, Self, get_args

from caxton.core.errors import CaxtonTypeError, CaxtonValueError
from caxton.core.formatting import Alignment, DisplayFormat, Style, StyleInput
from caxton.core.types import SemanticType

from ._validation import require_name
from .expressions import ColumnSource, ColumnSourceInput, normalize_source
from .formulas import Formula, FormulaInput, as_formula

_DISPLAY_FORMATS = get_args(DisplayFormat)


class GroupOrder(enum.StrEnum):
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


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class Column:
    """Immutable semantic column specification.

    A column defines its value either through a Python ``source`` evaluated
    before rendering or through an ``excel_formula`` retained in the artifact,
    never both and never neither.
    """

    id: str
    semantic_type: SemanticType
    source: ColumnSource | None
    excel_formula: Formula | None = None
    title: str | None = None
    alignment: Alignment | None = None
    width_hint: float | None = None
    display_format: DisplayFormat | None = None
    style_ref: StyleInput | None = None
    auto_width: bool = False
    grouping: Grouping | None = None

    def __post_init__(self) -> None:
        require_name(self.id, "Column id")
        if (self.source is None) == (self.excel_formula is None):
            message = "A column must define either a Python source or an Excel formula"
            raise CaxtonValueError(message)

    @property
    def display_title(self) -> str:
        """Explicit title, or the semantic id when no title was set."""
        return self.id if self.title is None else self.title

    def titled(self, value: str) -> Self:
        """Return a column with a different display title.

        Returns:
            A column carrying the new display title.

        Raises:
            CaxtonTypeError: If the title is not a string.
            CaxtonValueError: If the title is empty.
        """
        if not isinstance(value, str):
            message = "Column title must be a string"
            raise CaxtonTypeError(message)
        if not value.strip():
            message = "Column title cannot be empty"
            raise CaxtonValueError(message)
        return dataclasses.replace(self, title=value)

    def align(self, value: Alignment | str) -> Self:
        """Return a column with a horizontal alignment hint.

        Returns:
            A column carrying the new alignment.

        Raises:
            CaxtonTypeError: If the alignment has an invalid type.
            CaxtonValueError: If the alignment name is unsupported.
        """
        if not isinstance(value, (Alignment, str)):
            message = "Column alignment must be a string or Alignment"
            raise CaxtonTypeError(message)
        try:
            alignment = Alignment(value)
        except ValueError as error:
            message = f"Unsupported column alignment {value!r}"
            raise CaxtonValueError(message) from error
        return dataclasses.replace(self, alignment=alignment)

    def width(self, value: float | Literal["auto"]) -> Self:
        """Return a column with a positive width hint.

        Returns:
            A column carrying the new width intent.

        Raises:
            CaxtonTypeError: If the width is not numeric.
            CaxtonValueError: If the width is not positive and finite.
        """
        if value == "auto":
            return dataclasses.replace(self, width_hint=None, auto_width=True)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            message = "Column width must be numeric"
            raise CaxtonTypeError(message)
        if not math.isfinite(value) or value <= 0:
            message = "Column width must be positive"
            raise CaxtonValueError(message)
        return dataclasses.replace(self, width_hint=float(value), auto_width=False)

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
        return dataclasses.replace(self, style_ref=value)

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


def make_column(
    column_id: str,
    semantic_type: SemanticType,
    source: ColumnSourceInput,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    """Build a semantic column from declared factory arguments.

    Returns:
        An immutable column specification.

    Raises:
        CaxtonTypeError: If the column id is not a string.
        CaxtonValueError: If both a Python source and a formula are supplied.
    """
    if not isinstance(column_id, str):
        message = "Column id must be a string"
        raise CaxtonTypeError(message)
    if formula is not None and source is not None:
        message = "A column cannot define both a Python source and an Excel formula"
        raise CaxtonValueError(message)
    require_name(column_id, "Column id")
    return Column(
        id=column_id,
        semantic_type=semantic_type,
        source=None if formula is not None else normalize_source(column_id, source),
        excel_formula=None if formula is None else as_formula(formula),
        style_ref=style,
    )


__all__ = ("Column", "GroupOrder", "Grouping")
