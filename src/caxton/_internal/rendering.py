from collections.abc import Callable
from typing import TypeVar

from caxton.core.errors import BackendError, CaxtonError

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
        CaxtonError: If the operation already raised a public caxton error.
        BackendError: If the operation raised an implementation-specific error.
    """
    try:
        return operation()
    except CaxtonError:
        raise
    except Exception as error:
        raise BackendError(
            message,
            backend=backend,
            path=path,
            context={"exception_type": type(error).__name__},
        ) from error
