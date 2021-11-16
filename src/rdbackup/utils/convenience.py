def value_or_none (record, key):
    """Return the value of KEY or None."""
    try:
        return record[key]
    except KeyError:
        return None
