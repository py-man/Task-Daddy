#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_json(path: Path, default: Any) -> Any:
  try:
    return json.loads(path.read_text())
  except Exception:
    return default


def _npm_counts(data: Any) -> dict[str, int]:
  out = {"critical": 0, "high": 0, "moderate": 0, "low": 0}
  if not isinstance(data, dict):
    return out
  meta = data.get("metadata", {}).get("vulnerabilities")
  if isinstance(meta, dict):
    for k in out:
      out[k] = int(meta.get(k, 0) or 0)
  return out


def _pip_counts(data: Any) -> dict[str, int]:
  out = {"critical": 0, "high": 0, "moderate": 0, "low": 0}
  if not isinstance(data, dict):
    return out
  deps = data.get("dependencies")
  if isinstance(deps, list):
    for dep in deps:
      for vuln in dep.get("vulns", []) or []:
        sev = str(vuln.get("severity", "")).lower()
        if sev == "medium":
          sev = "moderate"
        if sev in out:
          out[sev] += 1
  vulns = data.get("vulnerabilities")
  if isinstance(vulns, list):
    for vuln in vulns:
      sev = str(vuln.get("severity", "")).lower()
      if sev == "medium":
        sev = "moderate"
      if sev in out:
        out[sev] += 1
  return out


def _semgrep_count(data: Any) -> int:
  if not isinstance(data, dict):
    return 0
  results = data.get("results")
  if isinstance(results, list):
    return len(results)
  return 0


def _find(base: Path, name: str) -> Path | None:
  for p in base.rglob(name):
    if p.is_file():
      return p
  return None


def main() -> int:
  parser = argparse.ArgumentParser(description="Build consolidated nightly report from collected artifacts")
  parser.add_argument("--input-dir", default="artifacts/collected")
  parser.add_argument("--output-dir", default="artifacts/nightly")
  args = parser.parse_args()

  input_dir = Path(args.input_dir)
  output_dir = Path(args.output_dir)
  output_dir.mkdir(parents=True, exist_ok=True)

  npm_path = _find(input_dir, "npm_audit.json")
  pip_path = _find(input_dir, "pip_audit.json")
  semgrep_path = _find(input_dir, "semgrep.json")
  status_path = _find(input_dir, "system_status.json")
  perf_path = _find(input_dir, "perf.txt")
  db_path = _find(input_dir, "db_report.txt")
  sarif_path = _find(input_dir, "security.sarif")

  npm = _npm_counts(_read_json(npm_path, {}) if npm_path else {})
  pip = _pip_counts(_read_json(pip_path, {}) if pip_path else {})
  semgrep_count = _semgrep_count(_read_json(semgrep_path, {}) if semgrep_path else {})
  system_status = _read_json(status_path, {}) if status_path else {}
  generated_at = datetime.now(timezone.utc).isoformat()

  findings = {
    "timestamp": generated_at,
    "pipeline": "nightly",
    "security": {
      "npm": npm,
      "pip": pip,
      "semgrepFindings": semgrep_count,
    },
    "artifacts": {
      "systemStatus": str(status_path) if status_path else "",
      "perf": str(perf_path) if perf_path else "",
      "db": str(db_path) if db_path else "",
      "sarif": str(sarif_path) if sarif_path else "",
    },
  }
  (output_dir / "findings.json").write_text(json.dumps(findings, indent=2))

  api_state = "unknown"
  sections = system_status.get("sections") if isinstance(system_status, dict) else None
  if isinstance(sections, list):
    api = next((s for s in sections if isinstance(s, dict) and s.get("key") == "api"), None)
    if isinstance(api, dict):
      api_state = str(api.get("state") or "unknown")

  report = [
    "# Task-Daddy Nightly Health Report",
    f"- timestamp: {generated_at}",
    "- pipeline: nightly",
    "",
    "## Security Summary",
    f"- npm vulnerabilities: {npm}",
    f"- pip vulnerabilities: {pip}",
    f"- semgrep findings: {semgrep_count}",
    "",
    "## System Summary",
    f"- api status: {api_state}",
    f"- system status snapshot: `{status_path}`" if status_path else "- system status snapshot: unavailable",
    f"- db report: `{db_path}`" if db_path else "- db report: unavailable",
    f"- perf report: `{perf_path}`" if perf_path else "- perf report: unavailable",
    "",
    "## Artifacts",
    "- findings.json",
    "- security.sarif",
    "- db_report.txt",
    "- perf.html/perf.txt",
  ]
  (output_dir / "nightly_report.md").write_text("\n".join(report) + "\n")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
