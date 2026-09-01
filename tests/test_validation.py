from collections.abc import Iterator

from caxton import decimal, ref, sheet, spreadsheet, table, validate
from caxton.testing import assert_spreadsheet_equal, inspect_spec


def test_validation_preserves_model_and_rows() -> None:
    visited = False

    def rows() -> Iterator[dict[str, int]]:
        nonlocal visited
        visited = True
        yield {"gross": 100, "cost": 40}

    document = spreadsheet(
        sheet(
            "Sales",
            table(
                rows(),
                decimal("gross"),
                decimal("cost"),
                decimal("margin", source=ref("gross") - ref("cost")),
                name="sales",
            ),
        ),
    )
    before_validation = inspect_spec(document)

    validate(document)

    assert_spreadsheet_equal(document, before_validation)
    assert not visited
