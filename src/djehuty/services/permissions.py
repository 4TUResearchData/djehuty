"""Collaborative-permission decision logic (framework-neutral).

Shared by the API layer -- ``djehuty.api.permissions`` turns a denial into an
HTTP 403 -- and the git service, which turns a denial into ``None`` -> 404,
matching the legacy git handlers. No HTTP or framework types belong here.
"""

from djehuty.utils.convenience import value_or


def is_permitted(db, account_uuid, item, item_type, permissions) -> bool:
    """Whether the account may act on the item with the given permission(s).

    Returns ``True`` for the owner -- the item is not shared with them, so no
    enforcement applies, exactly as in legacy. For a shared item, returns
    ``True`` only when the collaborator's record grants *every* required
    permission.

    Args:
        db: database interface (provides ``item_collaborative_permissions``).
        account_uuid: the authenticated account's UUID.
        item: the resolved dataset/collection/file record.
        item_type: ``"dataset"``, ``"collection"`` or ``"file"``.
        permissions: a permission name or list, e.g. ``"metadata_edit"``.
    """
    if not value_or(item, "is_shared_with_me", False):
        return True
    if "uuid" not in item:
        return False
    record = db.item_collaborative_permissions(item_type, item["uuid"], account_uuid)
    if isinstance(permissions, str):
        permissions = [permissions]
    return all(value_or(record, permission, False) for permission in permissions)
