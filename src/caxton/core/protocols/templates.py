from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from caxton.core.ir.base import DocumentIR
from caxton.core.models.templates import (
    TemplateCompilationResult,
    TemplateContext,
    TemplateSpecification,
)
from caxton.core.rendering import RenderContext, RendererDescriptor, RenderResult

from .rendering import OutputSink


@runtime_checkable
class TemplateInspector(Protocol):
    """Read-only adapter that discovers facts about one template source."""

    def inspect(self, template: TemplateSpecification) -> TemplateContext: ...


IR_contra = TypeVar("IR_contra", bound=DocumentIR, contravariant=True)


@runtime_checkable
class TemplateRenderer(Protocol[IR_contra]):
    """Renderer consuming a generic template compilation result."""

    descriptor: RendererDescriptor

    def render(
        self,
        compilation: TemplateCompilationResult[IR_contra],
        sink: OutputSink,
        context: RenderContext,
    ) -> RenderResult: ...


__all__ = ("TemplateInspector", "TemplateRenderer")
