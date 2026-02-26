#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8000}"
OUT_DIR="${OUT_DIR:-artifacts/nightly}"
mkdir -p "$OUT_DIR"

curl -sf "$API_BASE/openapi.json" >"$OUT_DIR/openapi.json"

python3 - "$OUT_DIR/openapi.json" "$OUT_DIR/api_contract_report.txt" <<'PY'
import json
import sys
from pathlib import Path

openapi_path = Path(sys.argv[1])
report_path = Path(sys.argv[2])
data = json.loads(openapi_path.read_text())
paths = set(data.get("paths", {}).keys())

required = {
    "/health",
    "/version",
    "/auth/login",
    "/auth/me",
    "/boards",
    "/admin/system-status",
    "/notifications/preferences",
    "/webhooks/events",
}
missing = sorted(required - paths)

lines = []
lines.append("API Contract Check")
lines.append("==================")
lines.append(f"paths_count={len(paths)}")
if missing:
    lines.append("status=FAILED")
    lines.append("missing_paths:")
    lines.extend([f"- {m}" for m in missing])
else:
    lines.append("status=PASS")
    lines.append("all required paths present")

report_path.write_text("\n".join(lines) + "\n")
print("\n".join(lines))
if missing:
    raise SystemExit(1)
PY
