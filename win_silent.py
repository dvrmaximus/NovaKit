"""Helpers Windows : lancer des process sans fenêtre noire."""

from __future__ import annotations

import ctypes
import subprocess
import sys
from typing import Sequence

CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200

if sys.platform == "win32":
    CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def _startupinfo():
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    return si


def _flags() -> dict:
    if sys.platform != "win32":
        return {}
    return {
        "creationflags": CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
        "startupinfo": _startupinfo(),
    }


def run_silent(args: Sequence[str], **kwargs) -> subprocess.CompletedProcess:
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("timeout", 15)
    for k, v in _flags().items():
        kwargs.setdefault(k, v)
    if sys.platform == "win32":
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | CREATE_NO_WINDOW
    return subprocess.run(list(args), **kwargs)


def popen_silent(args, **kwargs) -> subprocess.Popen:
    for k, v in _flags().items():
        kwargs.setdefault(k, v)
    if sys.platform == "win32":
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | CREATE_NO_WINDOW
    return subprocess.Popen(args, **kwargs)


def shell_open(target: str, params: str | None = None, show: int = 1) -> bool:
    """Ouvre un fichier / app / URL via ShellExecute — aucune console."""
    if sys.platform != "win32":
        return False
    rc = ctypes.windll.shell32.ShellExecuteW(
        None, "open", target, params, None, show
    )
    return int(rc) > 32


def patch_subprocess_no_window() -> None:
    """Force CREATE_NO_WINDOW sur tous les Popen (ex. pyngrok)."""
    if sys.platform != "win32":
        return
    if getattr(subprocess, "_astat_silent_patched", False):
        return
    _orig = subprocess.Popen

    class SilentPopen(_orig):  # type: ignore[valid-type,misc]
        def __init__(self, *args, **kwargs):
            kwargs["creationflags"] = kwargs.get("creationflags", 0) | CREATE_NO_WINDOW
            if "startupinfo" not in kwargs:
                kwargs["startupinfo"] = _startupinfo()
            super().__init__(*args, **kwargs)

    subprocess.Popen = SilentPopen  # type: ignore[misc,assignment]
    subprocess._astat_silent_patched = True
