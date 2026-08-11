import datetime as dt
import decimal
import json

import pytest

from formata import sheet, spreadsheet, table, text
from formata.testing import (
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
        '    "$type": "Difference",\n'
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
        sheet("Data", table([], text("value"), name="data")),
        metadata={"stage": "test"},
    )
    second = spreadsheet(
        sheet("Data", table([], text("value"), name="data")),
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


def test_snapshot_rejects_runtime_objects() -> None:
    with pytest.raises(TypeError, match="Unsupported snapshot value: object"):
        canonical_snapshot(object())


def test_snapshot_rejects_recursive_containers() -> None:
    recursive: list[object] = []
    recursive.append(recursive)

    with pytest.raises(ValueError, match="recursive containers"):
        canonical_snapshot(recursive)
