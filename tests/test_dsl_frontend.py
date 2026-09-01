from collections.abc import Iterator

from caxton import field, money, sheet, spreadsheet, table, text
from caxton.core.models import (
    Column,
    FieldRef,
    SpreadsheetDocument,
    SpreadsheetTable,
    TableData,
    Worksheet,
)
from caxton.core.types import Money, Text
from caxton.testing import assert_spreadsheet_equal


class _EmptySource:
    def iter_rows(self) -> Iterator[object]:
        return iter(())

    def get_value(self, _row: object, _field: str) -> object:
        return object()


def test_table_dsl_matches_direct_semantic_model() -> None:
    visited = False

    def rows() -> Iterator[dict[str, object]]:
        nonlocal visited
        visited = True
        yield {"employee_id": "A-1", "gross": 100}

    actual = spreadsheet(
        sheet(
            "Sales",
            table(
                rows(),
                text("person_id", source="employee_id").titled("Employee"),
                money("revenue", source=field("gross"), currency="USD"),
                name="sales",
            ),
        ),
        metadata={"locale": "en"},
    )
    expected = SpreadsheetDocument(
        worksheets=(
            Worksheet(
                name="Sales",
                blocks=(
                    SpreadsheetTable(
                        data=TableData(
                            source=_EmptySource(),
                            columns=(
                                Column(
                                    id="person_id",
                                    semantic_type=Text(),
                                    source=FieldRef("employee_id"),
                                    title="Employee",
                                ),
                                Column(
                                    id="revenue",
                                    semantic_type=Money(currency="USD"),
                                    source=FieldRef("gross"),
                                ),
                            ),
                        ),
                        name="sales",
                    ),
                ),
            ),
        ),
        metadata={"locale": "en"},
    )

    assert_spreadsheet_equal(actual, expected)
    assert not visited
