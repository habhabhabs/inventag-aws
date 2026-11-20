# PyInstaller spec: the InvenTag executable as one directory (dist/inventag/).
#
# Built by scripts/packaging/build_binary.sh, which runs PyInstaller with the
# repository root as the working directory and the hash-pinned locks installed.
# No version number here: the version is inventag/_version.py.
# -*- mode: python -*-
import os
import sys

from PyInstaller.utils.hooks import copy_metadata

HERE = os.path.abspath(SPECPATH)
ROOT = os.path.dirname(os.path.dirname(HERE))

# keyring finds its backends through entry points: the metadata must be inside.
datas = copy_metadata("keyring")

a = Analysis(
    [os.path.join(HERE, "entry.py")],
    pathex=[ROOT],
    datas=datas,
    hookspath=[os.path.join(HERE, "hooks")],
    # Left out on purpose:
    # - the Google output needs the "google" extra (install with pipx or uv);
    # - Pillow and Tk are not used;
    # - setuptools and its vendored modules come from the build environment,
    #   not from InvenTag's dependencies;
    # - readline, curses, dbm and crypt are not used by the CLI and their C
    #   libraries can be GPL or LGPL (architect decision 1, amendment 2).
    excludes=[
        "google",
        "googleapiclient",
        "google_auth_oauthlib",
        "PIL",
        "tkinter",
        "_tkinter",
        "test",
        "setuptools",
        "pkg_resources",
        "_distutils_hack",
        "readline",
        "curses",
        "_curses",
        "_curses_panel",
        "dbm",
        "_dbm",
        "_gdbm",
        "crypt",
        "_crypt",
    ],
    noarchive=False,
)

# macOS: PyInstaller thins, re-paths and re-signs every collected binary, so
# lxml's modules would no longer be the files of the hash-pinned wheel. They
# go in as data files at the same paths instead: COLLECT copies them unchanged
# (architect-package-dryrun-5.md ruling 1; decision 2, condition 2). This is
# done after Analysis, which would reclassify them as binaries again.
if sys.platform == "darwin":

    def _lxml_module(dest):
        parts = dest.replace(os.sep, "/").split("/")
        return parts[0] == "lxml" and parts[-1].endswith(".so")

    a.datas += [(d, s, "DATA") for d, s, _t in a.binaries if _lxml_module(d)]
    a.binaries = [e for e in a.binaries if not _lxml_module(e[0])]

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="inventag",
    console=True,
    strip=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="inventag", strip=False, upx=False)
