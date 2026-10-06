"""Which request paths are sealed while storage-maintenance is on.

Pure logic, no framework imports. Covers every byte-backed surface across both
HTTP stacks: file upload/download, zip, thumbnails, avatars, IIIF, git, the
file-integrity tooling, and publish (which reads file sizes/checksums). Sealing
is by path and method-agnostic -- these are all storage operations.
"""

import re

# Legacy-only byte routes, matched by prefix.
_SEALED_PREFIXES = (
    "/file/",
    "/ndownloader/",
    "/iiif/",
    "/thumbnails/",
)

# New-stack storage routes (and publish), matched by pattern.
_SEALED_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"^/v3/datasets/[^/]+/upload",
        r"^/v3/datasets/[^/]+/update-thumbnail",
        r"^/v3/datasets/[^/]+\.git",
        r"^/v3/datasets/[^/]+/publish$",
        r"^/v3/datasets/[^/]+/repair_md5s",
        r"^/v3/profile/picture",
        r"^/v3/admin/files-integrity-statistics",
        r"^/v2/articles/[^/]+/versions/[^/]+/update_thumb",
    )
)


def is_sealed_storage_path(path: str) -> bool:
    """Return True when PATH is a byte-backed route sealed during maintenance."""
    if any(path.startswith(prefix) for prefix in _SEALED_PREFIXES):
        return True
    return any(pattern.match(path) for pattern in _SEALED_PATTERNS)
