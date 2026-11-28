"""Version numbers for published datasets and collections.

A number is handed out once per container and never again, retracted versions included.
"""


def next_version(db, container_uuid):
    """Return the version number the container's draft gets when published."""
    return db.highest_version(container_uuid) + 1
