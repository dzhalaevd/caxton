from __future__ import annotations

import dataclasses
import math
from collections.abc import Iterator, Mapping, Sequence

from caxton._internal.aggregation import table_needs_preparation
from caxton._internal.block_paths import iter_blocks_with_paths
from caxton._internal.const import (
    _BLOCK_KINDS,
    _OVERLAPPING_KINDS,
    COLUMN_WIDTH_PIXELS,
    ROW_HEIGHT_PIXELS,
)
from caxton._internal.normalization import parse_cell_address
from caxton.core.errors import UnsupportedFeatureError
from caxton.core.ir import CellAddress, CellRange, SpreadsheetBlockKind
from caxton.core.models import (
    BlockDirection,
    Chart,
    Image,
    Matrix,
    Spacer,
    SpreadsheetBlock,
    SpreadsheetDocument,
    SpreadsheetTable,
    Title,
    Worksheet,
)
from caxton.core.protocols import DataSourceInfo


@dataclasses.dataclass(frozen=True, slots=True)
class BlockPlacement:
    """One resolved block position with its measured footprint."""

    block: SpreadsheetBlock
    kind: SpreadsheetBlockKind
    path: str
    anchor: CellAddress
    rows: int | None
    columns: int
    explicit: bool

    @property
    def occupied(self) -> CellRange | None:
        """Inclusive range covered by the block, when its height is known."""
        if self.rows is None:
            return None
        return CellRange(
            start=self.anchor,
            end=CellAddress(
                row=self.anchor.row + max(self.rows, 1) - 1,
                column=self.anchor.column + max(self.columns, 1) - 1,
            ),
        )


@dataclasses.dataclass(frozen=True, slots=True)
class Overlap:
    """Two placed blocks that share at least one worksheet cell."""

    first: str
    second: str
    cell_range: CellRange


@dataclasses.dataclass(frozen=True, slots=True)
class WorksheetPlan:
    """Resolved placement of every block declared by one worksheet."""

    name: str
    placements: Sequence[BlockPlacement]
    overlaps: Sequence[Overlap]

    def __post_init__(self) -> None:
        object.__setattr__(self, "placements", tuple(self.placements))
        object.__setattr__(self, "overlaps", tuple(self.overlaps))


@dataclasses.dataclass(frozen=True, slots=True)
class DocumentPlan:
    """Resolved placement of every worksheet of one document."""

    worksheets: Sequence[WorksheetPlan]

    def __post_init__(self) -> None:
        object.__setattr__(self, "worksheets", tuple(self.worksheets))


def plan_document(
    document: SpreadsheetDocument,
    *,
    measurements: Mapping[SpreadsheetBlock, tuple[int, int]] | None = None,
) -> DocumentPlan:
    """Resolve the flow layout of every worksheet without reading rows.

    Returns:
        A read-only placement plan for the whole document.
    """
    return DocumentPlan(
        worksheets=tuple(
            plan_worksheet(sheet, measurements=measurements)
            for sheet in document.worksheets
        ),
    )


def plan_worksheet(
    worksheet: Worksheet,
    *,
    measurements: Mapping[SpreadsheetBlock, tuple[int, int]] | None = None,
) -> WorksheetPlan:
    """Resolve the flow layout of one worksheet without reading rows.

    Returns:
        A read-only placement plan for the worksheet.
    """
    placements: list[BlockPlacement] = []
    _place_sequence(
        worksheet.blocks,
        origin=CellAddress(1, 1),
        direction=BlockDirection.VERTICAL,
        gap=0,
        path="block",
        placements=placements,
        measurements={} if measurements is None else measurements,
    )
    return WorksheetPlan(
        name=worksheet.name,
        placements=tuple(placements),
        overlaps=tuple(_iter_overlaps(placements)),
    )


@dataclasses.dataclass(slots=True)
class _Cursor:
    """Flow position that becomes unusable after an unmeasurable block."""

    row: int | None
    column: int | None

    def address(self, origin: CellAddress, path: str) -> CellAddress:
        if self.row is None or self.column is None:
            message = "Flow layout needs the size of every preceding block"
            raise UnsupportedFeatureError(
                message,
                context={"block": path, "reason": "unknown_block_size"},
            )
        return CellAddress(row=max(self.row, origin.row), column=self.column)


def _place_sequence(  # noqa: WPS211
    blocks: Sequence[SpreadsheetBlock],
    *,
    origin: CellAddress,
    direction: BlockDirection,
    gap: int,
    path: str,
    placements: list[BlockPlacement],
    measurements: Mapping[SpreadsheetBlock, tuple[int, int]],
) -> tuple[int | None, int]:
    cursor = _Cursor(row=origin.row, column=origin.column)
    span_rows: int | None = 0
    span_columns = 0
    for block, item_path in iter_blocks_with_paths(
        blocks,
        prefix=path,
        recursive=False,
    ):
        placement = _place_block(
            block,
            cursor=cursor,
            origin=origin,
            path=item_path,
            placements=placements,
            measurements=measurements,
        )
        span_rows = _extend(
            span_rows,
            placement.rows,
            origin_row=origin.row,
            anchor_row=placement.anchor.row,
        )
        span_columns = max(
            span_columns,
            placement.anchor.column + placement.columns - origin.column,
        )
        _advance(cursor, placement, direction=direction, gap=gap)
    return span_rows, max(span_columns, 1)


