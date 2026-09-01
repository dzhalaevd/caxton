import dataclasses

import pytest

from caxton import duration, link, money, time
from caxton.core.formatting import decimal_format
from caxton.core.types import (
    Boolean,
    Date,
    DateTime,
    Decimal,
    Duration,
    Integer,
    Link,
    Money,
    Percentage,
    SemanticType,
    Text,
    Time,
)


def test_identifiers_are_explicit_and_stable() -> None:
    identifiers: dict[type[SemanticType], str] = {
        Text: "text",
        Integer: "integer",
        Decimal: "decimal",
        Boolean: "boolean",
        Date: "date",
        Time: "time",
        DateTime: "datetime",
        Duration: "duration",
        Money: "money",
        Percentage: "percentage",
        Link: "link",
    }

    assert {type_.name for type_ in identifiers} == set(identifiers.values())
    assert all(type_.name == name for type_, name in identifiers.items())


def test_money_currency_is_value_semantics() -> None:
    rubles = Money(currency="RUB")

    assert Money().currency is None
    assert rubles.currency == "RUB"
    assert [field.name for field in dataclasses.fields(Money)] == ["currency"]


def test_new_type_factories_build_columns() -> None:
    columns = (
        time(id="starts_at", source="starts_at"),
        duration(id="elapsed", source="elapsed"),
        link(id="website", source="website"),
        money(id="revenue", source="revenue", currency="USD"),
    )

    assert columns[0].semantic_type == Time()
    assert columns[1].semantic_type == Duration()
    assert columns[2].semantic_type == Link()
    assert columns[3].semantic_type == Money(currency="USD")


def test_money_factory_builds_default_type() -> None:
    assert money(id="amount", source="amount").semantic_type == Money()


@pytest.mark.parametrize("places", [True, 2.5, float("nan")])
def test_decimal_places_require_an_integer(places: object) -> None:
    with pytest.raises(TypeError, match="integer"):
        decimal_format(places=places)  # type: ignore[arg-type]


def test_semantic_type_base_is_abstract() -> None:
    with pytest.raises(TypeError, match="abstract"):
        SemanticType()


@pytest.mark.parametrize("currency", ["", "   "])
def test_money_rejects_empty_currency(currency: str) -> None:
    with pytest.raises(ValueError, match="Currency"):
        Money(currency=currency)
