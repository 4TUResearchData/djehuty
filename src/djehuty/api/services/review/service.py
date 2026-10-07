"""Conversation store for field-level review (rounds, comments, events, notes).

Thin SQLAlchemy Core layer over the shared relational engine
(``djehuty.services.sql.SqlDatabase``). Routers call this; it returns plain
dicts. Visibility (author vs reviewer pool) is enforced here in the queries --
the author never sees pending comments or internal notes.
"""

from datetime import datetime, timezone

from sqlalchemy import delete, func, insert, select, update

from djehuty.api.services.review.schema import (
    review_comment,
    review_comment_event,
    review_round,
)


def _row_to_dict(row):
    return dict(row._mapping) if row is not None else None


class ReviewService:
    """CRUD for the review conversation, keyed by dataset UUID."""

    def __init__(self, sql):
        self.sql = sql

    # -- rounds ---------------------------------------------------------------

    def draft_round(self, dataset_uuid):
        """Return the open draft round for a dataset, or None."""
        query = select(review_round).where(
            review_round.c.dataset_uuid == dataset_uuid,
            review_round.c.status == "draft",
        )
        with self.sql.connect() as conn:
            return _row_to_dict(conn.execute(query).first())

    def open_draft_round(self, dataset_uuid, reviewer_account_uuid):
        """Return the id of the dataset's draft round, creating it if absent.

        Pending comments are reviewer-pool-wide, so the first reviewer to draft
        on a dataset owns the round record; others add to the same round.
        """
        existing = self.draft_round(dataset_uuid)
        if existing is not None:
            return existing["id"]
        with self.sql.begin() as conn:
            result = conn.execute(
                insert(review_round).values(
                    dataset_uuid=dataset_uuid,
                    reviewer_account_uuid=reviewer_account_uuid,
                    status="draft",
                )
            )
            return result.inserted_primary_key[0]

    def save_notes(
        self, dataset_uuid, reviewer_account_uuid, general_notes=None, internal_notes=None
    ):
        """Save draft general/internal notes on the dataset's draft round."""
        round_id = self.open_draft_round(dataset_uuid, reviewer_account_uuid)
        with self.sql.begin() as conn:
            conn.execute(
                update(review_round)
                .where(review_round.c.id == round_id)
                .values(general_notes=general_notes, internal_notes=internal_notes)
            )
        return round_id

    def submit_round(self, dataset_uuid, outcome, general_notes=None, internal_notes=None):
        """Mark the draft round submitted with OUTCOME; publishes its comments.

        Comments already carry this round's id, so flipping the round to
        'submitted' publishes them atomically. Returns the submitted round dict,
        or None when there is no draft round.
        """
        draft = self.draft_round(dataset_uuid)
        if draft is None:
            return None
        values = {"status": "submitted", "outcome": outcome, "submitted_at": func.now()}
        if general_notes is not None:
            values["general_notes"] = general_notes
        if internal_notes is not None:
            values["internal_notes"] = internal_notes
        with self.sql.begin() as conn:
            conn.execute(
                update(review_round).where(review_round.c.id == draft["id"]).values(**values)
            )
            row = conn.execute(select(review_round).where(review_round.c.id == draft["id"])).first()
        return _row_to_dict(row)

    # -- comments -------------------------------------------------------------

    def add_comment(
        self,
        dataset_uuid,
        reviewer_account_uuid,
        target_type,
        body,
        target_key=None,
        target_label=None,
        field_value_snapshot=None,
    ):
        """Add a pending comment (a single editable body) to the draft round."""
        round_id = self.open_draft_round(dataset_uuid, reviewer_account_uuid)
        with self.sql.begin() as conn:
            result = conn.execute(
                insert(review_comment).values(
                    round_id=round_id,
                    dataset_uuid=dataset_uuid,
                    target_type=target_type,
                    target_key=target_key,
                    target_label=target_label,
                    field_value_snapshot=field_value_snapshot,
                    body=body,
                    created_by_account_uuid=reviewer_account_uuid,
                )
            )
            return result.inserted_primary_key[0]

    def comment(self, comment_id):
        """Return a comment row, or None."""
        with self.sql.connect() as conn:
            return _row_to_dict(
                conn.execute(
                    select(review_comment).where(review_comment.c.id == comment_id)
                ).first()
            )

    def edit_comment(self, comment_id, body):
        """Edit a comment's body and stamp updated_at (shows as 'edited')."""
        with self.sql.begin() as conn:
            conn.execute(
                update(review_comment)
                .where(review_comment.c.id == comment_id)
                .values(body=body, updated_at=datetime.now(timezone.utc))
            )

    def delete_comment(self, comment_id):
        """Delete a comment (and, by cascade, its reply events)."""
        with self.sql.begin() as conn:
            conn.execute(delete(review_comment).where(review_comment.c.id == comment_id))

    def add_event(self, comment_id, account_uuid, kind, body=None):
        """Append a reply/addressed/resolved/reopened event; returns its id."""
        with self.sql.begin() as conn:
            result = conn.execute(
                insert(review_comment_event).values(
                    comment_id=comment_id,
                    account_uuid=account_uuid,
                    kind=kind,
                    body=body,
                )
            )
            return result.inserted_primary_key[0]

    def edit_event(self, event_id, account_uuid, body):
        """Edit one's own reply. Returns True if a reply was updated."""
        with self.sql.begin() as conn:
            result = conn.execute(
                update(review_comment_event)
                .where(
                    review_comment_event.c.id == event_id,
                    review_comment_event.c.account_uuid == account_uuid,
                    review_comment_event.c.kind == "reply",
                )
                .values(body=body)
            )
            return result.rowcount > 0

    def delete_event(self, event_id, account_uuid):
        """Delete one's own reply. Returns True if a reply was deleted."""
        with self.sql.begin() as conn:
            result = conn.execute(
                delete(review_comment_event).where(
                    review_comment_event.c.id == event_id,
                    review_comment_event.c.account_uuid == account_uuid,
                    review_comment_event.c.kind == "reply",
                )
            )
            return result.rowcount > 0

    def set_addressed(self, comment_id, account_uuid, addressed):
        """Author toggle: mark a comment addressed (or not) + log the signal."""
        with self.sql.begin() as conn:
            conn.execute(
                update(review_comment)
                .where(review_comment.c.id == comment_id)
                .values(author_addressed=addressed)
            )
        if addressed:
            self.add_event(comment_id, account_uuid, "addressed")

    def set_resolved(self, comment_id, account_uuid, resolved):
        """Reviewer toggle: resolve/reopen a comment + log the state event."""
        with self.sql.begin() as conn:
            conn.execute(
                update(review_comment)
                .where(review_comment.c.id == comment_id)
                .values(reviewer_resolved=resolved)
            )
        self.add_event(comment_id, account_uuid, "resolved" if resolved else "reopened")

    # -- read model -----------------------------------------------------------

    def conversation(
        self, dataset_uuid, *, include_pending, include_internal, include_resolved=True
    ):
        """Return the review conversation for a dataset, filtered by role.

        Reviewer pool: everything. Author: only comments in *submitted* rounds,
        submitted general notes, never internal notes, and never comments the
        reviewer has resolved (``include_pending=False, include_internal=False,
        include_resolved=False``) -- a resolved comment is closed, so the author
        has nothing left to act on.
        """
        with self.sql.connect() as conn:
            round_query = select(review_round).where(review_round.c.dataset_uuid == dataset_uuid)
            if not include_pending:
                round_query = round_query.where(review_round.c.status == "submitted")
            rounds = [_row_to_dict(r) for r in conn.execute(round_query).all()]
            visible_round_ids = {r["id"] for r in rounds}

            comment_query = select(review_comment).where(
                review_comment.c.dataset_uuid == dataset_uuid
            )
            comments = [
                _row_to_dict(c)
                for c in conn.execute(comment_query).all()
                if c._mapping["round_id"] in visible_round_ids
                and (include_resolved or not c._mapping["reviewer_resolved"])
            ]

            events_by_comment = {}
            if comments:
                comment_ids = [c["id"] for c in comments]
                event_rows = conn.execute(
                    select(review_comment_event)
                    .where(review_comment_event.c.comment_id.in_(comment_ids))
                    .order_by(review_comment_event.c.created_at, review_comment_event.c.id)
                ).all()
                for event in event_rows:
                    events_by_comment.setdefault(event._mapping["comment_id"], []).append(
                        _row_to_dict(event)
                    )

        for comment in comments:
            comment["events"] = events_by_comment.get(comment["id"], [])
        if not include_internal:
            for review in rounds:
                review.pop("internal_notes", None)

        return {"rounds": rounds, "comments": comments}
