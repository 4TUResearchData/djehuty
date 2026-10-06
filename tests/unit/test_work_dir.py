"""Unit tests for work-dir resolution (djehuty.web.ui.resolve_work_dir).

The working directory holds non-cache artifacts (SAML/handle config, temporary
working directories). It defaults to the cache directory so the on-disk layout is
unchanged, including when a custom cache-root is configured.
"""

from defusedxml import ElementTree

from djehuty.web.config.json_parser import JsonConfigElement
from djehuty.web.ui import resolve_work_dir


def _json(data):
    return JsonConfigElement("djehuty", data)


def _xml(inner):
    return ElementTree.fromstring(f"<djehuty>{inner}</djehuty>")


def test_absent_defaults_to_cache_storage():
    cache_storage = "/var/lib/djehuty/cache"
    assert resolve_work_dir(_json({}), cache_storage) == cache_storage
    assert resolve_work_dir(_xml(""), cache_storage) == cache_storage


def test_explicit_value_is_honoured():
    assert resolve_work_dir(_json({"work-dir": "/srv/work"}), "/cache") == "/srv/work"
    assert resolve_work_dir(_xml("<work-dir>/srv/work</work-dir>"), "/cache") == "/srv/work"


def test_defaults_follow_custom_cache_root():
    # With a custom cache-root and no work-dir, the working directory follows the
    # cache dir (the caller passes the already-resolved cache directory).
    custom_cache = "/mnt/fast/djehuty-cache"
    assert resolve_work_dir(_json({}), custom_cache) == custom_cache
