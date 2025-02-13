"""This module implements interaction with an S3 endpoint."""

import logging

try:
    import boto3
    from botocore.exceptions import ClientError, PartialCredentialsError
except (ImportError, ModuleNotFoundError):
    pass

class S3DownloadStreamer:
    """Generator to stream the contents of a file stored in S3."""

    def __init__ (self, endpoint, bucket, access_key, secret_key, filename, chunk_size=8192):
        self.log = logging.getLogger(__name__)
        self.chunk_size = chunk_size
        self.client = boto3.client ("s3", endpoint_url    = endpoint,
                                    aws_access_key_id     = access_key,
                                    aws_secret_access_key = secret_key)
        try:
            self.file_object   = self.client.get_object (Bucket = bucket,
                                                         Key    = filename)
            self.file_contents = self.file_object["Body"]
        except (ClientError, KeyError) as error:
            self.log.error ("An S3 download stream error occurred: %s", error)

    def __iter__ (self):
        return self

    def __next__ (self):
        chunk = self.file_contents.read (self.chunk_size)
        if chunk == b'':
            raise StopIteration
        return chunk

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
