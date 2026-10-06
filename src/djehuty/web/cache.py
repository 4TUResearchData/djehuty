"""Caching layer to avoid duplicated queries to the database server.

Callers reach the cache through the CacheBackend surface on the shared 'db'
object, so the on-disk FileCacheBackend (the default) and the shared
ValkeyCacheBackend are interchangeable. Cached objects must be JSON-serialisable.
"""

import glob
import hashlib
import json
import logging
import os


class CacheBackend:
    """Interface shared by all cache backends."""

    def make_key(self, input_string):
        """Procedure to turn 'input_string' into a short, unique identifier."""
        if input_string is None:
            return None

        md5 = hashlib.new("md5", usedforsecurity=False)
        md5.update(input_string.encode("utf-8"))
        return md5.hexdigest()

    def cache_is_ready(self):
        """Procedure to set up and test the ability to cache."""
        raise NotImplementedError

    def cached_value(self, prefix, key, is_raw=False):
        """Returns the cached value or None."""
        raise NotImplementedError

    def cache_value(self, prefix, key, value, query=None, is_raw=False):
        """Procedure to store 'value' as a cache."""
        raise NotImplementedError

    def invalidate_by_prefix(self, prefix):
        """Procedure to remove all cache items belonging to 'prefix'."""
        raise NotImplementedError

    def invalidate_all(self):
        """Procedure to remove all cache items."""
        raise NotImplementedError


class FileCacheBackend(CacheBackend):
    """This class provides an on-disk caching layer."""

    def __init__(self, storage_path):
        self.storage = storage_path
        self.log = logging.getLogger(__name__)

    def cache_is_ready(self):
        """Procedure to set up and test the ability to cache."""
        if self.storage is None:
            return False

        try:
            os.makedirs(self.storage, mode=0o700, exist_ok=True)
            return os.path.isdir(self.storage)
        except PermissionError:
            pass

        return False

    def cached_value(self, prefix, key, is_raw=False):
        """Returns the cached value or None."""
        try:
            filename = os.path.join(self.storage, f"{prefix}_{key}")
            with open(filename, "r", encoding="utf-8") as cache_file:
                cached = cache_file.read()
                if is_raw:
                    return cached
                return json.loads(cached)
        except OSError:
            self.log.debug("No cached response for %s.", key)
        except json.decoder.JSONDecodeError:
            self.log.error("Possible cache corruption at %s.", filename)

        return None

    def cache_value(self, prefix, key, value, query=None, is_raw=False):
        """Procedure to store 'value' as a cache."""
        try:
            cache_filename = os.path.join(self.storage, f"{prefix}_{key}")
            cache_fd = os.open(cache_filename, os.O_WRONLY | os.O_CREAT, 0o600)
            with open(cache_fd, "w", encoding="utf-8") as cache_file:
                if is_raw:
                    cache_file.write(value)
                else:
                    cache_file.write(json.dumps(value))
                if os.name != "nt":
                    os.fchmod(cache_fd, 0o400)  # pylint: disable=no-member

            if query is not None:
                query_filename = os.path.join(self.storage, f"{prefix}_{key}.sparql")
                query_fd = os.open(query_filename, os.O_WRONLY | os.O_CREAT, 0o600)
                with open(query_fd, "w", encoding="utf-8") as query_file:
                    query_file.write(query)
                    if os.name != "nt":
                        os.fchmod(query_fd, 0o400)  # pylint: disable=no-member
        except OSError:
            self.log.warning("Failed to save cache for %s.", key)

        return value

    def invalidate_by_prefix(self, prefix):
        """Procedure to remove all cache items belonging to 'prefix'."""
        for file_path in glob.glob(os.path.join(self.storage, f"{prefix}_*")):
            try:
                os.remove(file_path)
            except FileNotFoundError:
                self.log.warning("Trying to remove %s multiple times.", file_path)

        return True

    def invalidate_all(self):
        """Procedure to remove all cache items."""

        if not isinstance(self.storage, str):
            return False

        if self.storage in ("", "/"):
            return False

        files = glob.glob(os.path.join(self.storage, "*"))
        self.log.info("Removing %d files.", len(files))
        for file_path in files:
            try:
                os.remove(file_path)
            except FileNotFoundError:
                self.log.warning("Trying to remove %s multiple times.", file_path)
            except IsADirectoryError:
                pass

        return True


# Backwards-compatible alias for the historical default backend.
CacheLayer = FileCacheBackend


def build_cache_backend(config, file_backend):
    """Return the configured cache backend ('file' default, or Valkey)."""
    if getattr(config, "cache_backend_type", "file") == "valkey":
        from djehuty.web.cache_valkey import ValkeyCacheBackend

        return ValkeyCacheBackend(config)
    return file_backend
