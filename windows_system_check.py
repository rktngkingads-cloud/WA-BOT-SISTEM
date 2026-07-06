from __future__ import annotations

import tempfile

_original_temporary_directory = tempfile.TemporaryDirectory


def _windows_safe_temporary_directory(*args, **kwargs):
    kwargs.setdefault("ignore_cleanup_errors", True)
    return _original_temporary_directory(*args, **kwargs)


tempfile.TemporaryDirectory = _windows_safe_temporary_directory

import system_check


if __name__ == "__main__":
    raise SystemExit(system_check.main())
