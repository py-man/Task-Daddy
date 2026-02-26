# Task-Daddy iOS Shell

This folder contains a Capacitor wrapper so you can package Task-Daddy for iOS.

## Local setup

```bash
cd apps/ios-shell
npm ci --workspaces=false
npm run ios:add
npm run ios:sync
```

`ios:add` and `ios:sync` auto-generate `www/index.html` if missing.

## Live-server mode (recommended for internal testing)

```bash
cd apps/ios-shell
IOS_SHELL_LIVE_SERVER=1 IOS_SHELL_SERVER_URL=http://YOUR_SERVER_IP:3000 npm exec --workspaces=false -- cap sync ios
```

## Build archive + IPA on macOS

```bash
cd apps/ios-shell
bash scripts/build_ios_archive.sh
bash scripts/export_ipa.sh appstore
```

For ad-hoc export:

```bash
cd apps/ios-shell
bash scripts/export_ipa.sh adhoc
```

## One-shot signed IPA + TestFlight upload

Set your signing + upload credentials:

```bash
export IOS_TEAM_ID=YOUR_TEAM_ID
export IOS_BUNDLE_ID=com.yourcompany.neonlanes
export APPSTORE_API_KEY_ID=YOUR_API_KEY_ID
export APPSTORE_API_ISSUER_ID=YOUR_API_ISSUER_ID
```

Then run:

```bash
cd apps/ios-shell
bash scripts/build_and_upload_testflight.sh
```

If you prefer Apple ID upload:

```bash
export APPLE_ID=your-apple-id@example.com
export APP_SPECIFIC_PASSWORD=xxxx-xxxx-xxxx-xxxx
```
