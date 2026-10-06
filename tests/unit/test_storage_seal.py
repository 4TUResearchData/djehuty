"""Unit tests for the storage-maintenance sealed-path predicate."""

import pytest

from djehuty.storage_seal import is_sealed_storage_path

SEALED = [
    "/file/abc/def",
    "/ndownloader/items/abc/versions/1",
    "/iiif/v3/uuid/full/max/0/default.jpg",
    "/iiif/v3/uuid/info.json",
    "/thumbnails/abc.jpg",
    "/v3/datasets/123/upload",
    "/v3/datasets/uuid/update-thumbnail",
    "/v3/datasets/uuid.git/info/refs",
    "/v3/datasets/123/publish",
    "/v3/datasets/uuid/repair_md5s",
    "/v3/profile/picture",
    "/v3/profile/picture/uuid",
    "/v3/admin/files-integrity-statistics",
    "/v2/articles/123/versions/2/update_thumb",
]

ALLOWED = [
    "/",
    "/robots.txt",
    "/v3/datasets",
    "/v3/datasets/123",
    "/v3/datasets/123/submit-for-review",
    "/v3/file/uuid",
    "/v2/articles/123/files",
    "/v2/articles/123/files/456",
    "/v3/datasets/123/image-files",
]


@pytest.mark.parametrize("path", SEALED)
def test_sealed_paths(path):
    assert is_sealed_storage_path(path) is True


@pytest.mark.parametrize("path", ALLOWED)
def test_allowed_paths(path):
    assert is_sealed_storage_path(path) is False
