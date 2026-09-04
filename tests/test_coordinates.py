from collections.abc import Callable

import pytest

from caxton import CaxtonError
from caxton._internal.normalization import (  # noqa: PLC2701
    format_cell_address,
    parse_cell_address,
)
from caxton.core.ir import (
    SPREADSHEET_IR_VERSION,
    CellAddress,
    CellRange,
    ResolvedCellReference,
    ResolvedRangeReference,
    SpreadsheetIR,
    SpreadsheetTextIR,
)
from caxton.core.rendering import DataSourceRequirements


@pytest.mark.parametrize(
    ("address", "column"),
    [("Z1", 26), ("AA1", 27), ("ZZ1", 702), ("AAA1", 703)],
)
def test_cell_address_round_trip(address: str, column: int) -> None:
    parsed = parse_cell_address(address)

    assert parsed.column == column
    assert format_cell_address(parsed.row, parsed.column) == address


@pytest.mark.parametrize(
    "construct",
    [
        lambda: CellAddress(0, 1),
        lambda: CellRange(CellAddress(2, 1), CellAddress(1, 1)),
        lambda: ResolvedCellReference(column=0, row=1),
        lambda: SpreadsheetTextIR(anchor=CellAddress(1, 1), text="x", span=0),
        lambda: DataSourceRequirements(worksheet_index=-1, table_index=0),
    ],
)
def test_coordinate_contracts_use_caxton_errors(
    construct: Callable[[], object],
) -> None:
    with pytest.raises(CaxtonError):
        construct()


def test_resolved_range_rejects_reversed_bounds() -> None:
    with pytest.raises(CaxtonError, match="must not precede"):
        ResolvedRangeReference(
            sheet_name="Data",
            start=CellAddress(2, 2),
            end=CellAddress(1, 1),
            table_name="records",
            column_title="value",
        )


def test_spreadsheet_ir_rejects_unknown_version() -> None:
    with pytest.raises(CaxtonError, match="version"):
        SpreadsheetIR(worksheets=(), version=SPREADSHEET_IR_VERSION + 1)
