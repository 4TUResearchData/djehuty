"""Tests for configuration file parsing."""

import pytest

from djehuty.web.config import config
from djehuty.web.config.json_parser import JsonConfigElement
from djehuty.web.ui import config_value, read_boolean_value, read_raw_xml
from djehuty.web.ui import (
    read_custom_stylesheets,
    read_fonts_configuration,
    warn_about_unresolvable_asset,
)


class TestConfigValue:
    def test_simple_text_value(self, config_root):
        assert config_value(config_root, "bind-address") == "127.0.0.1"
        assert config_value(config_root, "port") == "8080"

    def test_nested_path(self, config_root):
        assert config_value(config_root, "rdf-store/sparql-uri") == "http://localhost:8890/sparql"
        assert config_value(config_root, "rdf-store/state-graph") == "djehuty://local"

    def test_missing_returns_none(self, config_root):
        assert config_value(config_root, "nonexistent") is None

    def test_missing_returns_fallback(self, config_root):
        assert config_value(config_root, "nonexistent", fallback="default") == "default"

    def test_command_line_takes_precedence(self, config_root):
        assert config_value(config_root, "port", command_line="9090") == "9090"

    def test_return_node(self, config_root):
        node = config_value(config_root, "cache-root", return_node=True)
        assert node is not None
        assert node.text == "./data/cache"
        assert node.attrib.get("clear-on-start") == "1"

    def test_none_root_returns_fallback(self):
        assert config_value(None, "port", fallback="1234") == "1234"


class TestReadBooleanValue:
    @pytest.mark.parametrize(
        "path, expected",
        [
            ("live-reload", True),
            ("disable-2fa", True),
            ("show-portal-summary", True),
            ("show-institutions", True),
            ("show-latest-datasets", True),
            ("enable-query-audit-log", True),
        ],
    )
    def test_true_values(self, config_root, logger, path, expected):
        assert read_boolean_value(config_root, path, False, logger) is expected

    def test_false_value(self, config_root, logger):
        assert read_boolean_value(config_root, "maintenance-mode", True, logger) is False

    @pytest.mark.parametrize("default", [True, False])
    def test_missing_returns_default(self, config_root, logger, default):
        assert read_boolean_value(config_root, "nonexistent", default, logger) is default


class TestReadRawXml:
    def test_sandbox_message_with_style(self, config_root):
        content, attributes = read_raw_xml(config_root, "sandbox-message")
        assert content is not None
        assert "example configuration" in content
        assert attributes is not None
        assert "background" in attributes.get("style", "")

    def test_notice_message(self, config_root):
        content, _ = read_raw_xml(config_root, "notice-message")
        assert content is not None
        assert "<a" in content

    def test_small_footer_contains_html(self, config_root):
        content, _ = read_raw_xml(config_root, "small-footer")
        assert content is not None
        assert "footer-wrapper2" in content

    def test_missing_returns_default(self, config_root):
        content, attributes = read_raw_xml(config_root, "nonexistent", "fallback")
        assert content == "fallback"
        assert attributes is None


