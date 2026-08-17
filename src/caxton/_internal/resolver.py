from __future__ import annotations

from collections.abc import Callable, Sequence

from caxton.core.errors import RenderError, UnsupportedFeatureError
from caxton.core.ir import SpreadsheetIR
from caxton.core.protocols import Renderer, TemplateRenderer
from caxton.core.rendering import (
    RENDERER_CONTRACT_VERSION,
    RendererDescriptor,
    RequiredCapabilities,
    WorkbookOperation,
)

RendererOption = Renderer[SpreadsheetIR] | TemplateRenderer[SpreadsheetIR]


class BuiltinRendererResolver:
    """Select one compatible bundled or explicitly supplied renderer."""

    def __init__(
        self,
        renderers: Sequence[RendererOption] | None = None,
    ) -> None:
        self._renderers = tuple(renderers) if renderers is not None else None

    def select(
        self,
        required: RequiredCapabilities,
        *,
        format_name: str,
        backend: str | None = None,
        renderer: RendererOption | None = None,
    ) -> RendererOption:
        """Resolve and preflight one renderer before compilation.

        Returns:
            A compatible renderer adapter.

        Raises:
            RenderError: If no unambiguous compatible renderer exists.
        """
        if renderer is not None:
            _preflight(renderer, required, format_name)
            return renderer
        candidates = (
            _select_builtins(required, format_name=format_name, backend=backend)
            if self._renderers is None
            else _filter_renderers(
                self._renderers,
                format_name=format_name,
                backend=backend,
            )
        )
        if not candidates:
            message = f"No renderer is available for format {format_name!r}"
            raise RenderError(
                message,
                context={"backend": backend, "format": format_name},
            )
        if len(candidates) > 1:
            message = f"Renderer selection is ambiguous for format {format_name!r}"
            raise RenderError(
                message,
                context={
                    "candidates": [item.descriptor.name for item in candidates],
                    "format": format_name,
                },
            )
        selected = candidates[0]
        _preflight(selected, required, format_name)
        return selected


def _select_builtins(
    required: RequiredCapabilities,
    *,
    format_name: str,
    backend: str | None,
) -> tuple[RendererOption, ...]:
    if not _matches_xlsx(format_name):
        return ()
    selected_backend = backend or _DEFAULT_BACKENDS.get(required.workbook_operation)
    if selected_backend is None:
        return ()
    loader = _BUILTIN_LOADERS.get(
        (required.workbook_operation, selected_backend.lower()),
    )
    return () if loader is None else (loader(),)


def _filter_renderers(
    renderers: Sequence[RendererOption],
    *,
    format_name: str,
    backend: str | None,
) -> tuple[RendererOption, ...]:
    return tuple(
        candidate
        for candidate in renderers
        if _matches_format(candidate.descriptor, format_name)
        and (backend is None or candidate.descriptor.name.lower() == backend.lower())
    )


def _load_xlsxwriter() -> Renderer[SpreadsheetIR]:
    from caxton._internal.backends.xlsxwriter import (  # noqa: PLC0415
        XlsxWriterRenderer,
    )

    return XlsxWriterRenderer()


def _load_openpyxl() -> Renderer[SpreadsheetIR]:
    try:
        from caxton._internal.backends.openpyxl import (  # noqa: PLC0415
            OpenpyxlRenderer,
        )
    except ModuleNotFoundError as error:
        if error.name != "openpyxl":
            raise
        message = "OpenPyXL runtime dependency is unavailable"
        raise RenderError(
            message,
            context={
                "backend": "openpyxl",
                "recovery": "reinstall caxton",
            },
        ) from error
    return OpenpyxlRenderer()


def _load_openpyxl_template() -> TemplateRenderer[SpreadsheetIR]:
    try:
        from caxton._internal.backends.openpyxl import (  # noqa: PLC0415
            OpenpyxlTemplateRenderer,
        )
    except ModuleNotFoundError as error:
        if error.name != "openpyxl":
            raise
        message = "OpenPyXL runtime dependency is unavailable"
        raise RenderError(message, context={"backend": "openpyxl-template"}) from error
    return OpenpyxlTemplateRenderer()


_DEFAULT_BACKENDS = {
    WorkbookOperation.CREATE_NEW_WORKBOOK: "xlsxwriter",
    WorkbookOperation.USE_EXISTING_TEMPLATE: "openpyxl-template",
}
_BUILTIN_LOADERS: dict[
    tuple[WorkbookOperation, str],
    Callable[[], RendererOption],
] = {
    (WorkbookOperation.CREATE_NEW_WORKBOOK, "xlsxwriter"): _load_xlsxwriter,
    # Transitional explicit create-new compatibility adapter. Template
    # rendering uses the separate loader below.
    (WorkbookOperation.CREATE_NEW_WORKBOOK, "openpyxl"): _load_openpyxl,
    (
        WorkbookOperation.USE_EXISTING_TEMPLATE,
        "openpyxl-template",
    ): _load_openpyxl_template,
}


def _preflight(
    renderer: RendererOption,
    required: RequiredCapabilities,
    format_name: str,
) -> None:
    descriptor = renderer.descriptor
    if descriptor.contract_version != RENDERER_CONTRACT_VERSION:
        message = "Renderer contract version is incompatible"
        raise UnsupportedFeatureError(
            message,
            context={
                "renderer": descriptor.name,
                "renderer_contract": descriptor.contract_version,
                "required_contract": RENDERER_CONTRACT_VERSION,
            },
        )
    if not _matches_format(descriptor, format_name):
        message = f"Renderer {descriptor.name!r} does not support {format_name!r}"
        raise UnsupportedFeatureError(message)
    if not descriptor.capabilities.supports(required):
        supported = descriptor.capabilities.features
        message = f"Renderer {descriptor.name!r} lacks required capabilities"
        raise UnsupportedFeatureError(
            message,
            context={
                "missing_features": sorted(required.features - supported),
                "renderer": descriptor.name,
                "required_execution_mode": required.execution.mode.value,
                "required_workbook_operation": required.workbook_operation.value,
            },
        )


def canonical_format_name(
    renderer: RendererOption,
    format_hint: str,
) -> str:
    """Resolve a format, MIME type, or extension to one logical format.

    Returns:
        The renderer's canonical logical format name.

    Raises:
        RenderError: If a non-logical hint maps to multiple formats.
    """
    descriptor = renderer.descriptor
    normalized = format_hint.lower()
    if normalized in descriptor.formats:
        return normalized
    if _matches_format(descriptor, normalized) and len(descriptor.formats) == 1:
        return next(iter(descriptor.formats))
    message = f"Format hint {format_hint!r} is ambiguous for {descriptor.name!r}"
    raise RenderError(
        message,
        context={
            "formats": sorted(descriptor.formats),
            "renderer": descriptor.name,
        },
    )


def _matches_xlsx(format_hint: str) -> bool:
    normalized = format_hint.lower()
    return normalized in {
        "xlsx",
        ".xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }


def _matches_format(
    descriptor: RendererDescriptor,
    format_hint: str,
) -> bool:
    normalized = format_hint.lower()
    extension = normalized if normalized.startswith(".") else f".{normalized}"
    return (
        normalized in descriptor.formats
        or normalized in descriptor.mime_types
        or extension in descriptor.extensions
    )


__all__ = ("BuiltinRendererResolver", "canonical_format_name")
