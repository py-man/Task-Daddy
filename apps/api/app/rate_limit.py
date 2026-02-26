from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock


@dataclass
class _Bucket:
  reset_at: float
  count: int


class RateLimiter:
  """
  Tiny in-memory fixed-window rate limiter.

  Notes:
  - Good enough for single-process MVP.
  - For multi-replica deployments, replace with Redis-backed limiter.
  """

  def __init__(self) -> None:
    self._lock = Lock()
    self._buckets: dict[str, _Bucket] = {}

  def hit(self, key: str, *, limit: int, window_seconds: int) -> tuple[bool, int]:
    """
    Returns (allowed, retry_after_seconds).
    """
    now = time.time()
    with self._lock:
      b = self._buckets.get(key)
      if b is None or now >= b.reset_at:
        self._buckets[key] = _Bucket(reset_at=now + window_seconds, count=1)
        return True, 0
      if b.count >= limit:
        retry = max(1, int(b.reset_at - now))
        return False, retry
      b.count += 1
      return True, 0

  def reset_prefix(self, prefix: str) -> None:
    with self._lock:
      for k in list(self._buckets.keys()):
        if k.startswith(prefix):
          del self._buckets[k]


limiter = RateLimiter()

