import inspect
import typing
from collections.abc import Callable, Iterator
from types import ModuleType

import caxton
from caxton import testing as testing_api
from caxton.core import (
    errors as core_errors,
    formatting,
    ir,
    models,
    protocols,
    rendering,
    types,
)
from caxton.testing import strategies as testing_strategies

AnnotationTarget = Callable[..., object]

_PUBLIC_MODULES = (
    caxton,
    core_errors,
    formatting,
    ir,
    models,
    protocols,
    rendering,
    types,
    testing_api,
    testing_strategies,
)


def _annotated_exports(
    module: ModuleType,
) -> Iterator[tuple[str, AnnotationTarget]]:
    for name in module.__all__:
        exported = getattr(module, name)
        if callable(exported) and getattr(exported, "__annotations__", None):
            yield f"{module.__name__}.{name}", exported


def _annotated_public_members(
    qualified_name: str,
    exported: type[object],
) -> Iterator[tuple[str, AnnotationTarget]]:
    for name, descriptor in exported.__dict__.items():
        if name.startswith("_") and name != "__call__":
            continue
        member = _annotation_target(descriptor)
        if callable(member) and getattr(member, "__annotations__", None):
            yield f"{qualified_name}.{name}", member


def _annotation_target(descriptor: object) -> object | None:
    if isinstance(descriptor, (classmethod, staticmethod)):
        return descriptor.__func__
    if isinstance(descriptor, property):
        return descriptor.fget
    return descriptor


def _public_annotation_targets() -> Iterator[tuple[str, AnnotationTarget]]:
    seen: set[int] = set()
    for module in _PUBLIC_MODULES:
        for qualified_name, exported in _annotated_exports(module):
            if id(exported) not in seen:
                seen.add(id(exported))
                yield qualified_name, exported
                if inspect.isclass(exported):
                    yield from _annotated_public_members(qualified_name, exported)


def test_package_can_be_imported() -> None:
    assert caxton is not None


def test_public_annotations_resolve_at_runtime() -> None:
    failures = {}
    for qualified_name, target in _public_annotation_targets():
        try:
            typing.get_type_hints(inspect.unwrap(target))
        except NameError as error:
            failures[qualified_name] = str(error)

    assert failures == {}
