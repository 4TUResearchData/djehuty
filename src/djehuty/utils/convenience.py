"""
This module provides convenience functions that can be used throughout
the codebase.
"""

def value_or (record, key, other):
    """Return the value of KEY or OTHER."""
    try:
        return record[key]
    except KeyError:
        return other
    except TypeError:
        return other

def value_or_none (record, key):
    """Return the value of KEY or None."""
    return value_or (record, key, None)

def to_camel (name):
    splitted = name.split("_")
    output = ""
    for part in splitted:
        output += part.capitalize()

    return output
