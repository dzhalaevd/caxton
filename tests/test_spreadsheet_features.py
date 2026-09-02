import datetime as dt
from collections.abc import Iterator
from itertools import starmap

import pytest

from caxton import (
    AggregateFunction,
    AutoWidth,
    CaxtonTypeError,
    CaxtonValueError,
    CorporateTheme,
    FillStyle,
    FontStyle,
    Freeze,
    Style,
    StyleSheet,
    Total,
    Totals,
    ValidationError,
    col,
    custom_format,
    date,
    date_format,
    decimal,
    decimal_format,
    percentage,
    percentage_format,
    render,
    sheet,
    spreadsheet,
    table,
    text,
    time,
    time_format,
    validate,
    when,
)
from caxton._internal.backends._common import fitted_width  # noqa: PLC2701
from caxton._internal.backends.openpyxl import (  # noqa: PLC2701
    OpenpyxlRenderer,
)
from caxton._internal.backends.xlsxwriter import (  # noqa: PLC2701
    XlsxWriterRenderer,
)
from caxton._internal.requirements import (  # noqa: PLC2701
    analyze_spreadsheet_requirements,
)
from caxton.core.formatting import money_format
from caxton.testing import (
    Rows,
    SpreadsheetAssertionError,
    assert_spreadsheet_equal,
    canonical_snapshot,
    inspect_artifact,
    inspect_layout,
    inspect_spec,
)


def test_spreadsheet_features_are_immutable_lazy_semantic_intent() -> None:
    visited = False

    def rows() -> Iterator[dict[str, object]]:
        nonlocal visited
        visited = True
        yield {"name": "A", "amount": 10, "delta": 2}

    styles = StyleSheet(
        {
            "money": Style(display_format=money_format()),
            "positive": Style(fill="#C6EFCE", font_color="#006100"),
        },
    )
    document = spreadsheet(
        sheet(
            "Sales",
            table(
                source=rows(),
                columns=(
                    text(id="name", source="name"),
                    decimal(id="amount", source="amount", style="money").width("auto"),
                    decimal(id="delta", source="delta"),
                ),
                name="sales",
                header_style=Style(
                    font=FontStyle(bold=True, size=12),
                    fill="#D9EAF7",
                    align="center",
                    border_bottom="thin",
                ),
                footer=Totals(
                    label="Total",
                    items=(Total("amount"),),
                ),
                rules=(
                    when(
                        (col("delta") > 0) & (col("amount") > 0),
                        style="positive",
                    ),
                ),
                autofilter=True,
                freeze_header=True,
                auto_width=True,
            ),
            freeze=Freeze(rows=0, columns=1),
        ),
        styles=styles,
        theme=CorporateTheme(
            font="Arial",
            header_fill="#004B8D",
            header_font_color="#FFFFFF",
        ),
    )

    spec = inspect_spec(document)
    sales = spec.worksheet("Sales").table("sales")

    assert not visited
    assert spec.styles["money"].display_format == money_format()
    assert spec.theme.default.font == FontStyle(name="Arial")
    assert spec.worksheet("Sales").freeze == Freeze(rows=0, columns=1)
    assert isinstance(sales.header_style, Style)
    assert sales.header_style.fill is not None
    assert sales.autofilter
    assert sales.freeze_header
    assert sales.auto_width
    assert sales.footer == Totals(
        label="Total",
        items=(Total("amount"),),
    )
    assert sales.rules[0].condition is not None
    assert sales.column("amount").style == "money"
    assert sales.column("amount").auto_width


