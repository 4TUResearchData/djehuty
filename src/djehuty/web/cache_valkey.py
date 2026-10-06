"""Shared cache backend backed by Valkey (a Redis-compatible keyspace).

Interchangeable with FileCacheBackend; reproduces its glob invalidation with
ancestor-aware version stamps and is fail-open (a circuit breaker bypasses to
SPARQL when Valkey is unreachable).
"""

import json
import logging
import time

import redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from djehuty.web.cache import CacheBackend

FAMILY_BASES = ("datasets", "collections", "physical-samples")
_SOCKET_TIMEOUT = 1
_FAIL_OPEN_COOLDOWN = 30


class ValkeyCacheBackend(CacheBackend):
    """A shared cache backend backed by Valkey."""

    def __init__(self, config):
        self.log = logging.getLogger(__name__)
        self.host = config.cache_backend_host
        self.port = int(config.cache_backend_port)
        self.db = int(config.cache_backend_db)
        self.password = config.cache_backend_password
        self.tls = bool(config.cache_backend_tls)
        self.ttl = int(config.cache_ttl) if config.cache_ttl else None
        self.coarse = bool(config.cache_coarse_invalidation)
        self.namespace = f"djehuty:{config.cache_deployment}"
        self.storage = config.work_dir
        self._redis = None
        self._down_until = 0.0

    def _client(self):
        """Return a lazily-created, per-process Valkey client."""
        if self._redis is None:
            self._redis = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                ssl=self.tls,
                decode_responses=True,
                socket_timeout=_SOCKET_TIMEOUT,
                socket_connect_timeout=_SOCKET_TIMEOUT,
                retry=Retry(NoBackoff(), 0),
            )
        return self._redis

    def _available(self):
        """False while the circuit breaker is open."""
        return time.monotonic() >= self._down_until

    def _trip(self, error, context):
        """Open the circuit breaker and drop the client after a failure."""
        self._down_until = time.monotonic() + _FAIL_OPEN_COOLDOWN
        self._redis = None
        self.log.warning(
            "Valkey unavailable on %s (%s); bypassing cache for %ds.",
            context,
            error,
            _FAIL_OPEN_COOLDOWN,
        )

    def _nsver_key(self):
        return f"{self.namespace}:nsver"

    def _pver_key(self, prefix):
        return f"{self.namespace}:pver:{prefix}"

    def _classify(self, prefix):
        """Return the family base when 'prefix' is a depth-2 child, else None."""
        for base in FAMILY_BASES:
            if prefix.startswith(f"{base}_"):
                return base
        return None

    def _value_key(self, client, prefix, key):
        """Build the version-stamped value key for (prefix, key)."""
        base = self._classify(prefix)
        counter_keys = [self._nsver_key(), self._pver_key(prefix)]
        if base is not None:
            counter_keys.append(self._pver_key(base))

        values = client.mget(counter_keys)
        nsver = int(values[0] or 0)
        pver = int(values[1] or 0)
        if base is not None:
            base_ver = int(values[2] or 0)
            stamp = f"{base_ver}.{pver}"
        else:
            stamp = str(pver)

        return f"{self.namespace}:n{nsver}:{prefix}#{stamp}:{key}"

    def cache_is_ready(self):
        """Procedure to set up and test the ability to cache."""
        if not self._available():
            return False
        try:
            return bool(self._client().ping())
        except (redis.RedisError, OSError) as error:
            self._trip(error, "ping")
            return False

    def cached_value(self, prefix, key, is_raw=False):
        """Returns the cached value or None."""
        if not self._available():
            return None
        try:
            client = self._client()
            cached = client.get(self._value_key(client, prefix, key))
            if cached is None:
                return None
            if is_raw:
                return cached
            return json.loads(cached)
        except (redis.RedisError, OSError) as error:
            self._trip(error, "read")
            return None
        except json.decoder.JSONDecodeError:
            self.log.error("Possible cache corruption at %s.", key)
            return None

    def cache_value(self, prefix, key, value, query=None, is_raw=False):
        """Procedure to store 'value' as a cache."""
        if self._available():
            try:
                client = self._client()
                value_key = self._value_key(client, prefix, key)
                stored = value if is_raw else json.dumps(value)
                if self.ttl:
                    client.set(value_key, stored, ex=self.ttl)
                else:
                    client.set(value_key, stored)
            except (redis.RedisError, OSError) as error:
                self._trip(error, "write")

        return value

    def invalidate_by_prefix(self, prefix):
        """Procedure to remove all cache items belonging to 'prefix'."""
        if not self._available():
            return False
        try:
            base = self._classify(prefix)
            if base is not None and self.coarse:
                self._client().incr(self._pver_key(base))
            else:
                self._client().incr(self._pver_key(prefix))
            return True
        except (redis.RedisError, OSError) as error:
            self._trip(error, f"invalidate_by_prefix({prefix})")
            return False

    def invalidate_all(self):
        """Procedure to remove all cache items."""
        if not self._available():
            return False
        try:
            self._client().incr(self._nsver_key())
            return True
        except (redis.RedisError, OSError) as error:
            self._trip(error, "invalidate_all")
            return False
