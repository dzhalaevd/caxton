from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Sequence

from caxton.core._compat import Self
from caxton.core.formatting import Alignment, DisplayFormat, StyleInput
from caxton.core.models import Column
from caxton.core.types import SemanticType
from caxton.core.values import CellValue


@dataclasses.dataclass(frozen=True, slots=True)
class RelativeMerge:
    """A vertical merge expressed in zero-based table data-row offsets."""

    column_offset: int
    start_row: int
    end_row: int


@dataclasses.dataclass(frozen=True, slots=True)
class PreparedColumn:
    """Renderer-neutral metadata for one prepared tabular column."""

    id: str
    title: str
    semantic_type: SemanticType
    alignment: Alignment | None = None
    width_hint: float | None = None
    display_format: DisplayFormat | None = None
    style_ref: StyleInput | None = None
    auto_width: bool = False
    matrix_key: tuple[CellValue, ...] | None = None

    @classmethod
    def from_column(cls, column: Column) -> Self:
        """Copy renderer-neutral column metadata from semantic intent.

        Returns:
            A prepared column detached from the public semantic node.
        """
        return cls(
            id=column.id,
            title=column.display_title,
            semantic_type=column.semantic_type,
            alignment=column.alignment,
            width_hint=column.width_hint,
            display_format=column.display_format,
            style_ref=column.style_ref,
            auto_width=column.auto_width,
        )


@dataclasses.dataclass(frozen=True, slots=True)
class PreparedTabularData:
    """Buffered output of grouped-table or matrix semantic execution."""

    columns: Sequence[PreparedColumn]
    rows: Iterable[Sequence[CellValue]]
    row_count: int
    merges: Sequence[RelativeMerge] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "columns", tuple(self.columns))
        object.__setattr__(self, "merges", tuple(self.merges))


__all__ = ("PreparedColumn", "PreparedTabularData", "RelativeMerge")