def test_spreadsheet_features_compile_to_resolved_layout() -> None:
    table_width = AutoWidth(minimum=15, maximum=40)
    amount_width = AutoWidth(minimum=10, maximum=20)
    document = spreadsheet(
        sheet(
            "Sales",
            table(
                source=[{"name": "A", "amount": 10, "delta": 2}],
                columns=(
                    text(id="name", source="name"),
                    decimal(id="amount", source="amount", style="money").width(
                        amount_width,
                    ),
                    decimal(id="delta", source="delta"),
                ),
                name="sales",
                anchor="C4",
                header_style=Style(fill="#D9EAF7", align="center"),
                footer=Totals(items=(Total("amount"),)),
                rules=(
                    when(
                        (col("delta") > 0) & (col("amount") > 0),
                        style="positive",
                    ),
                ),
                autofilter=True,
                freeze_header=True,
                auto_width=table_width,
            ),
            freeze=Freeze(rows=0, columns=1),
        ),
        styles=StyleSheet(
            {
                "money": Style(display_format=money_format()),
                "positive": Style(fill="#C6EFCE", font_color="#006100"),
            },
        ),
        theme=CorporateTheme(
            font="Arial",
            header_fill="#004B8D",
            header_font_color="#FFFFFF",
        ),
    )

    layout = inspect_layout(document, rows=Rows.all())
    worksheet = layout.worksheet("Sales")
    sales = worksheet.table("sales")

    assert worksheet.freeze == Freeze(rows=4, columns=1)
    assert sales.autofilter
    header_fill = sales.header_style.fill
    assert isinstance(header_fill, FillStyle)
    assert header_fill.color == "#D9EAF7"
    assert sales.header_style.font == FontStyle(
        name="Arial",
        bold=True,
        color="#FFFFFF",
    )
    assert sales.column("amount").auto_width == amount_width
    assert sales.column("name").auto_width == table_width
    assert sales.column("amount").display_format == money_format()
    assert sales.footer is not None
    assert sales.footer.items[0].column_offset == 1
    assert sales.rules[0].formula == "=AND($E5>0,$D5>0)"


@pytest.mark.parametrize("backend", ["xlsxwriter", "openpyxl"])
def test_spreadsheet_features_render_backend_neutral_xlsx(backend: str) -> None:
    iterations = 0

    def rows() -> Iterator[dict[str, object]]:
        nonlocal iterations
        iterations += 1
        yield {"name": "North", "amount": 1234.5, "delta": 2}
        yield {"name": "South", "amount": 20, "delta": -1}

    document = spreadsheet(
        sheet(
            "Sales",
            table(
                source=rows(),
                columns=(
                    text(id="name", source="name"),
                    decimal(id="amount", source="amount", style="money").width("auto"),
                    decimal(id="delta", source="delta"),
                ),
                header_style=Style(
                    font=FontStyle(bold=True, size=12),
                    fill="#D9EAF7",
                    align="center",
                    border_bottom="thin",
                ),
                footer=Totals(items=(Total("amount"),)),
                rules=(
                    when(
                        (col("delta") > 0) & (col("amount") > 0),
                        style="positive",
                    ),
                ),
                autofilter=True,
                freeze_header=True,
                auto_width=True,
            ),
            freeze=Freeze(rows=0, columns=1),
        ),
        styles=StyleSheet(
            {
                "money": Style(display_format=money_format()),
                "positive": Style(fill="#C6EFCE", font_color="#006100"),
            },
        ),
    )

    worksheet = inspect_artifact(render(document, backend=backend)).worksheet("Sales")

    assert iterations == 1
    assert worksheet.freeze_panes == "B2"
    assert worksheet.autofilter == "A1:C3"
    assert worksheet.cell("A1").fill_color == "#D9EAF7"
    assert worksheet.cell("A1").border_bottom == "thin"
    assert worksheet.cell("B2").number_format == "#,##0.00"
    assert worksheet.cell("A4").value == "Total"
    assert worksheet.cell("B4").formula == "=SUM(B2:B3)"
    assert worksheet.cell("B4").bold
    width = worksheet.column("B").width
    assert width is not None
    assert width >= 8
    assert worksheet.conditional_formats[0].cell_range == "A2:C3"
    assert worksheet.conditional_formats[0].formulae == ("AND($C2>0,$B2>0)",)
    assert worksheet.conditional_formats[0].fill_color == "#C6EFCE"


