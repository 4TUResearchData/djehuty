"""This module implements interaction with an S3 endpoint."""

import logging
import os
import threading
import uuid
from datetime import datetime

from djehuty.utils.convenience import value_or
from djehuty.web.config import config

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import (
        ClientError,
        PartialCredentialsError,
        ReadTimeoutError,
        ResponseStreamingError,
    )
    from urllib3.exceptions import IncompleteRead
except (ImportError, ModuleNotFoundError):
    pass

DEFAULT_CHUNK_SIZE = 32768
DEFAULT_OFFSET = 0


class S3ClientFactory:
    """Thread-safe singleton manager for boto3 S3 clients."""

    _clients = {}
    _lock = threading.Lock()
    _boto_config = Config(
        retries={"total_max_attempts": 30, "mode": "standard"},
        max_pool_connections=25,
        read_timeout=120,
    )

    @classmethod
    def get_client(cls, endpoint, access_key, secret_key):
        """
        Returns a cached boto3 S3 client for the given endpoint/credentials.
        Creates a new client only if one doesn't exist for this configuration.
        """
        cache_key = (endpoint, access_key, secret_key)

        if cache_key not in cls._clients:
            with cls._lock:
                # Double-check after acquiring lock
                if cache_key not in cls._clients:
                    logging.getLogger(__name__).info(
                        "Creating new S3 client for endpoint: %s", endpoint
                    )

                    cls._clients[cache_key] = boto3.client(
                        "s3",
                        endpoint_url=endpoint,
                        aws_access_key_id=access_key,
                        aws_secret_access_key=secret_key,
                        config=cls._boto_config,
                    )
        return cls._clients[cache_key]


class S3DownloadStreamer:
    """Generator to stream the contents of a file stored in S3."""

    def __init__(
        self,
        endpoint,
        bucket,
        access_key,
        secret_key,
        filename,
        name,
        chunk_size=DEFAULT_CHUNK_SIZE,
        offset=DEFAULT_OFFSET,
        end=None,
    ):
        self.client = None
        self.endpoint = endpoint
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key
        self.filename = filename
        self.chunk_size = chunk_size
        self.offset = offset
        self.end = end
        self.log = logging.getLogger(__name__)
        self.original_filename = name
        self.content_length = 0
        self.total_length = 0
        self.content_type = "binary/octet-stream"
        self.last_modified = None
        self.etag = None
        self.file_object = None
        self.file_contents = None

    def __range_header(self):
        """Builds the outbound S3 Range header for the current offset/end."""
        if self.end is not None:
            return f"bytes={self.offset}-{self.end}"
        return f"bytes={self.offset}-"

    def connect(self):
        """Initialize procedure that can be recalled."""
        self.client = S3ClientFactory.get_client(
            endpoint=self.endpoint, access_key=self.access_key, secret_key=self.secret_key
        )
        try:
            request_arguments = {
                "Bucket": self.bucket,
                "Key": self.filename,
                "Range": self.__range_header(),
            }
            if self.etag is not None:
                request_arguments["IfMatch"] = self.etag
            self.file_object = self.client.get_object(**request_arguments)
            self.file_contents = self.file_object["Body"]
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "PreconditionFailed":
                self.log.error(
                    "Object s3://%s/%s changed during download.", self.bucket, self.filename
                )
            else:
                self.log.error("An S3 download stream error occurred: %s", error)
            return
        except KeyError as error:
            self.log.error("An S3 download stream error occurred: %s", error)
            return

        try:
            http_headers = self.file_object["ResponseMetadata"]["HTTPHeaders"]
            self.content_type = value_or(http_headers, "content-type", self.content_type)
            ## On a ranged request 'content-length' is the slice size, not the
            ## whole object; the total is only in 'content-range'.
            self.content_length = int(value_or(http_headers, "content-length", 0))
            self.etag = value_or(http_headers, "etag", None)
            self.total_length = self.__total_from_headers(http_headers)
            modified = datetime.strptime(
                value_or(http_headers, "last-modified", "Tue, 01 Jan 1980 12:00:00 GMT"),
                "%a, %d %b %Y %H:%M:%S %Z",
            )
            self.last_modified = (
                modified.year,
                modified.month,
                modified.day,
                modified.hour,
                modified.minute,
                modified.second,
            )
        except (KeyError, TypeError):
            self.log.warning("Could not read metadata for s3://%s/%s", self.bucket, self.filename)

    def __total_from_headers(self, http_headers):
        """Returns the total object size from 'content-range', else 'content-length'."""
        content_range = value_or(http_headers, "content-range", None)
        if content_range is not None and "/" in content_range:
            total = content_range.rsplit("/", 1)[1].strip()
            if total.isdigit():
                return int(total)
        return self.content_length

    def body(self):
        """Returns the request body to directly read from."""
        if self.file_contents is None:
            self.connect()

        return self.file_contents

    def iterator(self):
        """Returns an iterator to read the request body."""
        if self.file_contents is None:
            self.connect()

        return self.file_contents.iter_chunks(chunk_size=self.chunk_size)

    def close(self):
        """Closes the file stream and resets the internal state."""
        if self.file_contents is not None:
            self.file_contents.close()
        self.file_object = None
        self.file_contents = None
        self.content_length = 0
        self.total_length = 0
        self.content_type = "binary/octet-stream"
        self.last_modified = None
        self.etag = None
        self.client = None

    def reset(self, offset=DEFAULT_OFFSET):
        """Resets the S3 connection and attempt to continue reading at OFFSET.

        The previously seen ETag is kept so the reconnect is guarded with
        'IfMatch': serving bytes from a changed object corrupts the download.
        """
        etag = self.etag
        self.close()
        self.etag = etag
        self.offset = offset
        self.connect()

    def reset_range(self, offset=DEFAULT_OFFSET, end=None):
        """Resets the connection to read the inclusive byte range [OFFSET, END].

        The previously seen ETag is kept so the reconnect is guarded with
        'IfMatch': serving bytes from a changed object corrupts the download.
        """
        etag = self.etag
        self.close()
        self.etag = etag
        self.offset = offset
        self.end = end
        self.connect()


def s3_file_exists(endpoint, bucket, access_key, secret_key, filename):
    """Returns True when FILENAME exists in BUCKET, False otherwise."""
    try:
        client = S3ClientFactory.get_client(
            endpoint=endpoint, access_key=access_key, secret_key=secret_key
        )
        client.head_object(Bucket=bucket, Key=filename)
        return True
    except PartialCredentialsError:
        logger = logging.getLogger(__name__)
        logger.warning("Potential misconfiguration of S3 bucket '%s'.", bucket)
        return False
    except ClientError:
        return False


def s3_temporary_file(reader):
    """Downloads the S3 file from READER and returns the local filesystem path."""
    cached_filename = os.path.join(config.s3_cache_storage, str(uuid.uuid4()))
    with open(cached_filename, "wb") as output_stream:
        retries = 3
        while retries > 0:
            try:
                for chunk in reader.iterator():
                    output_stream.write(chunk)
                retries = 0
            except (ResponseStreamingError, ReadTimeoutError, IncompleteRead):
                logger = logging.getLogger(__name__)
                current_offset = reader.body().tell()
                reader.reset(offset=current_offset)
                retries -= 1
                if retries > 0:
                    logger.warning(
                        "Retrying to fetch after %s bytes of %s.",
                        current_offset,
                        reader.original_filename,
                    )
                    continue
                logger.error(
                    "Failed to fetch S3 object %s (%s) for ZIP.",
                    reader.original_filename,
                    reader.content_length,
                )
    reader.close()
    return cached_filename
