from __future__ import annotations

import dataclasses
import enum
from collections.abc import Mapping
from types import MappingProxyType

from caxton.core.models.common import DocumentKind
from caxton.core.protocols.data import Repeatability

RENDERER_CONTRACT_VERSION = 1


class WorkbookOperation(enum.StrEnum):
    """How rendering obtains the workbook that will receive compiled content."""

    CREATE_NEW_WORKBOOK = "create_new_workbook"
    USE_EXISTING_TEMPLATE = "use_existing_template"


class ExecutionMode(enum.StrEnum):
    """Backend-neutral preference for how a renderer executes a render."""

    AUTO = "auto"
    STANDARD = "standard"
    STREAM = "stream"


@dataclasses.dataclass(frozen=True, slots=True)
class DataSourceRequirements:
    """Non-consuming execution facts about one table row source."""

    worksheet_index: int
    table_index: int
    repeatability: Repeatability = Repeatability.UNKNOWN
    row_count: int | None = None

    def __post_init__(self) -> None:
        if self.worksheet_index < 0 or self.table_index < 0:
            message = "Data source indexes cannot be negative"
            raise ValueError(message)
        if self.row_count is not None and self.row_count < 0:
            message = "Data source row count cannot be negative"
            raise ValueError(message)


@dataclasses.dataclass(frozen=True, slots=True)
class ExecutionRequirements:
    """Backend-neutral constraints used to choose an execution plan."""

    mode: ExecutionMode = ExecutionMode.AUTO
    data_sources: tuple[DataSourceRequirements, ...] = ()
    append_only: bool = False
    has_named_tables: bool = False
    requires_buffering: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", ExecutionMode(self.mode))
        object.__setattr__(self, "data_sources", tuple(self.data_sources))

    @property
    def requires_single_pass(self) -> bool:
        """Whether source metadata forbids an implicit second data pass."""
        return any(
            source.repeatability is not Repeatability.REITERABLE
            for source in self.data_sources
        )


@dataclasses.dataclass(frozen=True, slots=True)
class RequiredCapabilities:
    """Backend-independent requirements discovered from a semantic graph."""

    document_kind: DocumentKind
    ir_versions: frozenset[int]
    features: frozenset[str] = frozenset()
    workbook_operation: WorkbookOperation = WorkbookOperation.CREATE_NEW_WORKBOOK
    execution: ExecutionRequirements = ExecutionRequirements()

    def __post_init__(self) -> None:
        object.__setattr__(self, "ir_versions", frozenset(self.ir_versions))
        object.__setattr__(self, "features", frozenset(self.features))


@dataclasses.dataclass(frozen=True, slots=True)
class RendererCapabilities:
    """IR versions and semantic features supported by a renderer."""

    ir_versions: Mapping[DocumentKind, frozenset[int]]
    features: frozenset[str] = frozenset()
    workbook_operations: frozenset[WorkbookOperation] = frozenset(
        (WorkbookOperation.CREATE_NEW_WORKBOOK,),
    )
    execution_modes: frozenset[ExecutionMode] = frozenset(
        (ExecutionMode.STANDARD,),
    )

    def __post_init__(self) -> None:
        versions = {
            kind: frozenset(supported) for kind, supported in self.ir_versions.items()
        }
        object.__setattr__(self, "ir_versions", MappingProxyType(versions))
        object.__setattr__(self, "features", frozenset(self.features))
        object.__setattr__(
            self,
            "workbook_operations",
            frozenset(self.workbook_operations),
        )
        object.__setattr__(
            self,
            "execution_modes",
            frozenset(ExecutionMode(mode) for mode in self.execution_modes),
        )

    def supports(self, required: RequiredCapabilities) -> bool:
        """Return whether every required version and feature is compatible."""
        versions = self.ir_versions.get(required.document_kind, frozenset())
        requested_mode = required.execution.mode
        execution_supported = (
            requested_mode is ExecutionMode.AUTO
            or requested_mode in self.execution_modes
        )
        return (
            bool(versions & required.ir_versions)
            and required.features <= self.features
            and required.workbook_operation in self.workbook_operations
            and execution_supported
        )


@dataclasses.dataclass(frozen=True, slots=True)
class RendererDescriptor:
    """Stable metadata used before selecting and invoking a renderer."""

    name: str
    version: str
    formats: frozenset[str]
    mime_types: frozenset[str]
    extensions: frozenset[str]
    capabilities: RendererCapabilities
    contract_version: int = RENDERER_CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "formats",
            frozenset(item.lower() for item in self.formats),
        )
        object.__setattr__(self, "mime_types", frozenset(self.mime_types))
        object.__setattr__(
            self,
            "extensions",
            frozenset(_normalize_extension(item) for item in self.extensions),
        )


@dataclasses.dataclass(frozen=True, slots=True)
class RenderContext:
    """Resolved invocation settings passed to a renderer."""

    format: str
    backend: str
    execution: ExecutionRequirements = ExecutionRequirements()


@dataclasses.dataclass(frozen=True, slots=True)
class RenderResult:
    """Description of one completed rendering operation."""

    format: str
    mime_type: str
    renderer: str
    bytes_written: int
    data: bytes | None = None
    target: str | None = None
    execution_mode: ExecutionMode = ExecutionMode.STANDARD
    execution_plan: str | None = None

    @property
    def content(self) -> bytes | None:
        """Artifact bytes under the delivery-oriented public name."""
        return self.data


def _normalize_extension(value: str) -> str:
    lowered = value.lower()
    return lowered if lowered.startswith(".") else f".{lowered}"


__all__ = (
    "RENDERER_CONTRACT_VERSION",
    "DataSourceRequirements",
    "ExecutionMode",
    "ExecutionRequirements",
    "RenderContext",
    "RenderResult",
    "RendererCapabilities",
    "RendererDescriptor",
    "RequiredCapabilities",
    "WorkbookOperation",
)
