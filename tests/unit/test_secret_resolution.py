"""Tests for ${env:...} and ${file:...} secret references in JSON config."""

import json
import os

import pytest

from djehuty.web.config.json_parser import (
    ConfigurationError,
    JsonConfigElement,
    parse_config_root,
)


def _write_json(tmp_path, payload):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


class TestEnvReference:
    def test_resolves_env_var(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DJ_TEST_ORCID_SECRET", "abc123")
        path = _write_json(tmp_path, {
            "djehuty": {"authentication": {"orcid": {"client-secret": "${env:DJ_TEST_ORCID_SECRET}"}}}
        })
        root = parse_config_root(path)
        assert root.find("authentication/orcid/client-secret").text == "abc123"

    def test_missing_env_raises(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DJ_TEST_MISSING", raising=False)
        path = _write_json(tmp_path, {"djehuty": {"x": "${env:DJ_TEST_MISSING}"}})
        with pytest.raises(ConfigurationError, match="DJ_TEST_MISSING"):
            parse_config_root(path)

    def test_resolves_in_attribute(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DJ_TEST_DOMAIN", "example.org")
        path = _write_json(tmp_path, {"djehuty": {"quotas": {"@default": "${env:DJ_TEST_DOMAIN}"}}})
        root = parse_config_root(path)
        assert root.find("quotas").attrib["default"] == "example.org"


class TestFileReference:
    def test_resolves_file_contents(self, tmp_path):
        secret = tmp_path / "key.pem"
        secret.write_text("-----BEGIN-----\nbody\n-----END-----\n", encoding="utf-8")
        path = _write_json(tmp_path, {
            "djehuty": {"repository": {"private-key": f"${{file:{secret}}}"}}
        })
        root = parse_config_root(path)
        # .strip() removes the trailing newline; PEM body is preserved
        assert root.find("repository/private-key").text == "-----BEGIN-----\nbody\n-----END-----"

    def test_missing_file_raises(self, tmp_path):
        path = _write_json(tmp_path, {"djehuty": {"x": "${file:/nonexistent/path}"}})
        with pytest.raises(ConfigurationError, match="/nonexistent/path"):
            parse_config_root(path)


class TestPassThrough:
    def test_plain_string_unchanged(self, tmp_path):
        path = _write_json(tmp_path, {"djehuty": {"site-name": "Example"}})
        root = parse_config_root(path)
        assert root.find("site-name").text == "Example"

    def test_partial_placeholder_unchanged(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DJ_TEST_HOST", "ignored")
        path = _write_json(tmp_path, {"djehuty": {"url": "https://${env:DJ_TEST_HOST}/api"}})
        root = parse_config_root(path)
        # Partial interpolation is deliberately NOT supported; literal passes through.
        assert root.find("url").text == "https://${env:DJ_TEST_HOST}/api"

    def test_dollar_prefix_without_braces_unchanged(self, tmp_path):
        path = _write_json(tmp_path, {"djehuty": {"x": "$ENV"}})
        root = parse_config_root(path)
        assert root.find("x").text == "$ENV"


class TestJsonConfigElementDirect:
    def test_env_resolved_via_direct_construction(self, monkeypatch):
        monkeypatch.setenv("DJ_TEST_DIRECT", "value")
        elem = JsonConfigElement("root", {"k": "${env:DJ_TEST_DIRECT}"})
        assert elem.find("k").text == "value"
