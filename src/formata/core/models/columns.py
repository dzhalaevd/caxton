from __future__ import annotations

import dataclasses
import math
from typing import Literal, Self, get_args

from formata.core.errors import FormataTypeError, FormataValueError
from formata.core.formatting import Alignment, DisplayFormat, Style, StyleInput
from formata.core.types import SemanticType

from ._validation import require_name
from .expressions import ColumnSource, ColumnSourceInput, normalize_source
from .formulas import Formula, FormulaInput, as_formula

_DISPLAY_FORMATS = get_args(DisplayFormat)


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

    def __post_init__(self) -> None:
        require_name(self.id, "Column id")
        if (self.source is None) == (self.excel_formula is None):
            message = "A column must define either a Python source or an Excel formula"
            raise FormataValueError(message)

    @property
    def display_title(self) -> str:
        """Explicit title, or the semantic id when no title was set."""
        return self.id if self.title is None else self.title

    def titled(self, value: str) -> Self:
        """Return a column with a different display title.

        Returns:
            A column carrying the new display title.

        Raises:
            FormataTypeError: If the title is not a string.
            FormataValueError: If the title is empty.
        """
        if not isinstance(value, str):
            message = "Column title must be a string"
            raise FormataTypeError(message)
        if not value.strip():
            message = "Column title cannot be empty"
            raise FormataValueError(message)
        return dataclasses.replace(self, title=value)

    def align(self, value: Alignment | str) -> Self:
        """Return a column with a horizontal alignment hint.

        Returns:
            A column carrying the new alignment.

        Raises:
            FormataTypeError: If the alignment has an invalid type.
            FormataValueError: If the alignment name is unsupported.
        """
        if not isinstance(value, (Alignment, str)):
            message = "Column alignment must be a string or Alignment"
            raise FormataTypeError(message)
        try:
            alignment = Alignment(value)
        except ValueError as error:
            message = f"Unsupported column alignment {value!r}"
            raise FormataValueError(message) from error
        return dataclasses.replace(self, alignment=alignment)

    def width(self, value: float | Literal["auto"]) -> Self:
        """Return a column with a positive width hint.

        Returns:
            A column carrying the new width intent.

        Raises:
            FormataTypeError: If the width is not numeric.
            FormataValueError: If the width is not positive and finite.
        """
        if value == "auto":
            return dataclasses.replace(self, width_hint=None, auto_width=True)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            message = "Column width must be numeric"
            raise FormataTypeError(message)
        if not math.isfinite(value) or value <= 0:
            message = "Column width must be positive"
            raise FormataValueError(message)
        return dataclasses.replace(self, width_hint=float(value), auto_width=False)

    def format(self, value: DisplayFormat) -> Self:
        """Return a column with a backend-independent display format.

        Returns:
            A column carrying the new display format.

        Raises:
            FormataTypeError: If the value is not a display format.
        """
        if not isinstance(value, _DISPLAY_FORMATS):
            message = "Column format must be a display format"
            raise FormataTypeError(message)
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
            FormataTypeError: If the value is neither a style nor a style name.
        """
        if not isinstance(value, (Style, str)):
            message = "Column style must be a Style or a style name"
            raise FormataTypeError(message)
        return dataclasses.replace(self, style_ref=value)


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
        FormataTypeError: If the column id is not a string.
        FormataValueError: If both a Python source and a formula are supplied.
    """
    if not isinstance(column_id, str):
        message = "Column id must be a string"
        raise FormataTypeError(message)
    if formula is not None and source is not None:
        message = "A column cannot define both a Python source and an Excel formula"
        raise FormataValueError(message)
    require_name(column_id, "Column id")
    return Column(
        id=column_id,
        semantic_type=semantic_type,
        source=None if formula is not None else normalize_source(column_id, source),
        excel_formula=None if formula is None else as_formula(formula),
        style_ref=style,
    )


__all__ = ("Column",)
