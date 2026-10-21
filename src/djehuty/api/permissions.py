"""Collaborative-permission enforcement for private API endpoints.

Wraps the framework-neutral ``djehuty.services.permissions`` decision logic,
turning a denial into an HTTP 403 (``ForbiddenError``).
"""

from djehuty.api.exceptions import ForbiddenError
from djehuty.services.permissions import is_permitted
from djehuty.utils.convenience import value_or

#: Sentinel permission that only the owner satisfies; no collaborator flag grants it.
OWNER_ONLY = "owner_only"


def enforce_collaborative_permissions(db, account_uuid, item, item_type, permissions):
    """Raise :class:`ForbiddenError` unless the account holds the permission(s).

    No-op for the owner. :data:`OWNER_ONLY` denies every collaborator.
    """
    if permissions == OWNER_ONLY:
        enforce_owner(account_uuid, item, item_type)
        return
    if not is_permitted(db, account_uuid, item, item_type, permissions):
        raise ForbiddenError(
            f"account:{account_uuid} attempted an action requiring "
            f"{permissions!r} on this {item_type}."
        )


def enforce_owner(account_uuid, item, item_type):
    """Raise :class:`ForbiddenError` for any collaborator; no-op for the owner."""
    if value_or(item, "is_shared_with_me", False):
        raise ForbiddenError(
            f"collaborator account:{account_uuid} attempted an owner-only "
            f"action on this {item_type}."
        )
