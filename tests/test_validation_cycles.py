"""Focused contracts for the shared structural cycle detector."""

from collections.abc import Iterable, Mapping

from caxton._internal.validation.cycles import (  # noqa: PLC2701
    report_reference_cycles,
)
from caxton.core.errors import Issue, Notification


def _report(
    dependencies: Mapping[str, Iterable[str]],
) -> tuple[Issue, ...]:
    nodes = set(dependencies)
    nodes.update(
        dependency for children in dependencies.values() for dependency in children
    )
    notification = Notification()
    report_reference_cycles(
        dependencies,
        paths={node: f'column["{node}"]' for node in nodes},
        columns={node: node for node in nodes},
        notification=notification,
    )
    return notification.issues


def test_self_loop_reports_closed_path() -> None:
    issues = _report({"value": ("value",)})

    assert len(issues) == 1
    assert issues[0].code == "CyclicReferenceError"
    assert issues[0].context == {
        "column": "value",
        "cycle": ('column["value"]', 'column["value"]'),
    }


def test_repeated_self_reference_reports_once() -> None:
    issues = _report({"value": ("value", "value")})

    assert len(issues) == 1
    assert issues[0].code == "CyclicReferenceError"
    assert issues[0].context == {
        "column": "value",
        "cycle": ('column["value"]', 'column["value"]'),
    }


def test_repeated_dependency_keeps_cycles() -> None:
    issues = _report(
        {
            "first": ("second", "second", "third"),
            "second": ("first",),
            "third": ("first",),
        },
    )

    assert len(issues) == 2
    assert {issue.context["cycle"] for issue in issues} == {
        ('column["first"]', 'column["second"]', 'column["first"]'),
        ('column["first"]', 'column["third"]', 'column["first"]'),
    }


def test_independent_cycles_report_two_issues() -> None:
    issues = _report(
        {
            "first": ("second",),
            "second": ("first",),
            "third": ("fourth",),
            "fourth": ("third",),
        },
    )

    assert len(issues) == 2
    assert {issue.context["column"] for issue in issues} == {"first", "third"}


def test_target_only_node_is_not_a_cycle() -> None:
    assert _report({"source": ("target",)}) == ()


def test_long_cycle_does_not_use_python_recursion() -> None:
    size = 2_000
    dependencies = {str(index): (str(index + 1),) for index in range(size - 1)}
    dependencies[str(size - 1)] = ("0",)

    issues = _report(dependencies)

    assert len(issues) == 1
    assert len(issues[0].context["cycle"]) == size + 1
