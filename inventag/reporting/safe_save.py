"""Write a report file so that a failure never leaves a partial file behind."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Callable, Union

from ..security.safe_output import precreate_private

PathLike = Union[str, "os.PathLike[str]"]


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
