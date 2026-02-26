from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from time import monotonic


@dataclass
class RequestSample:
  ts: datetime
  status_code: int
  latency_ms: float


class RuntimeMetrics:
  def __init__(self) -> None:
    self._started_monotonic = monotonic()
    self._started_at = datetime.now(timezone.utc)
    self._samples: deque[RequestSample] = deque()
    self._lock = Lock()

  @property
  def started_at(self) -> datetime:
    return self._started_at

  def uptime_seconds(self) -> int:
    return max(0, int(monotonic() - self._started_monotonic))

  def observe_request(self, status_code: int, latency_ms: float) -> None:
    now = datetime.now(timezone.utc)
    with self._lock:
      self._samples.append(RequestSample(ts=now, status_code=status_code, latency_ms=latency_ms))
      self._prune_locked(now)

  def _prune_locked(self, now: datetime) -> None:
    cutoff = now - timedelta(hours=24)
    while self._samples and self._samples[0].ts < cutoff:
      self._samples.popleft()

  def snapshot(self) -> dict:
    now = datetime.now(timezone.utc)
    with self._lock:
      self._prune_locked(now)
      samples = list(self._samples)

    def window_stats(minutes: int) -> tuple[int, int]:
      cutoff = now - timedelta(minutes=minutes)
      total = 0
      errors = 0
      for sample in samples:
        if sample.ts < cutoff:
          continue
        total += 1
        if sample.status_code >= 500:
          errors += 1
      return total, errors

    total_15, errors_15 = window_stats(15)
    total_24h = len(samples)
    errors_24h = sum(1 for s in samples if s.status_code >= 500)

    p95_ms = 0.0
    if samples:
      sorted_latencies = sorted(s.latency_ms for s in samples)
      idx = max(0, int(len(sorted_latencies) * 0.95) - 1)
      p95_ms = sorted_latencies[idx]

    return {
      "uptimeSeconds": self.uptime_seconds(),
      "p95LatencyMs24h": round(p95_ms, 2),
      "requestCount15m": total_15,
      "requestCount24h": total_24h,
      "errorCount15m": errors_15,
      "errorCount24h": errors_24h,
      "errorRate15m": round((errors_15 / total_15) * 100, 2) if total_15 else 0.0,
      "errorRate24h": round((errors_24h / total_24h) * 100, 2) if total_24h else 0.0,
    }


runtime_metrics = RuntimeMetrics()
