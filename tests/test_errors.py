import copy
import dataclasses
import pickle  # noqa: S403
from collections.abc import Callable
from typing import Any, cast

import pytest

from caxton import errors as public_errors
from caxton._internal.rendering import run_backend  # noqa: PLC2701
from caxton.errors import (
    BackendError,
    CaxtonError,
    CaxtonTypeError,
    CaxtonValueError,
    ColumnNotFoundError,
    CyclicReferenceError,
    DuplicateColumnError,
    InvalidOperationError,
    Issue,
    Notification,
    RenderError,
    SchemaError,
    ValidationError,
)


def _error_instance(error_type: type[CaxtonError]) -> CaxtonError:
    values = {
        "backend": "test",
        "column": "value",
        "context": {"details": {"columns": ["value"]}},
        "cycle": ("value", "value"),
        "field": "value",
        "issues": (Issue("nested", context={"items": [1]}),),
        "message": "boom",
        "path": "document.value",
        "row_index": 1,
        "row_type": "dict",
        "source_type": "iterator",
    }
    arguments = {
        field.name: values[field.name]
        for field in dataclasses.fields(error_type)
        if field.init and field.name in values
    }
    constructor = cast("Any", error_type)
    return cast("CaxtonError", constructor(**arguments))


def _public_error_types() -> tuple[type[CaxtonError], ...]:
    return tuple(
        exported
        for name in public_errors.__all__
        if isinstance(exported := getattr(public_errors, name), type)
        and issubclass(exported, CaxtonError)
    )


def _pickle_round_trip(error: CaxtonError) -> CaxtonError:
    restored = pickle.loads(pickle.dumps(error))  # noqa: S301
    assert isinstance(restored, CaxtonError)
    return restored


def test_error_hierarchy() -> None:
    assert issubclass(ColumnNotFoundError, SchemaError)
    assert issubclass(SchemaError, ValidationError)
    assert issubclass(ValidationError, CaxtonError)
    assert issubclass(RenderError, CaxtonError)
    assert issubclass(InvalidOperationError, CaxtonError)


def test_cyclic_reference_error_context() -> None:
    cycle = (
        'worksheet["Report"].table[0].column["left"].source',
        'worksheet["Report"].table[0].column["right"].source',
        'worksheet["Report"].table[0].column["left"].source',
    )

    error = CyclicReferenceError(
        column="left",
        cycle=cycle,
        path=cycle[0],
    )

    assert issubclass(CyclicReferenceError, SchemaError)
    assert (
        error.message == f"Cyclic reference through 2 columns, starting at {cycle[0]}"
    )
    assert error.context == {"column": "left", "cycle": cycle}


@pytest.mark.parametrize("cycle", [(), ("value",), ("left", "right")])
def test_cyclic_error_requires_closed_cycle(
    cycle: tuple[str, ...],
) -> None:
    with pytest.raises(ValueError, match="closed path"):
        CyclicReferenceError(column="value", cycle=cycle)


def test_argument_error_hierarchy() -> None:
    assert issubclass(CaxtonTypeError, CaxtonError)
    assert issubclass(CaxtonTypeError, TypeError)
    assert issubclass(CaxtonValueError, CaxtonError)
    assert issubclass(CaxtonValueError, ValueError)


def test_missing_column_context() -> None:
    path = 'report["Monthly Sales"].sheet["Sales"].column["revenue"]'

    error = ColumnNotFoundError(column="revenue", path=path)

    assert error.column == "revenue"
    assert error.path == path
    assert error.context == {"column": "revenue"}
    assert str(error) == (
        f"Column 'revenue' was not found\n\nPath:\n{path}"
        "\n\nContext:\n  column: 'revenue'"
    )


def test_notification_aggregates_issues() -> None:
    notification = Notification()
    notification.add(
        Issue("Sheet name cannot be empty", path="report.sheet[0]"),
    )
    notification.add(
        ColumnNotFoundError(
            column="salary",
            path='report.sheet[0].table[0].column["salary"]',
        ),
    )
    notification.add(
        DuplicateColumnError(
            column="name",
            path="report.sheet[0].table[0]",
        ),
    )

    with pytest.raises(ValidationError) as captured:
        notification.raise_if_errors("Report validation failed")

    error = captured.value
    assert isinstance(error.issues, tuple)
    assert len(error.issues) == 3
    assert "Report validation failed with 3 errors:" in str(error)
    assert "Column 'salary' was not found" in str(error)
    assert 'at report.sheet[0].table[0].column["salary"]' in str(error)


def test_notification_public_snapshot() -> None:
    notification = Notification()
    first = notification.add("first")
    snapshot = notification.issues
    second = notification.add("second")

    assert snapshot == (first,)
    assert notification.issues == (first, second)

    with pytest.raises(ValidationError) as captured:
        notification.raise_if_errors()

    assert captured.value.issues == (first, second)


@pytest.mark.parametrize(
    "error_class",
    [ColumnNotFoundError, CyclicReferenceError],
)
def test_notification_rejects_specialized_errors(
    error_class: type[ValidationError],
) -> None:
    notification = Notification()
    notification.add("invalid")

    with pytest.raises(CaxtonTypeError, match="accept message and issues"):
        notification.raise_if_errors(error_class=error_class)


def test_backend_exception_is_wrapped_and_chained() -> None:
    backend_error = RuntimeError("openpyxl failed")

    def fail() -> None:
        raise backend_error

    with pytest.raises(BackendError) as captured:
        run_backend(fail, message="Failed to render document", backend="openpyxl")

    error = captured.value
    assert error.__cause__ is backend_error
    assert error.backend == "openpyxl"
    assert error.context == {
        "backend": "openpyxl",
        "exception_type": "RuntimeError",
    }


def test_public_error_bypasses_backend_wrapper() -> None:
    operation_error = InvalidOperationError("Invalid document state")

    def fail() -> None:
        raise operation_error

    with pytest.raises(InvalidOperationError) as captured:
        run_backend(fail)

    assert captured.value is operation_error


def test_issue_context_is_an_immutable_snapshot() -> None:
    context = {"columns": ["name"]}
    issue = Issue("Invalid columns", context=context)
    context["columns"].append("email")

    assert issue.context == {"columns": ("name",)}
    with pytest.raises(TypeError):
        issue.context["other"] = True  # type: ignore[index]


def test_error_context_is_an_immutable_snapshot() -> None:
    context = {"columns": ["name"]}
    error = CaxtonError("Invalid columns", context=context)
    context["columns"].append("email")

    assert error.context == {"columns": ("name",)}
    with pytest.raises(TypeError):
        error.context["other"] = True  # type: ignore[index]


@pytest.mark.parametrize("error_type", _public_error_types())
@pytest.mark.parametrize(
    "round_trip",
    [copy.copy, copy.deepcopy, _pickle_round_trip],
)
def test_public_errors_support_copy_and_pickle(
    error_type: type[CaxtonError],
    round_trip: Callable[[CaxtonError], CaxtonError],
) -> None:
    original = _error_instance(error_type)

    restored = round_trip(original)

    assert restored.__class__ is error_type
    assert restored.args == original.args
    for field in dataclasses.fields(original):
        assert getattr(restored, field.name) == getattr(original, field.name)
    with pytest.raises(TypeError):
        restored.context["new"] = True  # type: ignore[index]
