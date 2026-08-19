from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Mapping
from typing import Any, Self

from caxton.core._values import freeze_mapping

from .base import CaxtonError


@dataclasses.dataclass(frozen=True, slots=True)
class Issue:
    """One validation problem with machine-readable context."""

    message: str
    path: str | None = None
    code: str | None = None
    context: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "context",
            freeze_mapping(self.context, label="Issue context"),
        )

    @classmethod
    def from_error(cls, error: ValidationError) -> Self:
        """Create an issue while preserving a validation error's context.

        Returns:
            An issue containing the error message, path, and context.
        """
        return cls(
            message=error.message,
            path=error.path,
            code=type(error).__name__,
            context=error.context,
        )

    def __str__(self) -> str:
        if self.path is None:
            return self.message
        return f"{self.message}\n   at {self.path}"


@dataclasses.dataclass(eq=False)
class ValidationError(CaxtonError):
    """Raised for one or more errors in a semantic document model."""

    message: str = "Document validation failed"
    issues: tuple[Issue, ...] = dataclasses.field(default_factory=tuple, kw_only=True)

    def __post_init__(self) -> None:
        self.issues = tuple(self.issues)
        super().__post_init__()

    def __str__(self) -> str:
        if not self.issues:
            return super().__str__()

        count = len(self.issues)
        suffix = "error" if count == 1 else "errors"
        rendered_issues = "\n\n".join(
            f"{index}. {issue}" for index, issue in enumerate(self.issues, start=1)
        )

        return f"{self.message} with {count} {suffix}:\n\n{rendered_issues}"


@dataclasses.dataclass(eq=False)
class SchemaError(ValidationError):
    """Raised when a document schema is invalid."""


@dataclasses.dataclass(eq=False)
class ColumnNotFoundError(SchemaError):
    """Raised when a referenced column does not exist."""

    message: str = dataclasses.field(init=False)
    column: str = dataclasses.field(kw_only=True)

    def __post_init__(self) -> None:
        self.message = f"Column {self.column!r} was not found"
        self.context = {**self.context, "column": self.column}
        super().__post_init__()


@dataclasses.dataclass(eq=False)
class DuplicateColumnError(SchemaError):
    """Raised when a schema contains the same column more than once."""

    message: str = dataclasses.field(init=False)
    column: str = dataclasses.field(kw_only=True)

    def __post_init__(self) -> None:
        self.message = f"Duplicate column {self.column!r}"
        self.context = {**self.context, "column": self.column}
        super().__post_init__()


@dataclasses.dataclass(eq=False)
class ShapeError(ValidationError):
    """Raised when data dimensions do not match the document schema."""


@dataclasses.dataclass(slots=True)
class Notification:
    """Collect validation issues and raise them as one error."""

    _issues: list[Issue] = dataclasses.field(
        default_factory=list,
        init=False,
        repr=False,
    )

    @property
    def issues(self) -> tuple[Issue, ...]:
        """Collected issues as an immutable snapshot."""
        return tuple(self._issues)

    @property
    def has_errors(self) -> bool:
        """Whether at least one issue has been collected."""
        return bool(self._issues)

    def add(
        self,
        issue: Issue | ValidationError | str,
        *,
        path: str | None = None,
        code: str | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> Issue:
        """Add an issue, validation error, or plain validation message.

        Returns:
            The normalized issue added to this notification.
        """
        normalized: Issue
        if isinstance(issue, ValidationError):
            normalized = Issue.from_error(issue)
        elif isinstance(issue, Issue):
            normalized = issue
        else:
            normalized = Issue(
                message=issue,
                path=path,
                code=code,
                context=dict(context or {}),
            )
        self._issues.append(normalized)
        return normalized

    def extend(self, issues: Iterable[Issue | ValidationError]) -> None:
        """Add several issues while preserving their order."""
        for issue in issues:
            self.add(issue)

    def raise_if_errors(
        self,
        message: str = "Document validation failed",
    ) -> None:
        """Raise one aggregate error when validation found any issues.

        Raises:
            ValidationError: If at least one issue has been collected.
        """
        if self._issues:
            raise ValidationError(message, issues=tuple(self._issues))
