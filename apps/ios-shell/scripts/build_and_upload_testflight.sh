#!/usr/bin/env bash
set -euo pipefail

if [[ "${OSTYPE:-}" != darwin* ]]; then
  echo "This script must run on macOS with Xcode installed."
  exit 1
fi

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1"
    exit 1
  fi
}

require_cmd xcodebuild
require_cmd npm

WORKSPACE="${IOS_WORKSPACE:-ios/App/App.xcworkspace}"
SCHEME="${IOS_SCHEME:-App}"
CONFIGURATION="${IOS_CONFIGURATION:-Release}"
ARCHIVE_PATH="${IOS_ARCHIVE_PATH:-build/App.xcarchive}"
EXPORT_PATH="${IOS_EXPORT_PATH:-build/export/appstore}"
EXPORT_PLIST="${IOS_EXPORT_PLIST:-build/export/ExportOptions-generated.plist}"
TEAM_ID="${IOS_TEAM_ID:-}"
BUNDLE_ID="${IOS_BUNDLE_ID:-}"

if [[ -z "$TEAM_ID" ]]; then
  echo "Missing IOS_TEAM_ID. Example: export IOS_TEAM_ID=ABCDE12345"
  exit 1
fi

if [[ -z "$BUNDLE_ID" ]]; then
  echo "Missing IOS_BUNDLE_ID. Example: export IOS_BUNDLE_ID=com.example.neonlanes"
  exit 1
fi

echo "Preparing Capacitor web assets..."
npm run ios:sync

mkdir -p "$(dirname "$ARCHIVE_PATH")"
mkdir -p "$EXPORT_PATH"
mkdir -p "$(dirname "$EXPORT_PLIST")"

cat > "$EXPORT_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>method</key>
  <string>app-store-connect</string>
  <key>destination</key>
  <string>export</string>
  <key>signingStyle</key>
  <string>automatic</string>
  <key>teamID</key>
  <string>${TEAM_ID}</string>
  <key>stripSwiftSymbols</key>
  <true/>
  <key>compileBitcode</key>
  <false/>
</dict>
</plist>
EOF

echo "Building signed archive..."
xcodebuild \
  -workspace "$WORKSPACE" \
  -scheme "$SCHEME" \
  -configuration "$CONFIGURATION" \
  -archivePath "$ARCHIVE_PATH" \
  -destination "generic/platform=iOS" \
  -allowProvisioningUpdates \
  CODE_SIGN_STYLE=Automatic \
  DEVELOPMENT_TEAM="$TEAM_ID" \
  PRODUCT_BUNDLE_IDENTIFIER="$BUNDLE_ID" \
  archive

echo "Exporting signed IPA..."
xcodebuild \
  -exportArchive \
  -archivePath "$ARCHIVE_PATH" \
  -exportOptionsPlist "$EXPORT_PLIST" \
  -exportPath "$EXPORT_PATH" \
  -allowProvisioningUpdates

IPA_PATH="$(find "$EXPORT_PATH" -maxdepth 1 -name '*.ipa' | head -n 1)"
if [[ -z "$IPA_PATH" ]]; then
  echo "IPA export failed: no .ipa found in $EXPORT_PATH"
  exit 1
fi

echo "IPA ready: $IPA_PATH"

if [[ -n "${APPSTORE_API_KEY_ID:-}" && -n "${APPSTORE_API_ISSUER_ID:-}" ]]; then
  echo "Uploading to TestFlight with App Store Connect API key..."
  xcrun altool --upload-app --type ios --file "$IPA_PATH" --apiKey "$APPSTORE_API_KEY_ID" --apiIssuer "$APPSTORE_API_ISSUER_ID"
  echo "Upload submitted."
  exit 0
fi

if [[ -n "${APPLE_ID:-}" && -n "${APP_SPECIFIC_PASSWORD:-}" ]]; then
  echo "Uploading to TestFlight with Apple ID + app-specific password..."
  xcrun altool --upload-app --type ios --file "$IPA_PATH" --username "$APPLE_ID" --password "$APP_SPECIFIC_PASSWORD"
  echo "Upload submitted."
  exit 0
fi

echo "Upload skipped. Set either:"
echo "  APPSTORE_API_KEY_ID + APPSTORE_API_ISSUER_ID"
echo "or"
echo "  APPLE_ID + APP_SPECIFIC_PASSWORD"
