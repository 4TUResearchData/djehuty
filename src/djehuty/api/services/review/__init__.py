"""Field-level dataset review: the PostgreSQL conversation store.

The review *lifecycle* stays in Virtuoso (``is_under_review``, ``assigned_to``,
``last_seen_by_reviewer``, approved/declined); only the *conversation* (comment
threads, replies, two-sided resolution, rounds, general/internal notes, value
snapshots) lives here, in the shared relational store from ``djehuty.services.sql``.
The join key is the dataset UUID. Nothing here imports ``djehuty.web.wsgi``.
"""

from djehuty.api.services.review.schema import metadata
from djehuty.api.services.review.service import ReviewService

__all__ = ["ReviewService", "metadata"]
