"""Collaborative-permission decision logic (framework-neutral).

No HTTP or framework types belong here: the API layer turns a denial into a
403, the git service into a 404.
"""

from djehuty.utils.convenience import value_or


def is_permitted(db, account_uuid, item, item_type, permissions) -> bool:
    """Whether the account may act on the item with the given permission(s).

    ``True`` for the owner (the item is not shared with them); for a shared item,
    ``True`` only when the collaborator's record grants every permission.

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
    if not permissions:
        return False  # ``all(... for _ in [])`` is vacuously True; deny instead.
    record = db.item_collaborative_permissions(item_type, item["uuid"], account_uuid)
    if isinstance(permissions, str):
        permissions = [permissions]
    return all(value_or(record, permission, False) for permission in permissions)
