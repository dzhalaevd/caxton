from collections.abc import Callable
from typing import TypeVar

from formata.core.errors import BackendError, FormataError

ResultT = TypeVar("ResultT")


def run_backend(
    operation: Callable[[], ResultT],
    *,
    message: str = "Backend operation failed",
    backend: str | None = None,
    path: str | None = None,
) -> ResultT:
    """Run a backend call and translate implementation-specific exceptions.

    Returns:
        The value returned by the backend operation.

    Raises:
        FormataError: If the operation already raised a public formata error.
        BackendError: If the operation raised an implementation-specific error.
    """
    try:
        return operation()
    except FormataError:
        raise
    except Exception as error:
        raise BackendError(
            message,
            backend=backend,
            path=path,
            context={"exception_type": type(error).__name__},
        ) from error
