"""Login rate-limiter pure logic (ADR-0018)."""

from __future__ import annotations

from medminder.domain.rate_limit import LoginRateLimiter, SlidingWindowLimiter


def test_under_threshold_allows() -> None:
    lim = SlidingWindowLimiter(max_attempts=3, window_seconds=60)
    lim.record("k", now=0.0)
    lim.record("k", now=1.0)
    assert lim.retry_after("k", now=2.0) is None


def test_at_threshold_blocks_with_retry_after() -> None:
    lim = SlidingWindowLimiter(max_attempts=3, window_seconds=60)
    for t in (0.0, 1.0, 2.0):
        lim.record("k", now=t)
    # Oldest hit at t=0 expires at t=60; checking at t=2 → 58s remain.
    assert lim.retry_after("k", now=2.0) == 58.0


def test_window_slides_and_re_allows() -> None:
    lim = SlidingWindowLimiter(max_attempts=3, window_seconds=60)
    for t in (0.0, 1.0, 2.0):
        lim.record("k", now=t)
    assert lim.retry_after("k", now=2.0) is not None
    # Past the window: all three hits expired.
    assert lim.retry_after("k", now=61.0) is None


def test_reset_clears() -> None:
    lim = SlidingWindowLimiter(max_attempts=1, window_seconds=60)
    lim.record("k", now=0.0)
    assert lim.retry_after("k", now=1.0) is not None
    lim.reset("k")
    assert lim.retry_after("k", now=1.0) is None


def test_eviction_bounds_memory() -> None:
    lim = SlidingWindowLimiter(max_attempts=5, window_seconds=10, max_keys=2)
    # Many distinct expired keys, then a fresh record triggers the sweep.
    for i in range(10):
        lim.record(f"old:{i}", now=0.0)
    lim.record("new", now=100.0)  # 100s later → everything else expired
    assert "new" in lim._hits
    assert all(k == "new" for k in lim._hits)


def test_eviction_caps_active_keys_within_window() -> None:
    """Even when all keys are still active within the window, dict stays bounded."""
    lim = SlidingWindowLimiter(max_attempts=5, window_seconds=900, max_keys=3)
    for i in range(10):
        lim.record(f"active:{i}", now=float(i))
    # Cap enforces max_keys before inserting the latest key (so <= max_keys + 1).
    assert len(lim._hits) <= 4
    assert "active:9" in lim._hits
    assert "active:0" not in lim._hits


def test_login_limiter_ip_and_email_independent() -> None:
    lim = LoginRateLimiter(max_attempts=2, window_seconds=60)
    # Two failures for the same IP but different emails → IP key trips.
    lim.record_failure(ip="1.2.3.4", email="a@x.test", now=0.0)
    lim.record_failure(ip="1.2.3.4", email="b@x.test", now=1.0)
    assert lim.check(ip="1.2.3.4", email="c@x.test", now=2.0) is not None
    # A different IP with a never-seen email is still allowed.
    assert lim.check(ip="9.9.9.9", email="c@x.test", now=2.0) is None


def test_login_limiter_email_normalized() -> None:
    lim = LoginRateLimiter(max_attempts=1, window_seconds=60)
    lim.record_failure(ip="", email="  USER@X.test ", now=0.0)
    # Same email, different casing/whitespace, different IP → email key trips.
    assert lim.check(ip="other", email="user@x.test", now=1.0) is not None


def test_login_limiter_retry_after_is_ceil_int() -> None:
    lim = LoginRateLimiter(max_attempts=1, window_seconds=30)
    lim.record_failure(ip="1.1.1.1", email="a@x.test", now=0.0)
    retry = lim.check(ip="1.1.1.1", email="a@x.test", now=0.5)
    assert retry == 30  # 29.5 → ceil → 30, and an int
    assert isinstance(retry, int)
