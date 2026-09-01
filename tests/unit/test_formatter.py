"""Unit tests for djehuty.web.formatter."""

from djehuty.web.formatter import format_collection_record


class TestFormatCollectionRecord:
    """format_collection_record must surface the `version` field so the
    frontend can distinguish published versions from unversioned drafts.
    """

    def test_includes_version_when_present(self):
        record = {
            "collection_id": 1,
            "container_uuid": "abc-123",
            "title": "A collection",
            "version": 3,
        }
        assert format_collection_record(record)["version"] == 3

    def test_version_is_none_for_a_draft(self):
        record = {
            "collection_id": 1,
            "container_uuid": "abc-123",
            "title": "A draft collection",
        }
        assert format_collection_record(record)["version"] is None

    def test_all_fields_are_mapped(self):
        record = {
            "collection_id": 1,
            "container_uuid": "abc-123",
            "title": "A collection",
            "version": 2,
            "doi": "10.1234/abc",
            "handle": "hdl.handle.net/abc",
            "url": "https://example.org/collections/abc-123",
            "timeline_posted": "2024-01-01",
            "timeline_submission": "2024-01-02",
            "timeline_revision": "2024-01-03",
            "timeline_first_online": "2024-01-04",
            "timeline_publisher_publication": "2024-01-05",
            "published_date": "2024-01-06",
        }
        assert format_collection_record(record) == {
            "id": 1,
            "uuid": "abc-123",
            "title": "A collection",
            "version": 2,
            "doi": "10.1234/abc",
            "handle": "hdl.handle.net/abc",
            "url": "https://example.org/collections/abc-123",
            "timeline": {
                "posted": "2024-01-01",
                "submission": "2024-01-02",
                "revision": "2024-01-03",
                "firstOnline": "2024-01-04",
                "publisherPublication": "2024-01-05",
            },
            "published_date": "2024-01-06",
        }

    def test_missing_optional_fields_default_correctly(self):
        record = {
            "collection_id": 1,
            "container_uuid": "abc-123",
            "title": "A collection",
        }
        formatted = format_collection_record(record)

        assert formatted["handle"] == ""
        assert formatted["id"] == 1
        for key in ("doi", "url", "published_date"):
            assert formatted[key] is None
        for key in formatted["timeline"]:
            assert formatted["timeline"][key] is None

    def test_timeline_fields_are_mapped_individually(self):
        record = {
            "collection_id": 1,
            "container_uuid": "abc-123",
            "title": "A collection",
            "timeline_posted": "2024-01-01",
            "timeline_first_online": "2024-01-04",
        }
        timeline = format_collection_record(record)["timeline"]

        assert timeline["posted"] == "2024-01-01"
        assert timeline["firstOnline"] == "2024-01-04"
        assert timeline["submission"] is None
        assert timeline["revision"] is None
        assert timeline["publisherPublication"] is None
