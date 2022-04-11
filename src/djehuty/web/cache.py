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

    def make_key (self, input_string):
        """Procedure to turn 'input_string' into a short, unique identifier."""
        if input_string is None:
            return None

        return hashlib.md5(input_string.encode('utf-8')).hexdigest()

    def cache_is_ready(self):
        """Procedure to set up and test the ability to cache."""
        if self.storage is None:
            return False

        os.makedirs(self.storage, mode=0o700, exist_ok=True)
        return os.path.isdir(self.storage)

    def cached_value (self, prefix, key):
        """Returns the cached value or None."""
        data = None
        try:
            with open(f"{self.storage}/{prefix}_{key}", "r",
                      encoding = "utf-8") as file:
                cached = file.read()
                data = json.loads(cached)
                logging.debug("Cache hit for %s.", key)
        except OSError:
            logging.debug("No cached response for %s.", key)

        return data

    def cache_value (self, prefix, key, value):
        """Procedure to store 'value' as a cache."""
        try:
            with open(f"{self.storage}/{prefix}_{key}", "w",
                      encoding = "utf-8") as file:
                file.write(json.dumps(value))
        except OSError:
            logging.error("Failed to save cache for %s.", key)

        return value

    def remove_cached_value (self, prefix, key):
        """Procedure to invalidate a uniquely identifiable cache item."""
        file_path = f"{self.storage}/{prefix}_{key}"
        try:
            os.remove(file_path)
        except FileNotFoundError:
            logging.error ("Trying to remove %s multiple times.", file_path)

        return True

    def invalidate_by_prefix (self, prefix):
        """Procedure to remove all cache items belonging to 'prefix'."""
        for file_path in glob.glob(f"{self.storage}/{prefix}_*"):
            try:
                os.remove(file_path)
            except FileNotFoundError:
                logging.error ("Trying to remove %s multiple times.", file_path)

        return True

    def invalidate_all (self):
        """Procedure to remove all cache items."""
        for file_path in glob.glob(f"{self.storage}/*"):
            try:
                os.remove(file_path)
            except FileNotFoundError:
                logging.error ("Trying to remove %s multiple times.", file_path)

        return True
