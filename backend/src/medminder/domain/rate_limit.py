"""In-process login rate-limiting (Phase 10 hardening, ADR-0018).

Pure, dependency-free sliding-window counters.  No Redis/DB: the app runs
as a single instance (ADR-0017), so a process-local limiter is sufficient;
state is lost on restart, which is acceptable (brute force is also bounded
by Argon2 cost and the generic-failure response).  The clock is injected
(``now`` in monotonic seconds) so the logic is unit-testable without sleeps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

__all__ = ["LoginRateLimiter", "SlidingWindowLimiter"]


@dataclass
class SlidingWindowLimiter:
    """Per-key sliding-window failure counter.

    A key is *blocked* once it accrues ``max_attempts`` hits inside the
    trailing ``window_seconds``.  Eviction is lazy (expired hits are pruned
    on access) with an opportunistic full sweep when the key count exceeds
    ``max_keys`` — bounding memory against a hostile key-spray.
    """

    max_attempts: int
    window_seconds: float
    max_keys: int = 10_000
    _hits: dict[str, list[float]] = field(default_factory=dict)

    def _active(self, key: str, now: float) -> list[float]:
        """Return (and store back) the still-in-window hits for ``key``."""
        cutoff = now - self.window_seconds
        hits = [t for t in self._hits.get(key, []) if t > cutoff]
        if hits:
            self._hits[key] = hits
        else:
            self._hits.pop(key, None)
        return hits

    def _maybe_sweep(self, now: float) -> None:
        if len(self._hits) <= self.max_keys:
            return
        cutoff = now - self.window_seconds
        for key in list(self._hits):
            kept = [t for t in self._hits[key] if t > cutoff]
            if kept:
                self._hits[key] = kept
            else:
                del self._hits[key]

    def retry_after(self, key: str, *, now: float) -> float | None:
        """Seconds until ``key`` is allowed again, or ``None`` if not blocked."""
        hits = self._active(key, now)
        if len(hits) < self.max_attempts:
            return None
        return max(0.0, (min(hits) + self.window_seconds) - now)

    def record(self, key: str, *, now: float) -> None:
        self._maybe_sweep(now)
        self._active(key, now)  # prune before appending
        self._hits.setdefault(key, []).append(now)

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)


def _norm_email(email: str) -> str:
    return email.strip().lower()


@dataclass
class LoginRateLimiter:
    """Dual-keyed (client IP + normalized email) login throttle.

    A request is blocked when *either* its IP or its email is over the
    threshold, so neither a single IP spraying many emails nor a single
    email hammered from many IPs can exceed the limit.  Only failures are
    recorded; a successful login resets both keys.
    """

    max_attempts: int
    window_seconds: float
    _limiter: SlidingWindowLimiter = field(init=False)

    def __post_init__(self) -> None:
        self._limiter = SlidingWindowLimiter(
            max_attempts=self.max_attempts,
            window_seconds=self.window_seconds,
        )

    def check(self, *, ip: str, email: str, now: float) -> int | None:
        """Return integer ``Retry-After`` seconds if blocked, else ``None``."""
        candidates = [
            self._limiter.retry_after(f"ip:{ip}", now=now),
            self._limiter.retry_after(f"email:{_norm_email(email)}", now=now),
        ]
        active = [c for c in candidates if c is not None]
        if not active:
            return None
        return max(1, math.ceil(max(active)))

    def record_failure(self, *, ip: str, email: str, now: float) -> None:
        self._limiter.record(f"ip:{ip}", now=now)
        self._limiter.record(f"email:{_norm_email(email)}", now=now)

    def reset(self, *, ip: str, email: str) -> None:
        self._limiter.reset(f"ip:{ip}")
        self._limiter.reset(f"email:{_norm_email(email)}")
