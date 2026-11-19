#!/usr/bin/env python3
"""A small stand-in for rsync, for `run_gitlab_examples_locally.py` on a host without rsync.

gitlab-ci-local (4.77.1) runs `rsync` to copy the project into a job's own folder
(`--shell-isolation`) and to copy the artifacts out. This file does that copy and
nothing else. It is NOT rsync: it understands only the options gitlab-ci-local
passes (-a, -r, -R, --delete, --delete-excluded, --exclude, --exclude-from,
--files-from) and the form `SRC DST`; any other option is ignored.

Set RSYNC_STAND_IN_LOG to a file name to log each call and each copied file.
"""

import fnmatch
import os
import shlex
import shutil
import sys
from typing import List, Optional


def _is_excluded(path: str, excludes: List[str]) -> bool:
    p = path[2:] if path.startswith("./") else path
    p = "" if p == "." else p
    for pattern in excludes:
        e = pattern.strip("'").strip("/")
        if fnmatch.fnmatch(p, e) or p == e or p.startswith(e + "/"):
            return True
    return False


def _read_lines(name: str) -> List[str]:
    with open(name) as handle:
        return [x.strip() for x in handle if x.strip()]


def run(args: List[str]) -> List[str]:
    """Do the copy that `rsync ARGS` would; return the relative paths copied."""
    excludes: List[str] = []
    files_from: Optional[List[str]] = None
    relative = False
    positional: List[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--exclude":
            excludes.append(args[i + 1])
            i += 2
            continue
        if a.startswith("--exclude="):
            excludes.append(a.split("=", 1)[1])
        elif a.startswith("--exclude-from="):
            excludes += _read_lines(a.split("=", 1)[1])
        elif a.startswith("--files-from="):
            files_from = _read_lines(a.split("=", 1)[1])
        elif a.startswith("--"):
            pass
        elif a.startswith("-"):
            relative = relative or "R" in a
        else:
            positional.append(a)
        i += 1
    if len(positional) < 2:
        raise SystemExit("rsync stand-in: needs SRC and DST")
    src, dst = positional[0], positional[-1]
    copied: List[str] = []

    def copy_tree(rel_path: str, base: str) -> None:
        full = os.path.join(base, rel_path)
        if _is_excluded(rel_path, excludes):
            return
        if os.path.isdir(full) and not os.path.islink(full):
            for name in sorted(os.listdir(full)):
                copy_tree(os.path.normpath(os.path.join(rel_path, name)), base)
        elif os.path.exists(full):
            out = os.path.join(dst, rel_path)
            os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
            shutil.copy2(full, out)
            copied.append(rel_path)

    if files_from is not None:
        for name in files_from:
            copy_tree(os.path.normpath(name), src)
    elif relative:
        for s in positional[:-1]:
            copy_tree(os.path.normpath(s), ".")
    else:
        copy_tree(".", src)
    return copied


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    copied = run(args)
    log = os.environ.get("RSYNC_STAND_IN_LOG")
    if log:
        with open(log, "a") as handle:
            handle.write("rsync-stand-in " + " ".join(shlex.quote(a) for a in args))
            handle.write("\n")
            for name in copied:
                handle.write(f"  copied {name}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