class TestThemeConfiguration:
    def test_missing_fonts_leave_fonts_unconfigured(self, monkeypatch):
        """Leave fonts unconfigured when the section is absent."""
        monkeypatch.setattr(config, "fonts", None)
        root = JsonConfigElement("djehuty", {})

        read_fonts_configuration(root)

        assert config.fonts is None

    def test_reads_font_faces_and_font_families(self, monkeypatch):
        """Read font faces, families, and default properties."""
        monkeypatch.setattr(config, "fonts", None)
        root = JsonConfigElement(
            "djehuty",
            {
                "fonts": {
                    "body-font-family": "'Example Sans', sans-serif",
                    "ui-font-family": "'Example UI', sans-serif",
                    "mono-font-family": "'Example Mono', monospace",
                    "font-face": [
                        {
                            "family": "Example Sans",
                            "src": "/assets/fonts/example-regular.woff2",
                            "format": "woff2",
                            "weight": "400",
                            "style": "normal",
                        },
                        {
                            "family": "Example Sans",
                            "src": "/assets/fonts/example-bold.woff2",
                            "weight": "700",
                        },
                    ],
                },
            },
        )

        read_fonts_configuration(root)

        assert config.fonts == {
            "font_faces": [
                {
                    "family": "Example Sans",
                    "src": "/assets/fonts/example-regular.woff2",
                    "format": "woff2",
                    "weight": "400",
                    "style": "normal",
                    "display": "swap",
                },
                {
                    "family": "Example Sans",
                    "src": "/assets/fonts/example-bold.woff2",
                    "format": "woff2",
                    "weight": "700",
                    "style": None,
                    "display": "swap",
                },
            ],
            "body_font": "'Example Sans', sans-serif",
            "ui_font": "'Example UI', sans-serif",
            "mono_font": "'Example Mono', monospace",
        }

    def test_missing_custom_stylesheets_leave_list_empty(self, monkeypatch):
        """Leave custom stylesheets empty when none are configured."""
        monkeypatch.setattr(config, "custom_stylesheets", [])
        root = JsonConfigElement("djehuty", {})

        read_custom_stylesheets(root)

        assert config.custom_stylesheets == []

    def test_reads_unique_trimmed_custom_stylesheets(self, monkeypatch):
        """Trim stylesheet paths, remove duplicates, and ignore blanks."""
        monkeypatch.setattr(config, "custom_stylesheets", [])
        root = JsonConfigElement(
            "djehuty",
            {
                "custom-stylesheet": [
                    "/assets/css/first.css",
                    " /assets/css/second.css ",
                    "/assets/css/first.css",
                    "   ",
                ],
            },
        )

        read_custom_stylesheets(root)

        assert config.custom_stylesheets == [
            "/assets/css/first.css",
            "/assets/css/second.css",
        ]


class TestAssetWarnings:
    def test_ignores_non_asset_url(self, caplog, logger):
        """Ignore asset references outside the served asset path."""
        warn_about_unresolvable_asset(
            None,
            "https://example.com/custom.css",
            "Stylesheet",
            logger,
        )

        assert caplog.records == []

    def test_warns_when_assets_root_is_unset(self, caplog, logger):
        """Warn when an asset path is configured without an assets root."""
        warn_about_unresolvable_asset(
            None,
            "/assets/css/custom.css",
            "Stylesheet",
            logger,
        )

        assert "'custom-assets-root' is unset" in caplog.text

    def test_warns_when_asset_file_is_missing(self, tmp_path, caplog, logger):
        """Warn when a configured asset file does not exist."""
        warn_about_unresolvable_asset(
            str(tmp_path),
            "/assets/css/missing.css",
            "Stylesheet",
            logger,
        )

        assert "does not exist under" in caplog.text

    def test_does_not_warn_when_asset_file_exists(self, tmp_path, caplog, logger):
        """Do not warn when a configured asset file exists."""
        asset = tmp_path / "css" / "custom.css"
        asset.parent.mkdir()
        asset.write_text("body {}", encoding="utf-8")

        warn_about_unresolvable_asset(
            str(tmp_path),
            "/assets/css/custom.css",
            "Stylesheet",
            logger,
        )

        assert caplog.records == []

    def test_warns_when_asset_source_is_missing(self, tmp_path, caplog, logger):
        """Warn when a configured asset has no source."""
        warn_about_unresolvable_asset(
            str(tmp_path),
            None,
            "Font 'Example Sans'",
            logger,
        )

        assert "has no source configured" in caplog.text


class TestElementAttributes:
    def test_cache_root(self, config_root):
        node = config_root.find("cache-root")
        assert node is not None
        assert node.text == "./data/cache"
        assert node.attrib.get("clear-on-start") == "1"

    def test_quotas_default(self, config_root):
        quotas = config_root.find("quotas")
        assert quotas is not None
        assert quotas.attrib["default"] == "5000000000"

    def test_enable_query_audit_log(self, config_root):
        node = config_root.find("enable-query-audit-log")
        assert node is not None
        assert node.text == "1"


