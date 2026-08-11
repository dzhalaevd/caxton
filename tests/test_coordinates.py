import pytest

from formata._internal.normalization import (  # noqa: PLC2701
    format_cell_address,
    parse_cell_address,
)


@pytest.mark.parametrize(
    ("address", "column"),
    [("Z1", 26), ("AA1", 27), ("ZZ1", 702), ("AAA1", 703)],
)
def test_cell_address_round_trip(address: str, column: int) -> None:
    parsed = parse_cell_address(address)

    assert parsed.column == column
    assert format_cell_address(parsed.row, parsed.column) == address
