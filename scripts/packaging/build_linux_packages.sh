#!/usr/bin/env bash
# Build the .deb and .rpm of InvenTag with nfpm from the one-directory build
# of scripts/packaging/build_binary.sh (plan 3.4).
#
#   build_linux_packages.sh <work-dir> [deb|rpm ...]
#
# <work-dir> is the build_binary.sh work directory (it holds dist/inventag/).
# nfpm must be on PATH. The version is read from inventag/_version.py.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
work="${1:?work dir}"; shift
formats=("$@"); [ ${#formats[@]} -gt 0 ] || formats=(deb rpm)

[ -x "$work/dist/inventag/inventag" ] || { echo "no build in $work/dist/inventag" >&2; exit 2; }
for f in share/man/man1/inventag.1 share/completions/inventag.bash \
         share/completions/_inventag share/completions/inventag.fish; do
  [ -f "$work/dist/inventag/$f" ] || { echo "missing $f (build without --no-selftest)" >&2; exit 2; }
done

INVENTAG_VERSION="$(python3 -c 'import ast,sys; t=open(sys.argv[1]).read(); print(next(n.value.value for n in ast.parse(t).body if isinstance(n, ast.Assign) and n.targets[0].id == "__version__"))' "$ROOT/inventag/_version.py")"
case "$(uname -m)" in
  x86_64) NFPM_ARCH=amd64 ;;
  aarch64|arm64) NFPM_ARCH=arm64 ;;
  *) echo "unsupported CPU $(uname -m)" >&2; exit 2 ;;
esac
export INVENTAG_VERSION NFPM_ARCH
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git -C "$ROOT" log -1 --format=%ct 2>/dev/null || echo 0)}"

mkdir -p "$work/pkg"
gzip -n -9 -c "$work/dist/inventag/share/man/man1/inventag.1" > "$work/pkg/inventag.1.gz"
cd "$work"
for fmt in "${formats[@]}"; do
  nfpm package --config "$ROOT/packaging/nfpm/nfpm.yaml" --packager "$fmt" --target "$work/pkg/"
done
ls -l "$work/pkg"
