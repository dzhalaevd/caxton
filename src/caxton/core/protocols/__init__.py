from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from .data import DataSource, DataSourceInfo, Repeatability, RowAccessor

if TYPE_CHECKING:
    from .rendering import (
        BinarySeekable,
        BinaryWritable,
        OutputSink,
        OutputTarget,
        Renderer,
    )
    from .templates import TemplateInspector, TemplateRenderer

_RENDERING_EXPORTS = frozenset(
    (
        "BinarySeekable",
        "BinaryWritable",
        "OutputSink",
        "OutputTarget",
        "Renderer",
    ),
)
_TEMPLATE_EXPORTS = frozenset(("TemplateInspector", "TemplateRenderer"))


def __getattr__(name: str) -> object:  # noqa: WPS413
    if name in _RENDERING_EXPORTS:
        rendering = importlib.import_module(f"{__name__}.rendering")
        return getattr(rendering, name)
    if name in _TEMPLATE_EXPORTS:
        templates = importlib.import_module(f"{__name__}.templates")
        return getattr(templates, name)
    if name not in _RENDERING_EXPORTS | _TEMPLATE_EXPORTS:
        message = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(message)
    raise AssertionError(name)


__all__ = (
    "BinarySeekable",
    "BinaryWritable",
    "DataSource",
    "DataSourceInfo",
    "OutputSink",
    "OutputTarget",
    "Renderer",
    "Repeatability",
    "RowAccessor",
    "TemplateInspector",
    "TemplateRenderer",
)
