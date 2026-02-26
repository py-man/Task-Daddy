#!/usr/bin/env bash
set -euo pipefail

if [[ "${OSTYPE:-}" != darwin* ]]; then
  echo "This script must run on macOS with Xcode installed."
  exit 1
fi

WORKSPACE="ios/App/App.xcworkspace"
SCHEME="App"
ARCHIVE_PATH="build/App.xcarchive"

xcodebuild -workspace "$WORKSPACE" -scheme "$SCHEME" -configuration Release -archivePath "$ARCHIVE_PATH" archive -destination "generic/platform=iOS"
echo "Archive created at $ARCHIVE_PATH"

