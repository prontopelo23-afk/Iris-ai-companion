#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-run}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="IRIS"
PROCESS_NAME="IRISNative"
APP_BUNDLE="/Applications/$APP_NAME.app"
APP_BINARY="$APP_BUNDLE/Contents/MacOS/$PROCESS_NAME"
BUILD_SCRIPT="$ROOT_DIR/native_shell/script/build_and_install.sh"
LOG_FILE="$HOME/Library/Logs/IRIS/launcher.log"

kill_existing() {
  pkill -x "$PROCESS_NAME" >/dev/null 2>&1 || true
  sleep 1
}

build_install() {
  "$BUILD_SCRIPT" --install
}

open_app() {
  /usr/bin/open -na "$APP_BUNDLE"
}

case "$MODE" in
  run)
    kill_existing
    build_install
    open_app
    ;;
  --debug|debug)
    kill_existing
    build_install
    lldb -- "$APP_BINARY"
    ;;
  --logs|logs)
    kill_existing
    build_install
    open_app
    sleep 2
    test -f "$LOG_FILE" && tail -n 80 -F "$LOG_FILE"
    ;;
  --telemetry|telemetry)
    kill_existing
    build_install
    open_app
    /usr/bin/log stream --info --style compact --predicate "process == \"$PROCESS_NAME\""
    ;;
  --verify|verify)
    kill_existing
    build_install
    open_app
    sleep 3
    pgrep -x "$PROCESS_NAME" >/dev/null
    if [ -f "$LOG_FILE" ]; then
      tail -n 20 "$LOG_FILE"
    fi
    ;;
  *)
    echo "usage: $0 [run|--debug|--logs|--telemetry|--verify]" >&2
    exit 2
    ;;
esac
