"""Business logic for physical sample operations."""

from djehuty.web import validator


class PhysicalSampleService:
    """Service layer for physical sample operations."""

    def __init__(self, db):
        self.db = db

    def _resolve_physical_sample(self, identifier, is_latest=False, is_published=False):
        """Resolve a physical sample by container UUID, or return None."""
        if not validator.is_valid_uuid(identifier):
            return None
        try:
            return self.db.physical_samples(
                container_uuid=identifier,
                is_latest=is_latest,
                is_published=is_published,
                limit=1,
            )[0]
        except IndexError:
            return None
