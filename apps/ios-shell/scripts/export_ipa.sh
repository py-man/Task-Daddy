#!/usr/bin/env bash
set -euo pipefail

if [[ "${OSTYPE:-}" != darwin* ]]; then
  echo "This script must run on macOS with Xcode installed."
  exit 1
fi

MODE="${1:-appstore}"
if [[ "$MODE" != "appstore" && "$MODE" != "adhoc" ]]; then
  echo "Usage: $0 [appstore|adhoc]"
  exit 1
fi

ARCHIVE_PATH="build/App.xcarchive"
EXPORT_PATH="build/export/${MODE}"
PLIST_PATH="export-options/ExportOptions-${MODE}.plist"

mkdir -p "$EXPORT_PATH"
xcodebuild -exportArchive -archivePath "$ARCHIVE_PATH" -exportOptionsPlist "$PLIST_PATH" -exportPath "$EXPORT_PATH"
echo "IPA exported to $EXPORT_PATH"