def _place_block(  # noqa: WPS211
    block: SpreadsheetBlock,
    *,
    cursor: _Cursor,
    origin: CellAddress,
    path: str,
    placements: list[BlockPlacement],
    measurements: Mapping[SpreadsheetBlock, tuple[int, int]],
) -> BlockPlacement:
    declared = block.anchor
    explicit = declared is not None
    anchor = (
        parse_cell_address(declared)
        if declared is not None
        else cursor.address(origin, path)
    )
    nested: list[BlockPlacement] = []
    rows, columns = _measure(
        block,
        anchor=anchor,
        path=path,
        placements=nested,
        measurements=measurements,
    )
    placement = BlockPlacement(
        block=block,
        kind=_kind(block),
        path=path,
        anchor=anchor,
        rows=rows,
        columns=columns,
        explicit=explicit,
    )
    placements.append(placement)
    placements.extend(nested)
    return placement


def _advance(
    cursor: _Cursor,
    placement: BlockPlacement,
    *,
    direction: BlockDirection,
    gap: int,
) -> None:
    if direction is BlockDirection.HORIZONTAL:
        cursor.column = placement.anchor.column + placement.columns + gap
        return
    if placement.rows is None:
        cursor.row = None
        return
    end = placement.anchor.row + placement.rows + gap
    if cursor.row is None:
        cursor.row = end if placement.explicit else None
        return
    cursor.row = max(cursor.row, end)


def _extend(
    span: int | None,
    rows: int | None,
    *,
    origin_row: int,
    anchor_row: int,
) -> int | None:
    if span is None or rows is None:
        return None
    return max(span, anchor_row + rows - origin_row)


def _measure(  # noqa: C901, WPS212
    block: SpreadsheetBlock,
    *,
    anchor: CellAddress,
    path: str,
    placements: list[BlockPlacement],
    measurements: Mapping[SpreadsheetBlock, tuple[int, int]],
) -> tuple[int | None, int]:
    measured = measurements.get(block)
    if measured is not None:
        data_rows, columns = measured
        footer_rows = (
            1 if isinstance(block, SpreadsheetTable) and block.footer is not None else 0
        )
        return 1 + data_rows + footer_rows, max(columns, 1)
    if isinstance(block, SpreadsheetTable):
        return _measure_table(block)
    if isinstance(block, Matrix):
        return None, max(len(block.row_dimensions), 1)
    if isinstance(block, Title):
        return 1, block.span
    if isinstance(block, Spacer):
        return block.rows, max(block.columns, 1)
    if isinstance(block, (Image, Chart)):
        return _measure_object(block.width, block.height)
    return _place_sequence(
        block.items,
        origin=anchor,
        direction=block.direction,
        gap=block.gap,
        path=f"{path}.item",
        placements=placements,
        measurements=measurements,
    )


def _measure_table(table: SpreadsheetTable) -> tuple[int | None, int]:
    columns = max(len(table.columns), 1)
    if table_needs_preparation(table):
        return None, columns
    source = table.data.source
    row_count = source.row_count if isinstance(source, DataSourceInfo) else None
    if row_count is None:
        return None, columns
    footer_rows = 1 if table.footer is not None else 0
    return 1 + row_count + footer_rows, columns


def _measure_object(width: int, height: int) -> tuple[int, int]:
    return (
        max(math.ceil(height / ROW_HEIGHT_PIXELS), 1),
        max(math.ceil(width / COLUMN_WIDTH_PIXELS), 1),
    )


def _kind(block: SpreadsheetBlock) -> SpreadsheetBlockKind:
    for block_type, kind in _BLOCK_KINDS:
        if isinstance(block, block_type):
            return kind
    message = f"Unsupported spreadsheet block: {type(block).__name__}"
    raise TypeError(message)


def _iter_overlaps(placements: Sequence[BlockPlacement]) -> Iterator[Overlap]:
    solid = [
        placement
        for placement in placements
        if placement.kind in _OVERLAPPING_KINDS and placement.occupied is not None
    ]
    for index, first in enumerate(solid):
        for second in solid[index + 1 :]:
            shared = _shared_range(first, second)
            if shared is not None:
                yield Overlap(first.path, second.path, shared)


def _shared_range(
    first: BlockPlacement,
    second: BlockPlacement,
) -> CellRange | None:
    left = first.occupied
    right = second.occupied
    if left is None or right is None or not left.intersects(right):
        return None
    return CellRange(
        start=CellAddress(
            row=max(left.start.row, right.start.row),
            column=max(left.start.column, right.start.column),
        ),
        end=CellAddress(
            row=min(left.end.row, right.end.row),
            column=min(left.end.column, right.end.column),
        ),
    )


__all__ = (
    "COLUMN_WIDTH_PIXELS",
    "ROW_HEIGHT_PIXELS",
    "BlockPlacement",
    "DocumentPlan",
    "Overlap",
    "WorksheetPlan",
    "plan_document",
    "plan_worksheet",
)
