import base64
from collections.abc import Iterator

import pytest

from caxton import (
    ValidationError,
    chart,
    decimal,
    image,
    money,
    render,
    sheet,
    spacer,
    spreadsheet,
    stack,
    table,
    table_ref,
    text,
    title,
    validate,
)
from caxton.core.errors import UnsupportedFeatureError
from caxton.core.models import ChartKind, SpreadsheetDocument
from caxton.testing import BlockKind, Rows, inspect_artifact, inspect_layout

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAFElEQVR4nGP8"
    "z8DwnwEJMKEL0FYAAG3fAxAqNQyzAAAAAElFTkSuQmCC",
)


def _rows(count: int = 3) -> list[dict[str, object]]:
    return [{"day": f"d{index}", "revenue": index * 10} for index in range(count)]


def _dashboard() -> SpreadsheetDocument:
    return spreadsheet(
        sheet(
            "Dashboard",
            title("Sales report"),
            spacer(rows=1),
            table(
                _rows(),
                text("day").titled("Day"),
                money("revenue").titled("Revenue"),
                name="sales",
            ),
            spacer(rows=2),
            chart(
                table_ref("sales"),
                x="day",
                y="revenue",
                kind="line",
                title="Revenue by day",
            ),
        ),
    )


def test_flow_layout_places_every_block_in_order() -> None:
    layout = inspect_layout(_dashboard()).worksheet("Dashboard")

    assert [block.anchor for block in layout.blocks] == [
        "A1",
        "A2",
        "A3",
        "A7",
        "A9",
    ]
    assert [block.kind for block in layout.blocks] == [
        BlockKind.TITLE,
        BlockKind.SPACER,
        BlockKind.TABLE,
        BlockKind.SPACER,
        BlockKind.CHART,
    ]
    assert layout.table("sales").anchor == "A3"


def test_flow_layout_reports_occupied_ranges() -> None:
    layout = inspect_layout(_dashboard()).worksheet("Dashboard")

    assert layout.block("block[0]").cell_range == "A1:A1"
    assert layout.block("block[2]").cell_range == "A3:B6"
    assert layout.block("block[4]").cell_range == "A9:H23"


def test_title_resolves_text_and_style() -> None:
    layout = inspect_layout(_dashboard()).worksheet("Dashboard")
    heading = layout.texts[0]

    assert heading.anchor == "A1"
    assert heading.text == "Sales report"
    assert heading.style.font is not None
    assert heading.style.font.bold is True


def test_chart_resolves_series_ranges() -> None:
    layout = inspect_layout(_dashboard()).worksheet("Dashboard")
    plotted = layout.charts[0]

    assert plotted.kind is ChartKind.LINE
    assert plotted.title == "Revenue by day"
    assert plotted.series[0].name == "Revenue"
    assert plotted.series[0].categories == "A4:A6"
    assert plotted.series[0].values == "B4:B6"


def test_image_occupies_measured_cells() -> None:
    document = spreadsheet(
        sheet(
            "Charts",
            image(_PNG, width=128, height=40, name="logo"),
            table(_rows(1), text("day")),
        ),
    )

    layout = inspect_layout(document).worksheet("Charts")

    assert layout.images[0].anchor == "A1"
    assert layout.block("block[0]").cell_range == "A1:B2"
    assert layout.block("block[1]").anchor == "A3"


def test_stack_places_nested_blocks() -> None:
    document = spreadsheet(
        sheet(
            "Charts",
            stack(
                image(_PNG, width=64, height=20),
                image(_PNG, width=64, height=20),
                gap=1,
            ),
            title("After the stack"),
        ),
    )

    layout = inspect_layout(document).worksheet("Charts")

    assert layout.block("block[0].item[0]").anchor == "A1"
    assert layout.block("block[0].item[1]").anchor == "A3"
    assert layout.block("block[1]").anchor == "A4"


def test_horizontal_stack_advances_columns() -> None:
    document = spreadsheet(
        sheet(
            "Charts",
            stack(
                image(_PNG, width=64, height=20),
                image(_PNG, width=64, height=20),
                direction="horizontal",
                gap=1,
            ),
        ),
    )

    layout = inspect_layout(document).worksheet("Charts")

    assert layout.block("block[0].item[1]").anchor == "C1"


def test_explicit_anchor_overrides_flow() -> None:
    document = spreadsheet(
        sheet(
            "Report",
            title("Heading"),
            table(_rows(2), text("day"), anchor="D10", name="sales"),
        ),
    )

    layout = inspect_layout(document).worksheet("Report")

    assert layout.table("sales").anchor == "D10"
    assert layout.block("block[1]").explicit is True


def test_overlapping_blocks_are_reported() -> None:
    document = spreadsheet(
        sheet(
            "Report",
            title("Heading", anchor="A1"),
            table(_rows(2), text("day"), anchor="A1"),
        ),
    )

    with pytest.raises(ValidationError) as captured:
        validate(document)

    assert captured.value.issues[0].code == "block_overlap"


def test_unknown_table_height_stops_the_flow() -> None:
    def lazy() -> Iterator[dict[str, object]]:
        yield {"day": "d0"}

    document = spreadsheet(
        sheet(
            "Report",
            table(lazy(), text("day")),
            title("Below"),
        ),
    )

    with pytest.raises(UnsupportedFeatureError) as captured:
        inspect_layout(document)

    assert captured.value.context["reason"] == "unknown_block_size"


def test_chart_column_must_exist() -> None:
    document = spreadsheet(
        sheet(
            "Report",
            table(_rows(), text("day"), name="sales"),
            chart(table_ref("sales"), x="day", y="missing"),
        ),
    )

    with pytest.raises(ValidationError) as captured:
        validate(document)

    assert captured.value.issues[0].code == "ColumnNotFoundError"


def test_rendered_artifact_contains_blocks() -> None:
    document = spreadsheet(
        sheet(
            "Dashboard",
            title("Sales report", span=2),
            spacer(rows=1),
            table(
                _rows(),
                text("day").titled("Day"),
                decimal("revenue").titled("Revenue"),
                name="sales",
            ),
        ),
    )

    artifact = inspect_artifact(render(document))
    worksheet = artifact.worksheet("Dashboard")

    assert worksheet.cell("A1").value == "Sales report"
    assert worksheet.cell("A3").value == "Day"
    assert "A1:B1" in worksheet.merged_ranges


def test_artifact_accepts_image_and_chart() -> None:
    document = spreadsheet(
        sheet(
            "Dashboard",
            table(
                _rows(),
                text("day"),
                decimal("revenue"),
                name="sales",
            ),
            spacer(rows=1),
            chart(table_ref("sales"), x="day", y="revenue"),
            image(_PNG, width=64, height=40),
        ),
    )

    result = render(document)

    assert result.bytes_written > 0


def test_layout_rows_scope_is_unchanged_by_blocks() -> None:
    layout = inspect_layout(_dashboard(), rows=Rows.all())

    assert len(layout.worksheet("Dashboard").table("sales").rows) == 3
