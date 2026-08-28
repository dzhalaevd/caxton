"""Find and report cycles in structural reference dependency graphs."""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Iterator, Mapping
from typing import TypeVar

from caxton.core.errors import CyclicReferenceError, Notification

_Node = TypeVar("_Node", bound=Hashable)


def report_reference_cycles(
    dependencies: Mapping[_Node, Iterable[_Node]],
    paths: Mapping[_Node, str],
    columns: Mapping[_Node, str],
    notification: Notification,
) -> None:
    """Add one issue per detected back edge.

    Every cyclic graph produces an issue, but overlapping cycles can produce a
    representative cycle instead of every simple cycle.
    """
    for cycle in _dependency_cycles(dependencies):
        cycle_path = tuple(paths[node] for node in cycle)
        notification.add(
            CyclicReferenceError(
                column=columns[cycle[0]],
                cycle=cycle_path,
                path=cycle_path[0],
            ),
        )


def _dependency_cycles(
    dependencies: Mapping[_Node, Iterable[_Node]],
) -> Iterator[tuple[_Node, ...]]:
    completed: set[_Node] = set()
    for root in dependencies:
        if root in completed:
            continue
        yield from _cycles_from(root, dependencies, completed)


def _cycles_from(
    root: _Node,
    dependencies: Mapping[_Node, Iterable[_Node]],
    completed: set[_Node],
) -> Iterator[tuple[_Node, ...]]:
    path = [root]
    active = {root: 0}
    pending = [(root, _unique(dependencies.get(root, ())))]
    while pending:
        node, children = pending[-1]
        try:
            dependency = next(children)
        except StopIteration:
            pending.pop()
            path.pop()
            active.pop(node)
            completed.add(node)
            continue
        if dependency in completed:
            continue
        cycle_start = active.get(dependency)
        if cycle_start is not None:
            yield *path[cycle_start:], dependency
            continue
        active[dependency] = len(path)
        path.append(dependency)
        pending.append((dependency, _unique(dependencies.get(dependency, ()))))


def _unique(dependencies: Iterable[_Node]) -> Iterator[_Node]:
    """Yield each dependency once so a repeated reference reports one cycle."""
    seen: set[_Node] = set()
    for dependency in dependencies:
        if dependency in seen:
            continue
        seen.add(dependency)
        yield dependency


__all__ = ("report_reference_cycles",)
