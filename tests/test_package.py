import inspect
import typing
from collections.abc import Callable, Iterator
from types import ModuleType, NoneType

import caxton
from caxton import errors as public_errors, testing as testing_api
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


def test_presentation_value_types_are_closed() -> None:
    value_types = (
        formatting.AutoWidth,
        formatting.BorderLine,
        formatting.Borders,
        formatting.CellAlignment,
        formatting.CustomFormat,
        formatting.DateFormat,
        formatting.DecimalFormat,
        formatting.DocumentTheme,
        formatting.FillStyle,
        formatting.FontStyle,
        formatting.MoneyFormat,
        formatting.PercentageFormat,
        formatting.Style,
        formatting.StyleSheet,
        formatting.TimeFormat,
    )

    assert "CorporateTheme" not in caxton.__all__
    assert "CorporateTheme" not in formatting.__all__
    assert all(getattr(value_type, "__final__", False) for value_type in value_types)


def test_error_namespaces_export_all_symbols() -> None:
    assert set(core_errors.__all__) <= set(public_errors.__all__)
    assert set(core_errors.__all__) <= set(caxton.__all__)
    for name in core_errors.__all__:
        assert getattr(public_errors, name) is getattr(core_errors, name)
        assert getattr(caxton, name) is getattr(core_errors, name)


def test_public_annotations_resolve_at_runtime() -> None:
    failures = {}
    for qualified_name, target in _public_annotation_targets():
        try:
            typing.get_type_hints(inspect.unwrap(target))
        except NameError as error:  # noqa: PERF203
            failures[qualified_name] = str(error)

    assert failures == {}


def _factory_return_types() -> Iterator[tuple[str, str]]:
    for name in caxton.__all__:
        exported = getattr(caxton, name)
        if not inspect.isfunction(exported):
            continue
        annotation = typing.get_type_hints(exported).get("return")
        for returned in _named_types(annotation):
            yield name, returned


def _named_types(annotation: object) -> Iterator[str]:
    if annotation is None or annotation is NoneType or annotation is typing.Any:
        return
    if inspect.isclass(annotation):
        yield annotation.__name__
        return
    for argument in typing.get_args(annotation):
        yield from _named_types(argument)


def test_factory_return_types_are_public() -> None:
    exported = set(caxton.__all__)

    missing = {
        f"{factory}() -> {returned}"
        for factory, returned in _factory_return_types()
        if returned not in exported
    }

    assert missing == set()
