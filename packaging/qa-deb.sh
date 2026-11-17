#!/usr/bin/env bash
# Runtime QA for a built esword4linux .deb in the current graphical session.
#
# This is intentionally separate from packaging/build-deb.sh: a package build
# does not prove X11/Wayland compatibility. The script extracts the .deb to a
# temporary root, launches the *installed* launcher with ESWORD4LINUX_ROOT, and
# records what was actually observed.
#
# Usage:
#   packaging/qa-deb.sh dist/deb/esword4linux_0.5.0-1_amd64.deb [MODULES_DIR]
#
# X11 requires DISPLAY. Wayland requires WAYLAND_DISPLAY; without a compositor
# the script only verifies that the Wayland plugin and its ELF closure load.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEB="${1:-}"
MODULES="${2:-}"

if [ -z "$DEB" ] || [ ! -f "$DEB" ]; then
    echo "usage: $0 <package.deb> [MODULES_DIR]" >&2
    exit 2
fi
DEB="$(cd "$(dirname "$DEB")" && pwd)/$(basename "$DEB")"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/esword4linux-qa.XXXXXX")"
PID=""
cleanup() {
    [ -n "$PID" ] && kill "$PID" 2>/dev/null || true
    rm -rf "$WORK"
}
trap cleanup EXIT

ulimit -c 0 || true

echo "==> Extracting $DEB"
dpkg-deb -x "$DEB" "$WORK/root"
LAUNCHER="$WORK/root/usr/bin/esword4linux"
RUNTIME="$WORK/root/opt/esword4linux"
[ -x "$LAUNCHER" ] || { echo "missing launcher" >&2; exit 1; }
[ -d "$RUNTIME" ] || { echo "missing private runtime" >&2; exit 1; }

mkdir -p "$WORK/home" "$WORK/config/esword4linux" "$WORK/cache" "$WORK/modules"
if [ -n "$MODULES" ]; then
    MODULES="$(cd "$MODULES" && pwd)"
else
    MODULES="$WORK/modules"
fi

cat > "$WORK/config/esword4linux/settings.json" <<EOF
{"resources_dir": "$MODULES", "cache_dir": "$WORK/cache/esword4linux", "locale": "en"}
EOF

BEFORE="$(find "$MODULES" -type f -printf '%P %s %T@\n' 2>/dev/null | sort | sha256sum)"

export HOME="$WORK/home"
export XDG_CONFIG_HOME="$WORK/config"
export XDG_CACHE_HOME="$WORK/cache"
export ESWORD4LINUX_ROOT="$RUNTIME"
export QT_DEBUG_PLUGINS=1

run_x11() {
    if [ -z "${DISPLAY:-}" ]; then
        echo "X11: SKIP (DISPLAY unset)"
        return
    fi
    echo "==> X11 launch"
    QT_QPA_PLATFORM=xcb "$LAUNCHER" > "$WORK/x11.out" 2> "$WORK/x11.err" &
    PID=$!
    sleep 5
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "X11: FAIL (process exited)"
        tail -30 "$WORK/x11.err" >&2
        return 1
    fi
    if command -v wmctrl >/dev/null 2>&1; then
        if wmctrl -l | grep -qi esword4linux; then
            echo "X11: window present"
        else
            echo "X11: WARN (wmctrl did not list an esword4linux window)"
        fi
    fi
    grep -Fq 'platforms/libqxcb.so" loaded library' "$WORK/x11.err" || {
        echo "X11: FAIL (xcb plugin not loaded)"; return 1;
    }
    if grep -q 'not found' "$WORK/x11.err"; then
        echo "X11: FAIL (unresolved library)"; return 1
    fi
    kill "$PID" 2>/dev/null || true
    wait "$PID" 2>/dev/null || true
    PID=""
    echo "X11: PASS (xcb loaded, process stayed alive)"
}

run_wayland() {
    if [ -z "${WAYLAND_DISPLAY:-}" ]; then
        echo "Wayland: SKIP (WAYLAND_DISPLAY unset; no compositor)"
        # Plugin-load diagnostic only, not a full-session pass.
        QT_QPA_PLATFORM=wayland WAYLAND_DISPLAY=esword4linux-no-compositor \
            timeout 8 "$LAUNCHER" > "$WORK/wl.out" 2> "$WORK/wl.err" &
        WPID=$!
        wait "$WPID" 2>/dev/null || true
        if grep -Fq 'platforms/libqwayland.so" loaded library' "$WORK/wl.err"; then
            echo "Wayland: plugin loaded, ELF closure OK; session NOT validated"
        else
            echo "Wayland: FAIL (plugin did not load)"
            tail -20 "$WORK/wl.err" >&2
            return 1
        fi
        return 0
    fi
    echo "==> Wayland launch"
    QT_QPA_PLATFORM=wayland "$LAUNCHER" > "$WORK/wl.out" 2> "$WORK/wl.err" &
    PID=$!
    sleep 5
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "Wayland: FAIL (process exited)"
        tail -30 "$WORK/wl.err" >&2
        return 1
    fi
    grep -Fq 'platforms/libqwayland.so" loaded library' "$WORK/wl.err" || {
        echo "Wayland: FAIL (wayland plugin not loaded)"; return 1;
    }
    kill "$PID" 2>/dev/null || true
    wait "$PID" 2>/dev/null || true
    PID=""
    echo "Wayland: PASS (wayland plugin loaded, process stayed alive)"
}

run_x11
run_wayland

echo "==> User data and module folder checks"
[ -f "$WORK/cache/esword4linux/catalog.db" ] || {
    echo "FAIL: catalog was not created in XDG_CACHE_HOME"; exit 1;
}
AFTER="$(find "$MODULES" -type f -printf '%P %s %T@\n' 2>/dev/null | sort | sha256sum)"
[ "$BEFORE" = "$AFTER" ] || { echo "FAIL: modules folder changed"; exit 1; }
echo "modules folder unchanged; XDG cache created"

echo
echo "QA observations (never infer more than this):"
echo "  host: $(. /etc/os-release 2>/dev/null; echo "${PRETTY_NAME:-unknown}")"
echo "  session: XDG_SESSION_TYPE=${XDG_SESSION_TYPE:-unset} DISPLAY=${DISPLAY:-unset} WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-unset}"
