#!/usr/bin/env bash
# Build the InvenTag executable as one directory with PyInstaller (plan 3.4).
#
#   build_binary.sh venv  <venv-dir> [python]
#       Create the build environment from the hash-pinned locks
#       (requirements-lock.txt, requirements-lock-build.txt). Wheels only.
#       This is the only step that needs the network.
#   build_binary.sh build <venv-dir> <work-dir> [--no-selftest]
#       PyInstaller, the licence check, the man page, the completions and the
#       archive dist/inventag-<version>-<os>-<arch>.tar.gz. No network.
#
# One-directory only: a one-file build is refused (architect decision 2,
# condition 3: lxml's modules stay separate, unmodified files). The version is
# read from inventag/_version.py; no version is written here.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

die() { echo "build_binary.sh: $*" >&2; exit 2; }

for arg in "$@"; do
  case "$arg" in
    --onefile|-F|--one-file)
      die "a one-file build is refused: build one directory (architect decision 2)" ;;
  esac
done

stage="${1:-}"; shift || true
case "$stage" in
  venv)
    venv="${1:?venv dir}"; py="${2:-python3}"
    "$py" -m venv --clear "$venv"
    "$venv/bin/python" -m pip install --no-cache-dir --disable-pip-version-check \
      --require-hashes --no-deps --only-binary :all: \
      -r "$ROOT/requirements-lock.txt" -r "$ROOT/requirements-lock-build.txt"
    "$venv/bin/python" -m pip check
    ;;
  build)
    venv="${1:?venv dir}"; work="${2:?work dir}"; shift 2
    selftest=1
    for arg in "$@"; do
      case "$arg" in
        --no-selftest) selftest=0 ;;
        *) die "unknown option $arg" ;;
      esac
    done
    [ -x "$venv/bin/python" ] || die "no build environment at $venv (run: build_binary.sh venv $venv)"
    py="$venv/bin/python"
    version="$("$py" -c 'import ast,sys; t=open(sys.argv[1]).read(); print(next(n.value.value for n in ast.parse(t).body if isinstance(n, ast.Assign) and n.targets[0].id == "__version__"))' "$ROOT/inventag/_version.py")"
    os_name="$(uname -s | tr '[:upper:]' '[:lower:]')"
    arch="$(uname -m)"; [ "$arch" = "aarch64" ] && arch=arm64
    export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git -C "$ROOT" log -1 --format=%ct 2>/dev/null || echo 0)}"
    export PYTHONHASHSEED=0
    mkdir -p "$work"
    dist="$work/dist"; bundle="$dist/inventag"; build="$work/build"
    rm -rf "$dist" "$build"

    ( cd "$ROOT" && "$py" -m PyInstaller --noconfirm --clean \
        --distpath "$dist" --workpath "$build" packaging/pyinstaller/inventag.spec )

    cp "$ROOT/LICENSE" "$bundle/LICENSE"
    "$py" "$ROOT/scripts/packaging/third_party_licenses.py" \
      --bundle "$bundle" --workpath "$build/inventag" \
      --out "$bundle/THIRD-PARTY-LICENSES.txt" \
      --components-json "$work/components.json"

    "$bundle/inventag" --version
    share="$bundle/share"
    mkdir -p "$share/man/man1" "$share/completions"
    "$py" "$ROOT/scripts/packaging/gen_manpage.py" --out "$share/man/man1/inventag.1"
    if [ "$selftest" = 1 ]; then
      "$bundle/inventag" selftest
      "$bundle/inventag" completion bash > "$share/completions/inventag.bash"
      "$bundle/inventag" completion zsh > "$share/completions/_inventag"
      "$bundle/inventag" completion fish > "$share/completions/inventag.fish"
    else
      echo "build_binary.sh: selftest and completions skipped (--no-selftest)" >&2
    fi

    name="inventag-${version}-${os_name}-${arch}"
    tar --sort=name --owner=0 --group=0 --numeric-owner --mtime="@$SOURCE_DATE_EPOCH" \
      -C "$dist" -cf - inventag | gzip -n -9 > "$work/$name.tar.gz"
    echo "archive: $work/$name.tar.gz"
    ;;
  *)
    die "usage: build_binary.sh venv <venv-dir> [python] | build <venv-dir> <work-dir> [--no-selftest]" ;;
esac
