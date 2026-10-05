"""Valkey-specific cache backend tests (fakeredis; no container required).

The shared AS-IS contract lives in test_cache_backends.py (run against both the
file and Valkey backends). This file covers behaviour unique to the Valkey
backend: fail-open, the TTL backstop, per-deployment namespacing, and the
coarse-invalidation escape hatch.
"""

import fakeredis
import redis

from djehuty.web.cache_valkey import ValkeyCacheBackend
from tests.unit.test_cache_backends import valkey_backend, valkey_config


class _BrokenClient:
    """A client whose every operation raises, simulating an unreachable Valkey."""

    def __getattr__(self, _name):
        def _raise(*_args, **_kwargs):
            raise redis.ConnectionError("Valkey is down")

        return _raise


def _broken_backend():
    backend = ValkeyCacheBackend(valkey_config())
    backend._redis = _BrokenClient()
    return backend


def test_circuit_breaker_short_circuits_after_failure():
    # After one failure the breaker opens, so subsequent calls skip Valkey
    # entirely (no more client calls) instead of each paying a socket timeout.
    backend = ValkeyCacheBackend(valkey_config())
    calls = {"n": 0}

    class _CountingBroken:
        def __getattr__(self, _name):
            def _raise(*_args, **_kwargs):
                calls["n"] += 1
                raise redis.ConnectionError("Valkey is down")

            return _raise

    backend._redis = _CountingBroken()

    assert backend.cached_value("datasets", backend.make_key("q1")) is None
    assert calls["n"] == 1  # one client call tripped the breaker

    # Breaker is now open: these do not touch the client at all.
    assert backend.cached_value("datasets", backend.make_key("q2")) is None
    assert backend.cache_value("datasets", backend.make_key("q3"), {"v": 1}) == {"v": 1}
    assert backend.invalidate_by_prefix("datasets") is False
    assert calls["n"] == 1


def test_fail_open_reads_miss_writes_succeed():
    backend = _broken_backend()
    key = backend.make_key("q")

    # Reads degrade to a miss (caller falls back to SPARQL) ...
    assert backend.cached_value("datasets", key) is None
    # ... writes never raise and still return the value ...
    assert backend.cache_value("datasets", key, {"v": 1}) == {"v": 1}
    # ... invalidations are best-effort and report failure without raising ...
    assert backend.invalidate_by_prefix("datasets") is False
    assert backend.invalidate_all() is False
    # ... and readiness reports down.
    assert backend.cache_is_ready() is False


def test_ttl_applied_only_when_configured():
    with_ttl = valkey_backend(cache_ttl=3600)
    with_ttl.cache_value("datasets", with_ttl.make_key("q"), {"v": 1})
    keys = with_ttl._redis.keys("*")
    assert len(keys) == 1
    assert with_ttl._redis.ttl(keys[0]) > 0

    without_ttl = valkey_backend()
    without_ttl.cache_value("datasets", without_ttl.make_key("q"), {"v": 1})
    keys = without_ttl._redis.keys("*")
    assert len(keys) == 1
    assert without_ttl._redis.ttl(keys[0]) == -1  # -1 == no expiry in Redis/Valkey


def test_invalidate_all_is_namespaced_per_deployment():
    # Two deployments sharing one Valkey must not clear each other's keys.
    server = fakeredis.FakeServer()
    dep_a = valkey_backend(server=server, cache_deployment="a")
    dep_b = valkey_backend(server=server, cache_deployment="b")

    key_a = dep_a.make_key("q")
    key_b = dep_b.make_key("q")
    dep_a.cache_value("datasets", key_a, {"v": "a"})
    dep_b.cache_value("datasets", key_b, {"v": "b"})

    dep_a.invalidate_all()

    assert dep_a.cached_value("datasets", key_a) is None
    assert dep_b.cached_value("datasets", key_b) == {"v": "b"}


def test_coarse_mode_collapses_child_invalidation_to_base():
    backend = valkey_backend(cache_coarse_invalidation=True)
    base_key = backend.make_key("base")
    child_key = backend.make_key("child")
    sibling_key = backend.make_key("sibling")
    backend.cache_value("datasets", base_key, {"v": "base"})
    backend.cache_value("datasets_ACCOUNT", child_key, {"v": "child"})
    backend.cache_value("datasets_OTHER", sibling_key, {"v": "sibling"})

    # In coarse mode a single child invalidation bumps the whole base group, so
    # the base and the sibling are invalidated too (over-invalidates, never stale).
    backend.invalidate_by_prefix("datasets_ACCOUNT")

    assert backend.cached_value("datasets_ACCOUNT", child_key) is None
    assert backend.cached_value("datasets", base_key) is None
    assert backend.cached_value("datasets_OTHER", sibling_key) is None


def test_invalidate_by_prefix_is_a_single_counter_bump():
    # A prefix bump is O(1): it increments one counter and never touches value
    # keys or siblings directly (no SCAN/FLUSHDB).
    backend = valkey_backend()
    other_key = backend.make_key("other")
    backend.cache_value("accounts", other_key, {"v": "keep"})

    before = backend._redis.get(f"{backend.namespace}:pver:datasets")
    assert before is None
    backend.invalidate_by_prefix("datasets")
    after = backend._redis.get(f"{backend.namespace}:pver:datasets")
    assert after == "1"

    # An unrelated base is untouched.
    assert backend.cached_value("accounts", other_key) == {"v": "keep"}
