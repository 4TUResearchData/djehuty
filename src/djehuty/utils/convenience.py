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
    """Return a camel-casing string for a snake-casing string."""
    splitted = name.split("_")
    output = ""
    for part in splitted:
        output += part.capitalize()

    return output

def pretty_print_size (num_bytes):
    """Return pretty-printed file size."""

    output = ""
    if not isinstance(num_bytes, int):
        output = "0B"
    elif num_bytes < 1000:
        output = f"{num_bytes}B"
    elif num_bytes < 1000000:
        output = f"{num_bytes/1000:.2f}KB"
    elif num_bytes < 1000000000:
        output = f"{num_bytes/1000000:.2f}MB"
    elif num_bytes < 1000000000000:
        output = f"{num_bytes/1000000000:.2f}GB"
    else:
        output = f"{num_bytes/1000000000000:.2f}TB"

    return output
