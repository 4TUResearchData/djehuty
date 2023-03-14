"""
This module provides a general cache mechanism to avoid duplicated queries
to the database server. Any object can be cached, as long as the object is
serializable by means of 'json.dumps' and deseralizeable by means of
'json.loads'.
"""

import glob
import os
import logging
import hashlib
import json

class CacheLayer:
    """This class provides the caching layer."""

    def __init__ (self, storage_path):
        self.storage     = storage_path
        self.log         = logging.getLogger(__name__)

    def make_key (self, input_string):
        """Procedure to turn 'input_string' into a short, unique identifier."""
        if input_string is None:
            return None

        md5 = hashlib.new ("md5", usedforsecurity=False)
        md5.update (input_string.encode('utf-8'))
        return md5.hexdigest()

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

    def cached_value (self, prefix, key):
        """Returns the cached value or None."""
        data = None
        try:
            filename = f"{self.storage}/{prefix}_{key}"
            with open(filename, "r",
                      encoding = "utf-8") as cache_file:
                cached = cache_file.read()
                data   = json.loads(cached)
                self.log.debug ("Cache hit for %s.", key)
        except OSError:
            self.log.debug ("No cached response for %s.", key)
        except json.decoder.JSONDecodeError:
            self.log.error ("Possible cache corruption at %s.", filename)

        return data

    def cache_value (self, prefix, key, value, query=None):
        """Procedure to store 'value' as a cache."""
        try:
            cache_filename = f"{self.storage}/{prefix}_{key}"
            cache_fd = os.open (cache_filename, os.O_WRONLY | os.O_CREAT, 0o600)
            with open(cache_fd, "w", encoding = "utf-8") as cache_file:
                cache_file.write(json.dumps(value))
                if os.name != 'nt':
                    os.fchmod (cache_fd, 0o400)

            if query is not None:
                query_filename = f"{self.storage}/{prefix}_{key}.sparql"
                query_fd = os.open (query_filename, os.O_WRONLY | os.O_CREAT, 0o600)
                with open(query_fd, "w", encoding = "utf-8") as query_file:
                    query_file.write(query)
                    if os.name != 'nt':
                        os.fchmod (query_fd, 0o400)
        except OSError:
            self.log.error ("Failed to save cache for %s.", key)

        return value

    def remove_cached_value (self, prefix, key):
        """Procedure to invalidate a uniquely identifiable cache item."""
        file_path = f"{self.storage}/{prefix}_{key}"
        try:
            os.remove(file_path)
        except FileNotFoundError:
            self.log.error ("Trying to remove %s multiple times.", file_path)

        return True

    def invalidate_by_prefix (self, prefix):
        """Procedure to remove all cache items belonging to 'prefix'."""
        for file_path in glob.glob(f"{self.storage}/{prefix}_*"):
            try:
                os.remove(file_path)
            except FileNotFoundError:
                self.log.error ("Trying to remove %s multiple times.", file_path)

        return True

    def invalidate_all (self):
        """Procedure to remove all cache items."""

        if not isinstance(self.storage, str):
            return False

        if self.storage in ("", "/"):
            return False

        files = glob.glob(f"{self.storage}/*")
        self.log.info ("Removing %d files.", len(files))
        for file_path in files:
            try:
                os.remove(file_path)
            except FileNotFoundError:
                self.log.error ("Trying to remove %s multiple times.", file_path)
            except IsADirectoryError:
                pass

        return True
