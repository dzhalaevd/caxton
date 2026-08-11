from __future__ import annotations

import dataclasses
import math
from typing import Literal, Self

from formata.core.errors import FormataTypeError, FormataValueError
from formata.core.formatting import Alignment, DisplayFormat, StyleInput
from formata.core.types import SemanticType

from .expressions import ColumnSource, ColumnSourceInput, normalize_source
from .formulas import Formula, FormulaInput, as_formula


@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class Column:
    """Immutable semantic column specification."""

    id: str
    semantic_type: SemanticType
    source: ColumnSource | None
    excel_formula: Formula | None = None
    _title: str | None = None
    alignment: Alignment | None = None
    width_hint: float | None = None
    display_format: DisplayFormat | None = None
    style_ref: StyleInput | None = None
    auto_width: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.id, str):
            message = "Column id must be a string"
            raise FormataTypeError(message)
        if not self.id.strip():
            message = "Column id cannot be empty"
            raise FormataValueError(message)

    @property
    def display_title(self) -> str:
        """Explicit title, or the semantic id when no title was set."""
        return self._title if self._title is not None else self.id

    def title(self, value: str) -> Self:
        """Return a column with a different display title.

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
        return dataclasses.replace(self, _title=value)

    def align(self, value: Alignment | str) -> Self:
        """Return a column with a horizontal alignment hint.

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
        """Return a column with a backend-independent display format."""
        return dataclasses.replace(self, display_format=value)

    def formula(self, value: FormulaInput) -> Self:
        """Return a column whose cells retain an Excel formula in the artifact."""
        return dataclasses.replace(
            self,
            source=None,
            excel_formula=as_formula(value),
        )

    def styled(self, value: StyleInput) -> Self:
        """Return a column with an inline or reusable style reference."""
        return dataclasses.replace(self, style_ref=value)


def make_column(
    column_id: str,
    semantic_type: SemanticType,
    source: ColumnSourceInput,
    formula: FormulaInput | None = None,
    style: StyleInput | None = None,
) -> Column:
    if not isinstance(column_id, str):
        message = "Column id must be a string"
        raise FormataTypeError(message)
    if formula is not None and source is not None:
        message = "A column cannot define both a Python source and an Excel formula"
        raise FormataValueError(message)
    return Column(
        id=column_id,
        semantic_type=semantic_type,
        source=None if formula is not None else normalize_source(column_id, source),
        excel_formula=None if formula is None else as_formula(formula),
        style_ref=style,
    )


__all__ = ("Column",)
