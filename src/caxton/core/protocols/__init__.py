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

_RENDERING_EXPORTS = frozenset(
    (
        "BinarySeekable",
        "BinaryWritable",
        "OutputSink",
        "OutputTarget",
        "Renderer",
    ),
)


def __getattr__(name: str) -> object:  # noqa: WPS413
    if name not in _RENDERING_EXPORTS:
        message = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(message)
    rendering = importlib.import_module(f"{__name__}.rendering")
    return getattr(rendering, name)


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
)
