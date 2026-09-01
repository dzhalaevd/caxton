from pathlib import Path

import pytest

from caxton import OutputError
from caxton._internal import sinks as sinks_module  # noqa: PLC2701


def test_cleanup_error_keeps_write_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_error = OSError("write failed")

    def fail_write(_target: object, _data: bytes) -> int:
        raise write_error

    def fail_cleanup(_sink: object, _staged: Path) -> None:
        message = "cleanup failed"
        raise OSError(message)

    monkeypatch.setattr(sinks_module, "_write_all", fail_write)
    monkeypatch.setattr(sinks_module.FileSink, "discard_staged", fail_cleanup)
    target = tmp_path / "report.xlsx"

    with pytest.raises(OutputError) as captured:
        sinks_module.FileSink(target).write(b"artifact")

    assert captured.value.context == {
        "exception_type": "OSError",
        "operation": "write",
        "target": str(target),
    }
    assert captured.value.__cause__ is write_error
