"""Coverage for grouping paths the existing suite left unexercised.

Unlike ``test_grouping_regressions``, every test here passes today. They pin
behaviour that was correct but untested, so a later fix to the known defects
cannot silently change it.
"""

from __future__ import annotations

from caxton import (
    Total,
    decimal,
    field,
    render,
    sheet,
    spreadsheet,
    table,
    text,
)
from caxton.testing import Rows, inspect_artifact, inspect_layout


def test_three_level_grouping_merges_middle_level() -> None:
    """Merge runs resolve on an inner grouping level, not only the first."""
    rows = [
        {"region": "N", "shop": "A", "line": "X", "value": 1},
        {"region": "N", "shop": "A", "line": "Y", "value": 2},
        {"region": "N", "shop": "B", "line": "X", "value": 3},
    ]
    document = spreadsheet(
        sheet(
            "Summary",
            table(
                rows,
                text("region").grouped(merge=True),
                text("shop").grouped(merge=True),
                text("line").grouped(),
                decimal("total", source=field("value").agg(sum)),
            ),
        ),
    )

    grouped = inspect_layout(document, rows=Rows.all()).worksheet("Summary").tables[0]

    assert grouped.merged_ranges == ("A2:A4", "B2:B3")


def test_merged_groups_coexist_with_a_footer() -> None:
    """A merged group column and a totals footer do not disturb each other."""
    rows = [
        {"shop": "A", "line": "X", "value": 1},
        {"shop": "A", "line": "Y", "value": 2},
        {"shop": "B", "line": "X", "value": 3},
    ]
    document = spreadsheet(
        sheet(
            "Summary",
            table(
                rows,
                text("shop").grouped(merge=True),
                text("line").grouped(),
                decimal("total", source=field("value").agg(sum)),
                footer=[Total("total")],
            ),
        ),
    )

    worksheet = inspect_artifact(render(document)).worksheet("Summary")

    assert worksheet.merged_ranges == ("A2:A3",)
    assert worksheet.cell("A4").value == "B"
    assert worksheet.cell("A5").value == "Total"
