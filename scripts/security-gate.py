#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def read_json(path: Path):
  if not path.exists():
    return None
  try:
    return json.loads(path.read_text())
  except Exception:
    return None


def npm_counts(data) -> dict[str, int]:
  counts = {"critical": 0, "high": 0, "moderate": 0, "low": 0}
  if not isinstance(data, dict):
    return counts
  vulns = data.get("metadata", {}).get("vulnerabilities")
  if isinstance(vulns, dict):
    for level in counts.keys():
      counts[level] = int(vulns.get(level, 0) or 0)
    return counts
  # older shapes
  advisories = data.get("advisories", {})
  if isinstance(advisories, dict):
    for adv in advisories.values():
      sev = str(adv.get("severity", "")).lower()
      if sev in counts:
        counts[sev] += 1
  return counts


def pip_counts(data) -> dict[str, int]:
  counts = {"critical": 0, "high": 0, "moderate": 0, "low": 0}
  if not isinstance(data, dict):
    return counts
  vulns = data.get("vulnerabilities")
  if isinstance(vulns, list):
    for vuln in vulns:
      sev = str(vuln.get("severity", "")).lower()
      if sev in ("medium",):
        sev = "moderate"
      if sev in counts:
        counts[sev] += 1
  dependencies = data.get("dependencies")
  if isinstance(dependencies, list):
    for dep in dependencies:
      for vuln in dep.get("vulns", []) or []:
        sev = str(vuln.get("severity", "")).lower()
        if sev in ("medium",):
          sev = "moderate"
        if sev in counts:
          counts[sev] += 1
  return counts


def main() -> int:
  npm_path = Path(os.environ.get("NPM_AUDIT_JSON", "artifacts_npm_audit.json"))
  pip_path = Path(os.environ.get("PIP_AUDIT_JSON", "artifacts_pip_audit.json"))
  allow_high = os.environ.get("SECURITY_GATE_ALLOW_HIGH", "0") == "1"

  npm = npm_counts(read_json(npm_path))
  pip = pip_counts(read_json(pip_path))
  combined = {k: npm[k] + pip[k] for k in npm.keys()}

  print("Security Gate Summary")
  print("=====================")
  print(f"npm: {npm}")
  print(f"pip: {pip}")
  print(f"combined: {combined}")

  if combined["critical"] > 0:
    print("FAIL: critical vulnerabilities detected")
    return 1
  if not allow_high and combined["high"] > 0:
    print("FAIL: high vulnerabilities detected (set SECURITY_GATE_ALLOW_HIGH=1 to allow)")
    return 1
  print("PASS")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
