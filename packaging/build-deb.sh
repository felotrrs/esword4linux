#!/usr/bin/env bash
# Build the native Debian package for esword4linux.
#
# The script validates the source tree, prepares a pinned wheelhouse, runs the
# standard dpkg-buildpackage/debhelper workflow, runs package integrity checks
# and prints a build report. It never modifies .venv or the system Python
# environment.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${ESWORD4LINUX_PYTHON:-/usr/bin/python3}"
WHEELHOUSE="${ESWORD4LINUX_WHEELHOUSE:-${ROOT}/.build/wheelhouse}"
OUTDIR="${ROOT}/dist/deb"
OFFLINE=0
RUN_LINTIAN=1
SKIP_QA=0

usage() {
    cat <<'EOF'
Usage: packaging/build-deb.sh [options]

Options:
  --offline         Do not download wheels; use the existing wheelhouse.
  --wheelhouse DIR  Use DIR for the pinned wheels (default .build/wheelhouse).
  --no-lintian      Skip lintian.
  --skip-qa         Skip package extraction checks (not recommended).
  -h, --help        Show this help.
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --offline) OFFLINE=1 ;;
        --wheelhouse) WHEELHOUSE="${2:?missing directory}"; shift ;;
        --no-lintian) RUN_LINTIAN=0 ;;
        --skip-qa) SKIP_QA=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "build-deb: unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

die() {
    echo "build-deb: error: $*" >&2
    exit 1
}

need() {
    command -v "$1" >/dev/null 2>&1 || die "required tool not found: $1"
}

section() {
    echo
    echo "==> $*"
}

section "Validating source tree"
[ -f pyproject.toml ] || die "run from the repository root (pyproject.toml missing)"
[ -f debian/changelog ] || die "debian/changelog missing"
[ -f src/esword4linux/__init__.py ] || die "application source missing"
[ -f packaging/runtime-requirements.txt ] || die "runtime requirements missing"
[ -f packaging/runtime-manifest.yaml ] || die "runtime manifest missing"
[ -f packaging/esword4linux.launcher ] || die "launcher missing"

APP_VERSION="$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' src/esword4linux/__init__.py | head -n1)"
DEB_VERSION="$(dpkg-parsechangelog -SVersion)"
DEB_UPSTREAM="${DEB_VERSION%-*}"
[ "$APP_VERSION" = "$DEB_UPSTREAM" ] || \
    die "application version $APP_VERSION does not match Debian upstream version $DEB_UPSTREAM"
echo "application: $APP_VERSION (Debian $DEB_VERSION)"

DEB_ARCH="$(dpkg-architecture -qDEB_HOST_ARCH)"
[ "$DEB_ARCH" = "amd64" ] || \
    die "this package currently supports amd64 only (host: $DEB_ARCH)"

if command -v git >/dev/null 2>&1; then
    if git ls-files | grep -Eiq '\.(bblx|bbli|cmtx|cmti|dctx|dcti|lexi|lexx|refx|refi|topx|devx|harx|mapx|twm)$'; then
        die "an e-Sword module is tracked by git; refusing to package it"
    fi
    if ! git diff --quiet -- src packaging debian docs pyproject.toml 2>/dev/null; then
        echo "note: the working tree has uncommitted packaging/application changes"
    fi
fi

section "Checking build tools"
need dpkg-buildpackage
need dpkg-deb
need dpkg-parsechangelog
need dpkg-shlibdeps
need dh
need fakeroot
need "$PYTHON"
if [ "$RUN_LINTIAN" -eq 1 ]; then
    command -v lintian >/dev/null 2>&1 || echo "warning: lintian not installed; skipping"
fi

section "Preparing pinned wheelhouse"
mkdir -p "$WHEELHOUSE"
if [ "$OFFLINE" -eq 1 ]; then
    echo "offline mode: using $WHEELHOUSE"
else
    "$PYTHON" -m pip --version >/dev/null 2>&1 || \
        die "python3-pip is required to download the pinned wheels"
    "$PYTHON" -m pip download \
        --disable-pip-version-check \
        --no-deps \
        --only-binary=:all: \
        --require-hashes \
        --dest "$WHEELHOUSE" \
        -r packaging/runtime-requirements.txt
fi
WHEEL_COUNT="$(find "$WHEELHOUSE" -maxdepth 1 -name '*.whl' | wc -l)"
[ "$WHEEL_COUNT" -ge 3 ] || die "wheelhouse must contain the three pinned wheels"

