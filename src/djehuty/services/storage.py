"""
Shared storage helpers.

Extracted from ``djehuty.web.wsgi`` so the FastAPI handlers can resolve
file locations and write thumbnails without depending on the legacy
``ApiServer`` instance. The functions here are deliberately stateless —
they accept the file-metadata dict and rely only on the ``djehuty.web.config``
module for storage paths, S3 buckets, etc.
"""

from __future__ import annotations

import os

from djehuty.utils.convenience import value_or
from djehuty.web import s3
from djehuty.web.config import config

_ALLOWED_QUIRKY_CHARS = ".0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz"


def quirky_filename(path: str | None, file_id, name: str) -> str:
    """Return the legacy-quirky filename path for the given parameters.

    Used by storage backends that store pre-djehuty files under a sanitised
    ``<path>/<file_id>/<name>`` layout.
    """
    sanitised = "".join(ch for ch in name if ch in _ALLOWED_QUIRKY_CHARS)
    if path is None:
        path = ""
    return os.path.join(path, str(file_id), sanitised)


def filesystem_location(file_info: dict):
    """Resolve the filesystem path (or S3 streamer) for ``file_info``.

    Returns the path string or an :class:`s3.S3DownloadStreamer` on success,
    or ``None`` if no storage backend has the file.
    """
    # ---- New-style storage configuration (``config.storage_locations``).
    if config.storage_locations:
        for location in config.storage_locations:
            if "filename" in file_info:
                candidate = os.path.join(location["path"], file_info["filename"])
                if os.path.isfile(candidate):
                    return candidate
            elif "id" in file_info:
                candidate = os.path.join(location["path"], str(file_info["id"]), file_info["name"])
                if value_or(location, "quirks", False):
                    candidate = quirky_filename(
                        location["path"], file_info["id"], file_info["name"]
                    )
                if os.path.isfile(candidate):
                    return candidate

        # S3 buckets — only consulted in the new-style configuration.
        for _, bucket in config.s3_buckets.items():
            filename = f"{file_info['container_uuid']}_{file_info['uuid']}"
            if bucket["quirks-enabled"] and "id" in file_info:
                filename = quirky_filename("", file_info["id"], file_info["name"])

            if s3.s3_file_exists(
                bucket["endpoint"],
                bucket["name"],
                bucket["key-id"],
                bucket["secret-key"],
                filename,
            ):
                return s3.S3DownloadStreamer(
                    bucket["endpoint"],
                    bucket["name"],
                    bucket["key-id"],
                    bucket["secret-key"],
                    filename,
                    file_info["name"],
                )

    # ---- Historical configuration (``primary/secondary-storage-root``).
    if "filesystem_location" in file_info:
        if os.path.isfile(file_info["filesystem_location"]):
            return file_info["filesystem_location"]

    if "id" in file_info:
        filename = os.path.join(config.secondary_storage, str(file_info["id"]), file_info["name"])
        if config.secondary_storage_quirks:
            filename = quirky_filename(config.secondary_storage, file_info["id"], file_info["name"])
        if os.path.isfile(filename):
            return filename

    return None
