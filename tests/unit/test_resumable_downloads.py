"""Unit tests for resumable S3 downloads.

The e2e environment has no S3 backend, so the S3 streamer and the byte-range
decision logic are covered here with a fake boto3 client; no MinIO is needed.
"""

import pytest
from botocore.exceptions import ClientError

from djehuty.web import s3
from djehuty.web.wsgi import resolve_byte_range

PAYLOAD = bytes(range(256)) * 4  # 1 KiB, deterministic pattern
ETAG = '"etag-1"'
LAST_MODIFIED = "Mon, 20 Jul 2026 10:00:00 GMT"


class FakeBody:
    def __init__(self, payload):
        self.payload = payload
        self.closed = False

    def iter_chunks(self, chunk_size=8192):
        for index in range(0, len(self.payload), chunk_size):
            yield self.payload[index:index + chunk_size]

    def close(self):
        self.closed = True


class FakeS3Client:
    """Mimics boto3's get_object closely enough for S3DownloadStreamer."""

    def __init__(self, payload=PAYLOAD, etag=ETAG, with_content_range=True):
        self.payload = payload
        self.etag = etag
        self.with_content_range = with_content_range
        self.calls = []
        self.bodies = []

    def get_object(self, **kwargs):
        self.calls.append(kwargs)
        if "IfMatch" in kwargs and kwargs["IfMatch"] != self.etag:
            raise ClientError(
                {"Error": {"Code": "PreconditionFailed", "Message": "changed"}},
                "GetObject",
            )
        start, end = self._parse_range(kwargs["Range"])
        piece = self.payload[start:end + 1]
        headers = {
            "content-type": "application/octet-stream",
            "content-length": str(len(piece)),
            "etag": self.etag,
            "last-modified": LAST_MODIFIED,
        }
        if self.with_content_range:
            headers["content-range"] = (
                f"bytes {start}-{start + len(piece) - 1}/{len(self.payload)}"
            )
        body = FakeBody(piece)
        self.bodies.append(body)
        return {"Body": body, "ResponseMetadata": {"HTTPHeaders": headers}}

    def _parse_range(self, header):
        spec = header.removeprefix("bytes=")
        start, _, end = spec.partition("-")
        if end == "":
            return int(start), len(self.payload) - 1
        return int(start), int(end)


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeS3Client()
    monkeypatch.setattr(s3.S3ClientFactory, "get_client",
                        lambda **kwargs: client)
    return client


def make_streamer(**kwargs):
    return s3.S3DownloadStreamer("http://s3.test", "bucket", "key-id", "secret",
                                 "container_file", "file.bin", **kwargs)


class TestS3DownloadStreamer:
    """The streamer's outbound ranges, metadata parsing and IfMatch guard."""

    def test_connect_reads_metadata(self, fake_client):
        streamer = make_streamer()
        streamer.connect()
        assert fake_client.calls[0]["Range"] == "bytes=0-"
        assert "IfMatch" not in fake_client.calls[0]
        assert streamer.content_length == len(PAYLOAD)
        assert streamer.total_length == len(PAYLOAD)
        assert streamer.etag == ETAG
        assert streamer.last_modified == (2026, 7, 20, 10, 0, 0)

    def test_bounded_range_header(self, fake_client):
        streamer = make_streamer(offset=10, end=19)
        streamer.connect()
        assert fake_client.calls[0]["Range"] == "bytes=10-19"
        assert streamer.content_length == 10
        assert streamer.total_length == len(PAYLOAD)

    def test_total_falls_back_to_content_length(self, monkeypatch):
        client = FakeS3Client(with_content_range=False)
        monkeypatch.setattr(s3.S3ClientFactory, "get_client",
                            lambda **kwargs: client)
        streamer = make_streamer()
        streamer.connect()
        assert streamer.total_length == streamer.content_length == len(PAYLOAD)

    def test_iterator_streams_requested_slice(self, fake_client):
        streamer = make_streamer(offset=100, end=299, chunk_size=64)
        assert b"".join(streamer.iterator()) == PAYLOAD[100:300]

    def test_reset_range_reconnects_with_ifmatch(self, fake_client):
        streamer = make_streamer()
        streamer.connect()
        first_body = fake_client.bodies[0]
        streamer.reset_range(offset=100, end=199)
        assert first_body.closed
        assert fake_client.calls[1]["Range"] == "bytes=100-199"
        assert fake_client.calls[1]["IfMatch"] == ETAG
        assert b"".join(streamer.iterator()) == PAYLOAD[100:200]

    def test_reset_reconnects_with_ifmatch(self, fake_client):
        streamer = make_streamer()
        streamer.connect()
        streamer.reset(offset=512)
        assert fake_client.calls[1]["Range"] == "bytes=512-"
        assert fake_client.calls[1]["IfMatch"] == ETAG

    def test_changed_object_refuses_mixed_bytes(self, fake_client):
        streamer = make_streamer()
        streamer.connect()
        fake_client.etag = '"etag-2"'
        streamer.reset_range(offset=100, end=199)
        assert streamer.file_contents is None


TOTAL = 1000


class TestResolveByteRange:
    """The 200/206/416 decision, including malformed Range and If-Range."""

    @pytest.mark.parametrize("range_header", [
        None,
        "",
        "bytes=abc-def",
        "bytes=3333.2",
        "bytes",
        "bytes=0-1,5-6",
    ])
    def test_absent_or_malformed_range_serves_full_file(self, range_header):
        assert resolve_byte_range(range_header, None, ETAG, TOTAL) == ("full", None)

    def test_unknown_total_serves_full_file(self):
        assert resolve_byte_range("bytes=0-99", None, ETAG, 0) == ("full", None)

    @pytest.mark.parametrize("range_header, expected", [
        ("bytes=0-99", (0, 100)),
        ("bytes=900-", (900, TOTAL)),
        ("bytes=-100", (900, TOTAL)),
        ("bytes=0-0", (0, 1)),
        ("bytes=0-4999", (0, TOTAL)),
    ])
    def test_satisfiable_range_serves_partial(self, range_header, expected):
        assert resolve_byte_range(range_header, None, ETAG, TOTAL) == \
            ("partial", expected)

    def test_range_beyond_end_is_unsatisfiable(self):
        assert resolve_byte_range("bytes=1100-", None, ETAG, TOTAL) == \
            ("unsatisfiable", None)

    def test_if_range_with_matching_etag_serves_partial(self):
        assert resolve_byte_range("bytes=0-99", ETAG, ETAG, TOTAL) == \
            ("partial", (0, 100))

    @pytest.mark.parametrize("if_range", [
        '"stale-etag"',
        "Mon, 20 Jul 2026 10:00:00 GMT",
        "garbage",
    ])
    def test_if_range_mismatch_serves_full_file(self, if_range):
        assert resolve_byte_range("bytes=0-99", if_range, ETAG, TOTAL) == \
            ("full", None)

    def test_if_range_without_known_etag_serves_full_file(self):
        assert resolve_byte_range("bytes=0-99", ETAG, None, TOTAL) == ("full", None)