@pytest.mark.parametrize("backend", ["xlsxwriter", "openpyxl"])
def test_auto_width_bounds_render_backend_neutral_xlsx(backend: str) -> None:
    policy = AutoWidth(minimum=15, maximum=20)
    document = spreadsheet(
        sheet(
            "Widths",
            table(
                source=[{"short": "x", "long": "x" * 100}],
                columns=(text(source="short"), text(source="long")),
                auto_width=policy,
            ),
        ),
    )

    worksheet = inspect_artifact(render(document, backend=backend)).worksheet("Widths")
    short_width = worksheet.column("A").width
    long_width = worksheet.column("B").width

    assert fitted_width(1, policy) == 15
    assert fitted_width(100, policy) == 20
    assert short_width is not None
    assert long_width is not None
    assert 15 <= short_width < 16
    assert 20 <= long_width < 21


@pytest.mark.parametrize(
    ("kwargs", "error", "message"),
    [
        ({"minimum": "15"}, CaxtonTypeError, "minimum must be numeric"),
        ({"maximum": 0}, CaxtonValueError, "maximum must be positive"),
        (
            {"minimum": 20, "maximum": 10},
            CaxtonValueError,
            "minimum must not exceed",
        ),
    ],
)
def test_auto_width_rejects_invalid_bounds(
    kwargs: dict[str, object],
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error, match=message):
        AutoWidth(**kwargs)  # type: ignore[arg-type]


def test_spreadsheet_feature_validation_is_structural_and_lazy() -> None:
    visited = False

    def rows() -> Iterator[dict[str, int]]:
        nonlocal visited
        visited = True
        yield {"amount": 1}

    document = spreadsheet(
        sheet(
            "Data",
            table(
                source=rows(),
                columns=(decimal(id="amount", source="amount", style="missing"),),
                footer=Totals(items=(Total("unknown"), Total("unknown"))),
                rules=(when(col("unknown") > 0, style="missing"),),
            ),
        ),
    )

    with pytest.raises(ValidationError) as captured:
        validate(document)

    assert not visited
    assert {issue.code for issue in captured.value.issues} == {
        "ColumnNotFoundError",
        "duplicate_total",
        "style_not_found",
    }


def test_capability_analysis_declares_each_stage_three_feature() -> None:
    document = spreadsheet(
        sheet(
            "Data",
            table(
                source=[{"amount": 1}],
                columns=(
                    decimal(id="amount", source="amount", style="number").width("auto"),
                ),
                header_style=Style(fill="#D9EAF7"),
                footer=Totals(items=(Total("amount"),)),
                rules=(when(col("amount") > 0, style=Style(fill="#C6EFCE")),),
                autofilter=True,
                freeze_header=True,
            ),
        ),
        styles=StyleSheet(
            {"number": Style(display_format=decimal_format(grouping=True))},
        ),
    )

    required = analyze_spreadsheet_requirements(document)
    features = {
        "autofilter",
        "auto_width",
        "conditional_format",
        "display_format",
        "freeze_panes",
        "formula",
        "style",
        "totals",
    }

    assert features <= required.features
    assert XlsxWriterRenderer.descriptor.capabilities.supports(required)
    assert OpenpyxlRenderer.descriptor.capabilities.supports(required)


def test_testing_diff_and_snapshot_include_stage_three_properties() -> None:
    actual = spreadsheet(
        sheet(
            "Data",
            table(
                source=[],
                columns=(decimal(id="amount", source="amount").width("auto"),),
                header_style=Style(fill="#FF0000"),
                autofilter=True,
            ),
        ),
    )
    expected = spreadsheet(
        sheet(
            "Data",
            table(
                source=[],
                columns=(decimal(id="amount", source="amount").width("auto"),),
                header_style=Style(fill="#0000FF"),
                autofilter=True,
            ),
        ),
    )

    with pytest.raises(SpreadsheetAssertionError) as captured:
        assert_spreadsheet_equal(actual, expected)

    assert captured.value.differences[0].path.endswith(".header_style")
    snapshot = canonical_snapshot(inspect_spec(actual))
    assert '"$type": "AutoWidth"' in snapshot
    assert '"autofilter": true' in snapshot

    shared_style = Style(fill="#C6EFCE")
    with_rule = spreadsheet(
        sheet(
            "Data",
            table(
                source=[],
                columns=(decimal(id="amount", source="amount"),),
                rules=(when(col("amount") > 0, style=shared_style),),
            ),
        ),
    )
    equivalent = spreadsheet(
        sheet(
            "Data",
            table(
                source=[],
                columns=(decimal(id="amount", source="amount"),),
                rules=(when(col("amount") > 0, style=shared_style),),
            ),
        ),
    )
    different = spreadsheet(
        sheet(
            "Data",
            table(
                source=[],
                columns=(decimal(id="amount", source="amount"),),
                rules=(when(col("amount") < 0, style=shared_style),),
            ),
        ),
    )

    assert_spreadsheet_equal(with_rule, equivalent)
    with pytest.raises(SpreadsheetAssertionError):
        assert_spreadsheet_equal(with_rule, different)


