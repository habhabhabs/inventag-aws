"""Write a report file so that a failure never leaves a partial file behind."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Callable, Union

from ..security.safe_output import precreate_private

PathLike = Union[str, "os.PathLike[str]"]


def plain_open_mode(near: PathLike) -> int:
    """Return the mode a plain ``open(path, "w")`` gives a new file in the
    folder of ``near`` (0666 minus the umask), without changing the umask.

    The process umask is never touched, not even for a moment: another thread
    that creates a file at that moment would get a wider mode. Where
    ``/proc/self/status`` has the umask it is read from there; elsewhere a
    probe file is created, measured and removed in that folder.
    """
    try:
        with open("/proc/self/status", encoding="ascii") as status:
            for line in status:
                if line.startswith("Umask:"):
                    return 0o666 & ~int(line.split()[1], 8)
    except (OSError, ValueError, IndexError):
        pass
    folder = Path(os.fspath(near)).parent
    probe = folder / f".{uuid.uuid4().hex[:8]}.mode"
    descriptor = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    try:
        return os.fstat(descriptor).st_mode & 0o777
    finally:
        os.close(descriptor)
        try:
            probe.unlink()
        except OSError:
            pass


def plain_open_mode_for(path: PathLike) -> int:
    """Return the mode ``path`` has after a plain ``open(path, "w")``: the
    mode of the existing file (open keeps it), else the mode of a new file
    (:func:`plain_open_mode`)."""
    try:
        return os.stat(os.fspath(path)).st_mode & 0o7777
    except FileNotFoundError:
        return plain_open_mode(path)


def save_atomically(path: PathLike, writer: Callable[[str], None]) -> str:
    """Call ``writer(temp_path)``, then move the result to ``path``.

    The temporary file is in the same folder (so the move is one step), is
    owner-only (0600) and is removed if ``writer`` or the move fails. A report
    that already exists at ``path`` stays as it was until the new one is
    complete. Returns ``path`` as text.
    """
    target = Path(os.fspath(path))
    temp = target.with_name(f".{target.name}.{uuid.uuid4().hex[:8]}.tmp")
    precreate_private(temp)
    try:
        writer(str(temp))
        os.replace(temp, target)
    except BaseException:
        try:
            temp.unlink()
        except OSError:
            pass
        raise
    return str(target)
