"""Backend-contract tests for the cache layer.

The same assertions run against every CacheBackend implementation so the file
and shared backends cannot drift. The Valkey backend (via fakeredis) is added to
the ``backend`` fixture's params where it lives; these tests are the single
definition of the behaviour both must honour.
"""

import json
from types import SimpleNamespace

import fakeredis
import pytest

from djehuty.web.cache import FileCacheBackend
from djehuty.web.cache_valkey import ValkeyCacheBackend


def _file_backend(tmp_path):
    backend = FileCacheBackend(str(tmp_path / "cache"))
    assert backend.cache_is_ready()
    return backend


def valkey_config(**overrides):
    """A minimal config object exposing the attributes ValkeyCacheBackend reads."""
    defaults = {
        "cache_backend_host": "localhost",
        "cache_backend_port": 6379,
        "cache_backend_db": 0,
        "cache_backend_password": None,
        "cache_backend_tls": False,
        "cache_ttl": None,
        "cache_coarse_invalidation": False,
        "cache_deployment": "test",
        "work_dir": "/tmp/djehuty-work",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def valkey_backend(server=None, **overrides):
    """A ValkeyCacheBackend wired to an in-memory fakeredis (no container)."""
    backend = ValkeyCacheBackend(valkey_config(**overrides))
    backend._redis = fakeredis.FakeRedis(server=server, decode_responses=True)
    return backend


@pytest.fixture(params=["file", "valkey"])
def backend(request, tmp_path):
    """Yield a ready-to-use cache backend for each supported implementation."""
    if request.param == "file":
        return _file_backend(tmp_path)
    if request.param == "valkey":
        return valkey_backend()
    raise ValueError(f"Unknown backend param: {request.param}")


def test_make_key_is_stable_and_cross_backend(backend):
    # md5 of "abc"; pinned so every backend produces identical keys.
    assert backend.make_key("abc") == "900150983cd24fb0d6963f7d28e17f72"
    assert backend.make_key("abc") == backend.make_key("abc")
    assert backend.make_key("abc") != backend.make_key("abd")
    assert backend.make_key(None) is None


def test_miss_returns_none(backend):
    assert backend.cached_value("datasets", "missing") is None
    assert backend.cached_value("datasets", "missing", is_raw=True) is None


@pytest.mark.parametrize(
    "value",
    [
        {"a": 1, "b": [1, 2, 3]},
        [{"uuid": "x"}, {"uuid": "y"}],
        True,
        False,
        "a plain string",
        42,
    ],
)
def test_json_round_trip(backend, value):
    key = backend.make_key("some-query")
    assert backend.cache_value("datasets", key, value) == value
    assert backend.cached_value("datasets", key) == value


def test_is_raw_round_trip(backend):
    key = backend.make_key("raw-query")
    backend.cache_value("iiif_manifest", key, "raw-bytes-as-string", is_raw=True)
    assert backend.cached_value("iiif_manifest", key, is_raw=True) == "raw-bytes-as-string"


def test_git_languages_double_encoded_shape(backend):
    # services/git.py stores an already-json.dumps'd string with is_raw=False, so
    # the backend json.dumps it again; reading it back json.loads once, yielding
    # the original JSON string (not the decoded object). Pin that exact shape.
    summary = json.dumps({"Python": 10, "C": 3})
    key = backend.make_key("git-languages")
    backend.cache_value("git_languages", key, summary)
    assert backend.cached_value("git_languages", key) == summary


def test_invalidate_by_prefix_isolates_other_bases(backend):
    d_key = backend.make_key("d")
    c_key = backend.make_key("c")
    backend.cache_value("datasets", d_key, {"v": 1})
    backend.cache_value("collections", c_key, {"v": 2})

    backend.invalidate_by_prefix("datasets")

    assert backend.cached_value("datasets", d_key) is None
    assert backend.cached_value("collections", c_key) == {"v": 2}


def test_invalidate_base_also_clears_children(backend):
    # Reproduces the file glob: invalidate_by_prefix("datasets") also clears
    # datasets_{uuid}_* (the depth-2 family).
    base_key = backend.make_key("base")
    child_key = backend.make_key("child")
    backend.cache_value("datasets", base_key, {"v": "base"})
    backend.cache_value("datasets_ACCOUNT", child_key, {"v": "child"})

    backend.invalidate_by_prefix("datasets")

    assert backend.cached_value("datasets", base_key) is None
    assert backend.cached_value("datasets_ACCOUNT", child_key) is None


def test_invalidate_child_leaves_base_and_siblings(backend):
    base_key = backend.make_key("base")
    child_key = backend.make_key("child")
    sibling_key = backend.make_key("sibling")
    backend.cache_value("datasets", base_key, {"v": "base"})
    backend.cache_value("datasets_ACCOUNT", child_key, {"v": "child"})
    backend.cache_value("datasets_OTHER", sibling_key, {"v": "sibling"})

    backend.invalidate_by_prefix("datasets_ACCOUNT")

    assert backend.cached_value("datasets_ACCOUNT", child_key) is None
    assert backend.cached_value("datasets", base_key) == {"v": "base"}
    assert backend.cached_value("datasets_OTHER", sibling_key) == {"v": "sibling"}


def test_invalidate_all_clears_everything(backend):
    d_key = backend.make_key("d")
    c_key = backend.make_key("c")
    backend.cache_value("datasets", d_key, {"v": 1})
    backend.cache_value("collections", c_key, {"v": 2})

    backend.invalidate_all()

    assert backend.cached_value("datasets", d_key) is None
    assert backend.cached_value("collections", c_key) is None
