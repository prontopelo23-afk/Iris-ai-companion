#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PRODUCT="IRISNative"
APP_NAME="IRIS"
BUNDLE_ID="com.karmaswoop.iris"
DIST_DIR="$ROOT/dist"
APP_DIR="$DIST_DIR/$APP_NAME.app"
INSTALL_DIR="/Applications/$APP_NAME.app"
ICON_SOURCE="/Users/karmaswoop/Documents/Codex/2026-04-19-files-mentioned-by-the-user-iris/iris-app-icon.icns"

cd "$ROOT"
swift build -c release

BIN_PATH="$(find "$ROOT/.build" -type f -path "*/release/$PRODUCT" | head -n 1)"
if [ -z "$BIN_PATH" ]; then
  echo "Executable introuvable: $PRODUCT" >&2
  exit 1
fi

rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"
cp "$BIN_PATH" "$APP_DIR/Contents/MacOS/$PRODUCT"

if [ -f "$ICON_SOURCE" ]; then
  cp "$ICON_SOURCE" "$APP_DIR/Contents/Resources/IRIS.icns"
fi

cat > "$APP_DIR/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleDisplayName</key>
  <string>$APP_NAME</string>
  <key>CFBundleExecutable</key>
  <string>$PRODUCT</string>
  <key>CFBundleIconFile</key>
  <string>IRIS</string>
  <key>CFBundleIdentifier</key>
  <string>$BUNDLE_ID</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>$APP_NAME</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>13.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>NSMicrophoneUsageDescription</key>
  <string>IRIS utilise le micro pour permettre le pilotage vocal du cockpit local.</string>
  <key>NSSpeechRecognitionUsageDescription</key>
  <string>IRIS utilise la reconnaissance vocale pour transcrire les commandes opérateur.</string>
  <key>NSPrincipalClass</key>
  <string>NSApplication</string>
</dict>
</plist>
PLIST

touch "$APP_DIR/Contents/PkgInfo"
printf 'APPL????' > "$APP_DIR/Contents/PkgInfo"
codesign --force --deep --sign - "$APP_DIR" >/dev/null 2>&1 || true

echo "Staged app: $APP_DIR"
if [ "${1:-}" = "--install" ]; then
  rm -rf "$INSTALL_DIR"
  cp -R "$APP_DIR" "$INSTALL_DIR"
  codesign --force --deep --sign - "$INSTALL_DIR" >/dev/null 2>&1 || true
  echo "Installed app: $INSTALL_DIR"
fi