@pytest.mark.parametrize("backend", ["xlsxwriter", "openpyxl"])
def test_expanded_display_formats_render_semantically(backend: str) -> None:
    document = spreadsheet(
        sheet(
            "Formats",
            table(
                source=[
                    {
                        "date": dt.date(2026, 8, 11),
                        "time": dt.time(13, 5),
                        "ratio": 0.125,
                        "weight": 12.5,
                    },
                ],
                columns=(
                    date(id="date", source="date").format(date_format(variant="short")),
                    time(id="time", source="time").format(
                        time_format(seconds=False, clock=12)
                    ),
                    percentage(id="ratio", source="ratio").format(
                        percentage_format(places=1)
                    ),
                    decimal(id="weight", source="weight").format(
                        custom_format("weight", '0.000 "kg"')
                    ),
                ),
            ),
        ),
    )

    worksheet = inspect_artifact(render(document, backend=backend)).worksheet(
        "Formats",
    )

    assert tuple(
        worksheet.cell(address).number_format for address in ("A2", "B2", "C2", "D2")
    ) == ("m/d/yy", "h:mm AM/PM", "0.0%", '0.000 "kg"')


@pytest.mark.parametrize("backend", ["xlsxwriter", "openpyxl"])
def test_all_standard_totals_render_as_formulas(backend: str) -> None:
    document = spreadsheet(
        sheet(
            "Totals",
            table(
                source=[{"label": "A", "a": 1, "b": 2, "c": 3, "d": 4, "e": 5}],
                columns=(
                    text(id="label", source="label"),
                    decimal(id="a", source="a"),
                    decimal(id="b", source="b"),
                    decimal(id="c", source="c"),
                    decimal(id="d", source="d"),
                    decimal(id="e", source="e"),
                ),
                footer=Totals(
                    items=tuple(
                        starmap(
                            Total,
                            zip(
                                ("a", "b", "c", "d", "e"),
                                AggregateFunction,
                                strict=True,
                            ),
                        )
                    ),
                ),
            ),
        ),
    )

    worksheet = inspect_artifact(render(document, backend=backend)).worksheet("Totals")

    assert tuple(worksheet.cell(f"{letter}3").formula for letter in "BCDEF") == (
        "=SUM(B2:B2)",
        "=AVERAGE(C2:C2)",
        "=MIN(D2:D2)",
        "=MAX(E2:E2)",
        "=COUNT(F2:F2)",
    )


@pytest.mark.parametrize("backend", ["xlsxwriter", "openpyxl"])
def test_named_table_autofilter_is_explicit(backend: str) -> None:
    enabled = spreadsheet(
        sheet(
            "Enabled",
            table(
                source=[{"value": 1}],
                columns=(decimal(id="value", source="value"),),
                name="enabled",
                autofilter=True,
            ),
        ),
    )
    disabled = spreadsheet(
        sheet(
            "Disabled",
            table(
                source=[{"value": 1}],
                columns=(decimal(id="value", source="value"),),
                name="disabled",
            ),
        ),
    )

    enabled_table = (
        inspect_artifact(render(enabled, backend=backend))
        .worksheet(
            "Enabled",
        )
        .table("enabled")
    )
    disabled_table = (
        inspect_artifact(render(disabled, backend=backend))
        .worksheet(
            "Disabled",
        )
        .table("disabled")
    )

    assert enabled_table.autofilter
    assert not disabled_table.autofilter
