"""Tests for the prefix-free JSON schema (no @attr / #text required)."""

import json

import pytest

from djehuty.web.config.json_parser import JsonConfigElement, parse_config_root


def _write_json(tmp_path, payload):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


class TestCleanSchema:
    def test_scalar_key_populates_both_attrib_and_child(self):
        elem = JsonConfigElement("account", {"orcid": "0000-0001"})
        # Reachable via attribute access (XML-attribute style)
        assert elem.attrib.get("orcid") == "0000-0001"
        # Reachable via find() (XML-child-element style)
        assert elem.find("orcid").text == "0000-0001"

    def test_nested_dict_only_a_child(self):
        elem = JsonConfigElement("djehuty", {"colors": {"primary": "#fff"}})
        assert "colors" not in elem.attrib
        assert elem.find("colors").find("primary").text == "#fff"

    def test_quotas_default_attribute(self, tmp_path):
        path = _write_json(tmp_path, {"djehuty": {"quotas": {"default": "5000"}}})
        root = parse_config_root(path)
        quotas = root.find("quotas")
        assert quotas.attrib["default"] == "5000"

    def test_group_metadata_as_plain_keys(self, tmp_path):
        path = _write_json(tmp_path, {"djehuty": {"groups": {"group": [
            {"name": "TU", "domain": "tudelft.nl", "id": "1", "is_featured": "1"}
        ]}}})
        root = parse_config_root(path)
        group = next(iter(root.find("groups")))
        assert group.attrib["name"] == "TU"
        assert group.attrib["domain"] == "tudelft.nl"
        assert group.attrib["is_featured"] == "1"


class TestBackCompat:
    def test_at_prefix_still_recognised(self):
        elem = JsonConfigElement("account", {"@orcid": "0000-0001"})
        assert elem.attrib["orcid"] == "0000-0001"
        # Legacy form does NOT also create a child.
        assert elem.find("orcid") is None

    def test_hash_text_marker_still_recognised(self):
        elem = JsonConfigElement("quota", {"domain": "tudelft.nl", "#text": "50000"})
        assert elem.attrib["domain"] == "tudelft.nl"
        assert elem.text == "50000"

    def test_mixed_legacy_and_clean(self):
        # Legacy @ keys and bare keys can coexist.
        elem = JsonConfigElement("x", {"@legacy": "a", "modern": "b"})
        assert elem.attrib["legacy"] == "a"
        assert elem.attrib["modern"] == "b"
        assert elem.find("modern").text == "b"
        assert elem.find("legacy") is None


class TestExampleConfigClean:
    """Smoke tests on the rewritten example config to catch regressions."""

    def test_loads(self, json_root):
        assert json_root.tag == "djehuty"

    def test_account_metadata_accessible_as_attrib(self, json_root):
        privileges = json_root.find("privileges")
        account = next(iter(privileges))
        assert account.attrib.get("email") == "you@example.com"
        assert account.attrib.get("orcid") == "0000-0000-0000-0001"

    def test_group_metadata_accessible_as_attrib(self, json_root):
        groups = json_root.find("groups")
        first = next(iter(groups))
        for key in ("name", "domain", "id", "parent_id"):
            assert key in first.attrib, f"missing {key}"

    def test_quota_default_accessible_as_attrib(self, json_root):
        quotas = json_root.find("quotas")
        assert quotas.attrib["default"] == "5000000000"

    def test_quota_group_keeps_text_value(self, json_root):
        quotas = json_root.find("quotas")
        groups = [q for q in quotas if q.tag == "group"]
        assert groups[0].attrib["domain"] == "tudelft.nl"
        assert int(groups[0].text) == 50000000000
