"""ReviewService conversation store: rounds, comments, events, visibility."""

import pytest
from sqlalchemy.exc import IntegrityError

from djehuty.api.services.review import ReviewService
from djehuty.api.services.review.schema import metadata, review_round
from djehuty.services.sql import SqlDatabase

DS = "11111111-1111-4111-8111-111111111111"
REV = "22222222-2222-4222-8222-222222222222"
AUTH = "33333333-3333-4333-8333-333333333333"


@pytest.fixture
def svc(tmp_path):
    sql = SqlDatabase(f"sqlite:///{tmp_path / 'review.db'}")
    metadata.create_all(sql.engine)
    try:
        yield ReviewService(sql)
    finally:
        sql.dispose()


def test_open_draft_round_is_get_or_create(svc):
    first = svc.open_draft_round(DS, REV)
    second = svc.open_draft_round(DS, REV)
    assert first == second
    assert svc.draft_round(DS)["status"] == "draft"


def test_one_draft_round_per_dataset_is_enforced(svc):
    svc.open_draft_round(DS, REV)
    with pytest.raises(IntegrityError), svc.sql.begin() as conn:
        conn.execute(
            review_round.insert().values(dataset_uuid=DS, reviewer_account_uuid=REV, status="draft")
        )


def test_pending_comment_hidden_from_author_visible_to_reviewer(svc):
    comment_id = svc.add_comment(
        DS,
        REV,
        "scalar",
        "Please clarify the title.",
        target_key="title",
        field_value_snapshot="Old title",
    )
    svc.add_event(comment_id, AUTH, "reply", "Done.")
    svc.set_addressed(comment_id, AUTH, True)
    svc.set_resolved(comment_id, REV, True)

    reviewer = svc.conversation(DS, include_pending=True, include_internal=True)
    assert len(reviewer["comments"]) == 1
    comment = reviewer["comments"][0]
    assert comment["body"] == "Please clarify the title."
    assert comment["field_value_snapshot"] == "Old title"
    assert bool(comment["author_addressed"]) is True
    assert bool(comment["reviewer_resolved"]) is True
    # Events are the dialogue only (replies + state), not the reviewer's body.
    assert [e["kind"] for e in comment["events"]] == ["reply", "addressed", "resolved"]

    author = svc.conversation(DS, include_pending=False, include_internal=False)
    assert author["comments"] == []


def test_edit_comment_updates_body_and_marks_edited(svc):
    comment_id = svc.add_comment(DS, REV, "scalar", "Original.", target_key="title")
    assert svc.comment(comment_id)["updated_at"] is None
    svc.edit_comment(comment_id, "Revised with more detail.")
    edited = svc.comment(comment_id)
    assert edited["body"] == "Revised with more detail."
    assert edited["updated_at"] is not None


def test_delete_comment_removes_it(svc):
    comment_id = svc.add_comment(DS, REV, "scalar", "Remove me.", target_key="title")
    svc.delete_comment(comment_id)
    assert svc.comment(comment_id) is None


def test_submit_publishes_comments_and_hides_internal_notes(svc):
    svc.add_comment(DS, REV, "scalar", "Please revise.", target_key="title")
    svc.save_notes(DS, REV, general_notes="Overall looks good.", internal_notes="watch licence")
    submitted = svc.submit_round(DS, "request_changes")
    assert submitted["status"] == "submitted"
    assert submitted["outcome"] == "request_changes"

    author = svc.conversation(DS, include_pending=False, include_internal=False)
    assert len(author["comments"]) == 1
    assert author["rounds"][0]["general_notes"] == "Overall looks good."
    assert "internal_notes" not in author["rounds"][0]

    reviewer = svc.conversation(DS, include_pending=True, include_internal=True)
    assert reviewer["rounds"][0]["internal_notes"] == "watch licence"


def test_submit_without_draft_returns_none(svc):
    assert svc.submit_round(DS, "approve") is None