section "Cleaning previous build products"
rm -rf .build/runtime debian/esword4linux debian/.debhelper build "$OUTDIR"
rm -f debian/files debian/debhelper-build-stamp debian/*.substvars
mkdir -p "$ROOT/.build" "$OUTDIR"

if [ -z "${SOURCE_DATE_EPOCH:-}" ]; then
    SOURCE_DATE_EPOCH="$(date -u -d "$(dpkg-parsechangelog -SDate)" +%s)"
fi
export SOURCE_DATE_EPOCH
export ESWORD4LINUX_WHEELHOUSE="$WHEELHOUSE"
echo "SOURCE_DATE_EPOCH=$SOURCE_DATE_EPOCH"

section "Building package with dpkg-buildpackage"
LOG="$ROOT/.build/dpkg-buildpackage.log"
set +e
dpkg-buildpackage -b -us -uc 2>&1 | tee "$LOG"
STATUS=${PIPESTATUS[0]}
set -e
[ "$STATUS" -eq 0 ] || die "dpkg-buildpackage failed (see $LOG)"

ARCH="$DEB_ARCH"
DEB_SRC="$(ls -1t "${ROOT}/../esword4linux_${DEB_VERSION}_${ARCH}.deb" 2>/dev/null | head -n1 || true)"
[ -n "$DEB_SRC" ] || DEB_SRC="$(ls -1t "${ROOT}/../esword4linux_"*".deb" 2>/dev/null | head -n1 || true)"
[ -n "$DEB_SRC" ] || die "could not locate the generated .deb"
DEB="${OUTDIR}/$(basename "$DEB_SRC")"
mv -f "$DEB_SRC" "$DEB"
for extra in "${ROOT}/../esword4linux_${DEB_VERSION}_${ARCH}.buildinfo" \
             "${ROOT}/../esword4linux_${DEB_VERSION}_${ARCH}.changes"; do
    [ -f "$extra" ] && mv -f "$extra" "$OUTDIR/"
done

section "Package integrity checks"
dpkg-deb --info "$DEB" > "$ROOT/.build/dpkg-deb-info.txt"
dpkg-deb --contents "$DEB" > "$ROOT/.build/dpkg-deb-contents.txt"
dpkg-deb --field "$DEB" Depends > "$ROOT/.build/dpkg-deb-depends.txt"

for required in \
    ./usr/bin/esword4linux \
    ./usr/share/applications/esword4linux.desktop \
    ./usr/share/icons/hicolor/512x512/apps/esword4linux.png \
    ./usr/share/doc/esword4linux/copyright \
    ./usr/share/doc/esword4linux/licenses/GPL-3.0-only.txt \
    ./opt/esword4linux/app/esword4linux/app.py \
    ./opt/esword4linux/python/PySide6/QtCore.abi3.so \
    ./opt/esword4linux/python/PySide6/Qt/plugins/platforms/libqxcb.so \
    ./opt/esword4linux/python/PySide6/Qt/plugins/platforms/libqwayland.so; do
    grep -Fq " $required" "$ROOT/.build/dpkg-deb-contents.txt" || \
        die "package is missing $required"
done

if grep -Eq '(__pycache__|\.pyc$|site-packages|/\.venv|\.whl$)' "$ROOT/.build/dpkg-deb-contents.txt"; then
    die "package contains a development/build artifact"
fi
if grep -Eiq '\.(bblx|bbli|cmtx|cmti|dctx|dcti|lexi|lexx|refx|refi|topx|devx|harx|mapx|twm)$' "$ROOT/.build/dpkg-deb-contents.txt"; then
    die "package contains an e-Sword module"
fi
if grep -Eq '/opt/esword4linux/python/yaml/(_yaml|cyaml)' "$ROOT/.build/dpkg-deb-contents.txt"; then
    die "compiled PyYAML artifacts must not be shipped"
fi
if grep -Eq 'libqt6|qt6-' "$ROOT/.build/dpkg-deb-depends.txt"; then
    die "package depends on a distribution Qt package; private Qt must be self-contained"
fi

if [ "$SKIP_QA" -eq 0 ]; then
    rm -rf "$ROOT/.build/extract"
    mkdir -p "$ROOT/.build/extract"
    dpkg-deb -x "$DEB" "$ROOT/.build/extract"
    "$PYTHON" -B packaging/validate_runtime.py \
        --root "$ROOT/.build/extract/opt/esword4linux"
fi

LINTIAN_STATUS="not run"
if [ "$RUN_LINTIAN" -eq 1 ] && command -v lintian >/dev/null 2>&1; then
    set +e
    lintian --fail-on error "$DEB" > "$ROOT/.build/lintian.txt" 2>&1
    LINTIAN_STATUS=$?
    set -e
    if [ "$LINTIAN_STATUS" -ne 0 ]; then
        cat "$ROOT/.build/lintian.txt" >&2
        die "lintian reported an error"
    fi
    echo "lintian: $(grep -c '^[WE]:' "$ROOT/.build/lintian.txt" || true) tag(s), no errors"
fi

if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate packaging/esword4linux.desktop || \
        die "desktop-file-validate failed"
fi

section "Build report"
DEB_SIZE="$(du -h "$DEB" | cut -f1)"
{
    echo "esword4linux Debian package"
    echo "  version:       $DEB_VERSION"
    echo "  architecture:  $ARCH"
    echo "  package:       $DEB"
    echo "  size:          $DEB_SIZE"
    echo "  sha256:        $(sha256sum "$DEB" | cut -d' ' -f1)"
    echo
    echo "Depends:"
    sed 's/^/  /' "$ROOT/.build/dpkg-deb-depends.txt"
    echo
    echo "Installed size:"
    dpkg-deb --info "$DEB" | sed -n 's/^ Installed-Size: /  /p'
    echo
    echo "Lintian: $LINTIAN_STATUS"
    echo "Logs: .build/dpkg-buildpackage.log, .build/dpkg-deb-contents.txt, .build/lintian.txt"
} | tee "$ROOT/.build/REPORT.txt"

echo
echo "Built: $DEB"
echo "Install with: sudo apt install ./$(basename "$DEB")"
