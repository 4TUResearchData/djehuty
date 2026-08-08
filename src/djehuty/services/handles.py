"""Handle.net PID registration for published files.

Standalone port of the legacy wsgi ``__register_file_handle``. Registers a
file's download URL with the configured handle server and returns False when
handles are not configured, so callers can treat registration as best-effort.
"""

import logging

import requests

from djehuty.web.config import config

logger = logging.getLogger(__name__)


def register_file_handle(handle, download_url):
    """Register a file handle; return True on success, False otherwise."""
    if config.handle_url is None:
        return False

    handle_data = {
        "values": [
            {
                "index": config.handle_index,
                "type": "URL",
                "data": {"format": "string", "value": download_url},
            }
        ]
    }
    http_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": 'Handle clientCert="true"',
    }

    try:
        response = requests.put(
            f"{config.handle_url}/{handle}",
            headers=http_headers,
            cert=(config.handle_certificate_path, config.handle_private_key_path),
            timeout=60,
            json=handle_data,
        )
        if response.status_code == 201:
            logger.info("Handle %s created.", handle)
            return True
        logger.error("Handle registration failed with %s (%s)", response.status_code, response.text)
    except requests.exceptions.ConnectionError as error:
        logger.error("Failed to create handle %s due to a connection error.", handle)
        logger.error("Error: %s", error)

    return False
