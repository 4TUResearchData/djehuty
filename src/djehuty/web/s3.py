"""This module implements interaction with an S3 endpoint."""

import logging
import uuid
import os
from datetime import datetime
from djehuty.web.config import config
from djehuty.utils.convenience import value_or

try:
    import boto3
    from botocore.exceptions import ClientError, PartialCredentialsError
    from botocore.exceptions import ResponseStreamingError, ReadTimeoutError
    from botocore.config import Config
    from urllib3.exceptions import IncompleteRead
except (ImportError, ModuleNotFoundError):
    pass

class S3DownloadStreamer:
    """Generator to stream the contents of a file stored in S3."""

    def __init__ (self, endpoint, bucket, access_key, secret_key, filename, name, chunk_size=32768, offset=0):
        self.client = None
        self.endpoint = endpoint
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key
        self.filename = filename
        self.chunk_size = chunk_size
        self.offset = offset
        self.log = logging.getLogger (__name__)
        self.chunk_size = chunk_size
        self.original_filename = name
        self.content_length = 0
        self.content_type = "binary/octet-stream"
        self.last_modified = None
        self.file_object = None
        self.file_contents = None
        self.boto_config = Config(retries = { "total_max_attempts": 30,
                                              "mode": "standard" },
                                  max_pool_connections = 1,
                                  read_timeout = 120)

    def connect (self):
        """Initialize procedure that can be recalled."""
        self.client = boto3.client ("s3", endpoint_url    = self.endpoint,
                                    aws_access_key_id     = self.access_key,
                                    aws_secret_access_key = self.secret_key,
                                    config                = self.boto_config)
        try:
            self.file_object   = self.client.get_object (Bucket = self.bucket,
                                                         Key    = self.filename,
                                                         Range  = f"bytes={self.offset}-")
            self.file_contents = self.file_object["Body"]
        except (ClientError, KeyError) as error:
            self.log.error ("An S3 download stream error occurred: %s", error)

        try:
            http_headers = self.file_object["ResponseMetadata"]["HTTPHeaders"]
            self.content_type   = value_or (http_headers, "content-type", self.content_type)
            self.content_length = int(value_or (http_headers, "content-length", 0))
            modified = datetime.strptime (value_or (http_headers, "last-modified",
                                                    "Tue, 01 Jan 1980 12:00:00 GMT"),
                                          "%a, %d %b %Y %H:%M:%S %Z")
            self.last_modified  = (modified.year, modified.month, modified.day,
                                   modified.hour, modified.minute, modified.second)
        except (KeyError, TypeError):
            self.log.warning ("Could not read metadata for s3://%s/%s",
                              self.bucket, self.filename)

    def body (self):
        """Returns the request body to directly read from."""
        if self.file_contents is None:
            self.connect ()

        return self.file_contents

    def iterator (self):
        """Returns an iterator to read the request body."""
        if self.file_contents is None:
            self.connect ()

        return self.file_contents.iter_chunks (chunk_size=self.chunk_size)

    def close (self):
        """Closes the S3 client and resets the internal state."""
        self.file_contents.close()
        self.client.close()
        self.file_object = None
        self.file_contents = None
        self.content_length = 0
        self.content_type = "binary/octet-stream"
        self.last_modified = None

    def reset (self, offset=0):
        """Resets the S3 connection and ttempt to contunie reading at OFFSET."""
        self.close ()
        self.offset = offset
        self.connect ()

def s3_file_exists (endpoint, bucket, access_key, secret_key, filename):
    """Returns True when FILENAME exists in BUCKET, False otherwise."""
    try:
        client = boto3.client("s3", endpoint_url=endpoint,
                              aws_access_key_id=access_key,
                              aws_secret_access_key=secret_key)
        client.head_object (Bucket=bucket, Key=filename)
        return True
    except PartialCredentialsError:
        logger = logging.getLogger(__name__)
        logger.warning ("Potential misconfiguration of S3 bucket '%s'.", bucket)
        return False
    except ClientError:
        return False

def s3_temporary_file (reader):
    """Downloads the S3 file from READER and returns the local filesystem path."""
    cached_filename = os.path.join (config.s3_cache_storage, str(uuid.uuid4()))
    with open (cached_filename, "wb") as output_stream:
        retries = 3
        while retries > 0:
            try:
                for chunk in reader.iterator():
                    output_stream.write (chunk)
                retries = 0
            except (ResponseStreamingError, ReadTimeoutError, IncompleteRead):
                logger = logging.getLogger (__name__)
                current_offset = reader.body().tell()
                reader.reset (offset = current_offset)
                retries -= 1
                if retries > 0:
                    logger.warning ("Retrying to fetch after %s bytes of %s.",
                                    current_offset, reader.original_filename)
                    continue
                logger.error ("Failed to fetch S3 object %s (%s) for ZIP.",
                              reader.original_filename,
                              reader.content_length)
    reader.close()
    return cached_filename
