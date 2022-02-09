"""
This module provides an atomic ID iterator.
"""

from multiprocessing import Value

class IdGenerator:
    """
    This class implements atomic ID iterators to make the
    relational database style of assigning numeric IDs to records
    work for the RDF model.

    This class implements atomic iterators for the lifetime of a
    single run, so the user must set the initial state _before_
    serving/performing any state-changing operations.
    """

    def __init__ (self):
        self.counters = {
            "article"          : Value('i', 0),
            "article_category" : Value('i', 0),
            "article_author"   : Value('i', 0),
            "article_file"     : Value('i', 0),
            "collection"       : Value('i', 0),
            "collection_author" : Value('i', 0),
            "collection_article" : Value('i', 0),
            "author"           : Value('i', 0),
            "account"          : Value('i', 0),
            "file"             : Value('i', 0),
            "funding"          : Value('i', 0),
            "category"         : Value('i', 0),
            "project"          : Value('i', 0),
            "timeline"         : Value('i', 0),
            "institution"      : Value('i', 0),
            "tag"              : Value('i', 0),
            "reference"        : Value('i', 0),
            "custom_field"     : Value('i', 0),
            "private_links"    : Value('i', 0),
            "session"          : Value('i', 0)
        }

    def set_id (self, item_id, item_type):
        """Procedure to set the current value of ITEM_ID."""
        self.counters[item_type].value = item_id
        return True

    def next_id (self, item_type):
        """Returns the next ITEM_ID value to assign to an article."""
        self.counters[item_type].value += 1
        return self.counters[item_type].value

    def current_id (self, item_type):
        """Returns the current ID value."""
        return self.counters[item_type].value

    def keys (self):
        """Returns a list of counters."""
        return list(self.counters.keys())
