"""SQLAlchemy Core schema for the field-level review conversation.

One ``MetaData`` for the three ``review_*`` tables. Identifiers are UUID strings
(``String(36)``) generated application-side -- matching djehuty's identity model
(``dataset_uuid``/``account_uuid`` are UUIDs) and avoiding enumerable sequential
keys in the API. Types stay portable so the unit tests run the migration on
SQLite while production uses PostgreSQL.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    String,
    Table,
    Text,
    false,
    func,
)

metadata = MetaData()


def _new_uuid():
    return str(uuid.uuid4())


def _utcnow():
    # Application-side timestamp with microsecond precision so the chronological
    # thread order is stable on SQLite too (server CURRENT_TIMESTAMP is only
    # second-granularity, and UUID ids give no creation-order tiebreaker).
    return datetime.now(timezone.utc)


# One open draft round per dataset at a time; submitting it publishes its
# comments. Outcome is null until submit.
review_round = Table(
    "review_round",
    metadata,
    Column("id", String(36), primary_key=True, default=_new_uuid),
    Column("dataset_uuid", String(36), nullable=False),
    Column("reviewer_account_uuid", String(36), nullable=False),
    Column("status", String(16), nullable=False, server_default="draft"),
    Column("outcome", String(16), nullable=True),
    Column("general_notes", Text, nullable=True),
    Column("internal_notes", Text, nullable=True),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    ),
    Column("submitted_at", DateTime(timezone=True), nullable=True),
)

# At most one draft round per dataset (partial unique index).
Index(
    "ix_review_round_one_draft",
    review_round.c.dataset_uuid,
    unique=True,
    postgresql_where=(review_round.c.status == "draft"),
    sqlite_where=(review_round.c.status == "draft"),
)

review_comment = Table(
    "review_comment",
    metadata,
    Column("id", String(36), primary_key=True, default=_new_uuid),
    Column(
        "round_id", String(36), ForeignKey("review_round.id", ondelete="CASCADE"), nullable=False
    ),
    Column("dataset_uuid", String(36), nullable=False),
    Column("target_type", String(32), nullable=False),
    Column("target_key", String(255), nullable=True),
    # Human label of the commented field/entity, captured at comment time (e.g.
    # "Title" or "Funding: Horizon 2020") so any view can show it without the
    # dataset's entity list.
    Column("target_label", Text, nullable=True),
    Column("field_value_snapshot", Text, nullable=True),
    # The reviewer's comment text: a single editable body, not a reply thread.
    Column("body", Text, nullable=True),
    Column("author_addressed", Boolean, nullable=False, server_default=false()),
    Column("reviewer_resolved", Boolean, nullable=False, server_default=false()),
    Column("created_by_account_uuid", String(36), nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    ),
    # Set when the reviewer edits the body; surfaces an "edited" marker.
    Column("updated_at", DateTime(timezone=True), nullable=True),
    Index("ix_review_comment_dataset", "dataset_uuid"),
    Index("ix_review_comment_round", "round_id"),
)

# Flat chronological thread: replies and resolution history interleave in
# creation order (body is null for state events).
review_comment_event = Table(
    "review_comment_event",
    metadata,
    Column("id", String(36), primary_key=True, default=_new_uuid),
    Column(
        "comment_id",
        String(36),
        ForeignKey("review_comment.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("account_uuid", String(36), nullable=False),
    Column("kind", String(16), nullable=False),
    Column("body", Text, nullable=True),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    ),
    Index("ix_review_comment_event_comment", "comment_id"),
)
