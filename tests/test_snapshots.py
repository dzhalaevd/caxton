import dataclasses
import datetime as dt
import decimal
import json

import pytest

from caxton import sheet, spreadsheet, table, text
from caxton.testing import (
    SNAPSHOT_SCHEMA,
    Difference,
    DifferenceKind,
    canonical_snapshot,
    inspect_spec,
)


def test_snapshot_has_versioned_canonical_json() -> None:
    difference = Difference(
        path="worksheet['Data']",
        kind=DifferenceKind.MISSING,
        expected="Data",
        actual=None,
    )

    assert canonical_snapshot(difference) == (
        "{\n"
        f'  "$schema": "{SNAPSHOT_SCHEMA}",\n'
        '  "value": {\n'
        '    "$type": "caxton.testing._diff.Difference",\n'
        '    "actual": null,\n'
        '    "expected": "Data",\n'
        '    "kind": "missing",\n'
        '    "path": "worksheet[\'Data\']"\n'
        "  }\n"
        "}\n"
    )


def test_snapshot_normalizes_unordered_values() -> None:
    first = {"mapping": {"b": 2, "a": 1}, "values": {3, 1, 2}}
    second = {"values": {2, 3, 1}, "mapping": {"a": 1, "b": 2}}

    assert canonical_snapshot(first) == canonical_snapshot(second)


def test_semantic_snapshot_is_repeatable() -> None:
    first = spreadsheet(
        sheet(
            "Data",
            table(source=[], columns=(text(id="value", source="value"),), name="data"),
        ),
        metadata={"stage": "test"},
    )
    second = spreadsheet(
        sheet(
            "Data",
            table(source=[], columns=(text(id="value", source="value"),), name="data"),
        ),
        metadata={"stage": "test"},
    )

    assert canonical_snapshot(inspect_spec(first)) == canonical_snapshot(
        inspect_spec(second),
    )


def test_snapshot_encodes_non_json_scalars() -> None:
    snapshot = canonical_snapshot(
        {
            "bytes": b"xlsx",
            "date": dt.date(2026, 8, 11),
            "decimal": decimal.Decimal("1.20"),
        },
    )

    assert json.loads(snapshot)["value"] == {
        "bytes": {"$bytes": "eGxzeA=="},
        "date": {"$date": "2026-08-11"},
        "decimal": {"$decimal": "1.20"},
    }


def test_snapshot_tags_do_not_collide_with_keys() -> None:
    tagged = canonical_snapshot(b"xlsx")
    mapping = canonical_snapshot({"$bytes": "eGxzeA=="})

    assert tagged != mapping
    assert json.loads(mapping)["value"] == {"$$bytes": "eGxzeA=="}


def test_snapshot_uses_qualified_dataclass_names() -> None:
    first_type = dataclasses.make_dataclass(
        "Box",
        (("value", int),),
        frozen=True,
    )
    first_type.__module__ = "first_module"
    second_type = dataclasses.make_dataclass(
        "Box",
        (("value", int),),
        frozen=True,
    )
    second_type.__module__ = "second_module"

    assert canonical_snapshot(first_type(1)) != canonical_snapshot(second_type(1))


def test_snapshot_rejects_runtime_objects() -> None:
    with pytest.raises(TypeError, match="Unsupported snapshot value: object"):
        canonical_snapshot(object())


def test_snapshot_rejects_recursive_containers() -> None:
    recursive: list[object] = []
    recursive.append(recursive)

    with pytest.raises(ValueError, match="recursive containers"):
        canonical_snapshot(recursive)