class TestElementIteration:
    def test_privileges_accounts(self, config_root):
        privileges = config_root.find("privileges")
        assert privileges is not None
        accounts = list(privileges)
        assert len(accounts) >= 1
        first = accounts[0]
        assert first.tag == "account"
        assert "email" in first.attrib
        assert "first_name" in first.attrib

    def test_privilege_child_values(self, config_root):
        privileges = config_root.find("privileges")
        account = list(privileges)[0]
        assert config_value(account, "may-administer") == "1"

    def test_quotas_children(self, config_root):
        quotas = config_root.find("quotas")
        children = list(quotas)
        assert len(children) >= 2
        tags = {child.tag for child in children}
        assert "group" in tags
        assert "account" in tags

    def test_quota_group_has_domain_and_value(self, config_root):
        quotas = config_root.find("quotas")
        groups = [q for q in quotas if q.tag == "group"]
        assert len(groups) >= 1
        assert groups[0].attrib.get("domain") is not None
        assert int(groups[0].text) > 0

    def test_groups_required_attributes(self, config_root):
        groups = config_root.find("groups")
        assert groups is not None
        group_list = list(groups)
        assert len(group_list) > 0
        for attr in ("name", "domain", "id"):
            assert attr in group_list[0].attrib

    def test_groups_featured_flag(self, config_root):
        groups = config_root.find("groups")
        featured = [g for g in groups if g.attrib.get("is_featured") == "1"]
        not_featured = [g for g in groups if g.attrib.get("is_featured") is None]
        assert len(featured) > 0
        assert len(not_featured) > 0

    def test_group_has_no_iterable_children(self, config_root):
        # Each <group/> is self-closing in XML: name/domain/id/... are
        # attributes, not children. Iterating a group must yield nothing so the
        # member-loop in ui.py does not mistake attributes for member entries.
        groups = config_root.find("groups")
        first_group = list(groups)[0]
        assert list(first_group) == []
        assert len(first_group) == 0
        assert first_group.attrib.get("name") is not None


class TestNestedConfigurations:
    @pytest.mark.parametrize(
        "path",
        [
            "rdf-store/sparql-uri",
            "rdf-store/sparql-update-uri",
            "rdf-store/state-graph",
        ],
    )
    def test_rdf_store_fields_present(self, config_root, path):
        assert config_value(config_root, path) is not None

    def test_datacite(self, config_root):
        datacite = config_root.find("datacite")
        assert datacite is not None
        assert config_value(datacite, "api-url") == "https://api.datacite.org"
        assert config_value(datacite, "prefix") == "10.5438"

    def test_authentication_orcid(self, config_root):
        orcid = config_root.find("authentication/orcid")
        assert orcid is not None
        assert config_value(orcid, "endpoint") == "https://orcid.org/oauth"

    def test_email_port(self, config_root):
        email = config_root.find("email")
        assert email is not None
        assert config_value(email, "port") == "587"

    @pytest.mark.parametrize(
        "color_key, expected",
        [
            ("primary-color", "#f49120"),
            ("primary-color-hover", "#d26000"),
            ("primary-color-active", "#9d4800"),
        ],
    )
    def test_colors(self, config_root, color_key, expected):
        colors = config_root.find("colors")
        assert colors is not None
        assert config_value(colors, color_key) == expected


class TestSiteMetadata:
    @pytest.mark.parametrize(
        "path, expected",
        [
            ("site-name", "Djehuty example instance"),
            ("site-shorttag", "example-shorttag"),
            ("site-description", "Djehuty example instance"),
            ("support-email-address", "support@example.com"),
        ],
    )
    def test_site_fields(self, config_root, path, expected):
        assert config_value(config_root, path) == expected


class TestPublisherRors:
    def test_block_present(self, config_root):
        block = config_root.find("publisher-rors")
        assert block is not None

    def test_entries_have_name_and_url(self, config_root):
        block = config_root.find("publisher-rors")
        entries = list(block)
        assert len(entries) >= 1
        for entry in entries:
            assert entry.tag == "publisher-ror"
            assert entry.attrib.get("name")
            assert entry.attrib.get("url", "").startswith("https://ror.org/")

    def test_site_name_entry_resolvable(self, config_root):
        block = config_root.find("publisher-rors")
        mapping = {e.attrib["name"]: e.attrib["url"] for e in block}
        site_name = config_root.find("site-name").text
        assert mapping.get(site_name, "").startswith("https://ror.org/")
