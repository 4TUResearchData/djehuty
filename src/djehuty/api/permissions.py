"""Collaborative-permission enforcement for private API endpoints.

The decision logic lives in the framework-neutral
``djehuty.services.permissions``; this module turns a denial into an HTTP 403
(``ForbiddenError``). Faithful port of the legacy
``ApiServer.__needs_collaborative_permissions``: a no-op for the owner, and a
403 for a collaborator who lacks the permission an action requires.

(The git endpoints deliberately do *not* use this wrapper: legacy hides a git
permission denial as 404, so the git service calls
``djehuty.services.permissions.is_permitted`` directly and returns ``None``.)
"""

from djehuty.api.exceptions import ForbiddenError
from djehuty.services.permissions import is_permitted


def enforce_collaborative_permissions(db, account_uuid, item, item_type, permissions):
    """Raise :class:`ForbiddenError` unless the account holds the permission(s).

    No-op for the owner (the item is not shared with them), as in legacy.
    """
    if not is_permitted(db, account_uuid, item, item_type, permissions):
        raise ForbiddenError(
            f"account:{account_uuid} attempted an action requiring "
            f"{permissions!r} on this {item_type}."
        )
