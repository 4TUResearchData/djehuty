"""Initial field-level review schema (rounds, comments, events).

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-07

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DRAFT = sa.text("status = 'draft'")


def upgrade() -> None:
    op.create_table(
        "review_round",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("dataset_uuid", sa.String(length=36), nullable=False),
        sa.Column("reviewer_account_uuid", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("outcome", sa.String(length=16), nullable=True),
        sa.Column("general_notes", sa.Text(), nullable=True),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_review_round_one_draft",
        "review_round",
        ["dataset_uuid"],
        unique=True,
        postgresql_where=_DRAFT,
        sqlite_where=_DRAFT,
    )

    op.create_table(
        "review_comment",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "round_id",
            sa.String(length=36),
            sa.ForeignKey("review_round.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dataset_uuid", sa.String(length=36), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_key", sa.String(length=255), nullable=True),
        sa.Column("target_label", sa.Text(), nullable=True),
        sa.Column("field_value_snapshot", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("author_addressed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reviewer_resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_account_uuid", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_review_comment_dataset", "review_comment", ["dataset_uuid"])
    op.create_index("ix_review_comment_round", "review_comment", ["round_id"])

    op.create_table(
        "review_comment_event",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "comment_id",
            sa.String(length=36),
            sa.ForeignKey("review_comment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_uuid", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_review_comment_event_comment", "review_comment_event", ["comment_id"])


def downgrade() -> None:
    op.drop_table("review_comment_event")
    op.drop_table("review_comment")
    op.drop_index("ix_review_round_one_draft", table_name="review_round")
    op.drop_table("review_round")
