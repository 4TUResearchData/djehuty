"""Field-level review conversation endpoints for the v3 API.

Thin handlers over ``ReviewService`` (the PostgreSQL conversation store). The
RDF lifecycle is untouched here except that approve/reject reuse the extracted
publish/decline cores in ``publishing.py``. The feature self-disables (404) when
off or without a SQL store, so the author overlay renders nothing.
"""

import logging

from fastapi import APIRouter, Depends, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from djehuty.api.dependencies import (
    get_current_account,
    get_db,
    get_sql,
    get_token,
    require_auth,
    resolve_reviewer_context,
)
from djehuty.api.exceptions import ForbiddenError, InvalidInputError, NotFoundError
from djehuty.api.models.common import ErrorResponse
from djehuty.api.models.review import (
    AddressedRequest,
    CommentCreateRequest,
    CommentEditRequest,
    NotesRequest,
    ReplyRequest,
    ResolveRequest,
    SubmitRequest,
)
from djehuty.api.services.review import ReviewService
from djehuty.api.v3._shared import _ok
from djehuty.api.v3.datasets._shared import DatasetId, _resolve_any_dataset, _resolve_dataset
from djehuty.utils.convenience import value_or
from djehuty.utils.rdf import uri_to_uuid
from djehuty.web.config import config

router = APIRouter(tags=["V3 / Datasets / Review"])
logger = logging.getLogger(__name__)


def _get_review_service(sql=Depends(get_sql)) -> ReviewService:
    """Return a ReviewService, or 404 when the feature is off / unconfigured."""
    if sql is None or not config.enable_dataset_review:
        raise NotFoundError()
    return ReviewService(sql)


def _resolve_review_dataset(db, dataset_id):
    """Resolve the dataset under review (draft preferred), else any resolvable."""
    try:
        return _resolve_dataset(db, dataset_id, None, is_under_review=True)
    except NotFoundError:
        return _resolve_any_dataset(db, dataset_id)


def _institutional_only(ctx):
    return ctx["may_review_institution"] and not ctx["may_review_all"]


def _check_group(ctx, dataset):
    """Institutional reviewers may only act on datasets in their own group."""
    if _institutional_only(ctx) and value_or(dataset, "group_id", "A") != value_or(
        ctx["account"], "group_id", "not-A"
    ):
        raise ForbiddenError("Reviewer group mismatch.")


def _require_owner(account, dataset):
    if not account or account["uuid"] != dataset["account_uuid"]:
        raise ForbiddenError("Not allowed.")


def _is_reviewer_for(db, token, dataset):
    """True when TOKEN grants review of this dataset (group-scoped)."""
    if db.may_review(token):
        return True
    if db.may_review_institution(token):
        account = db.account_by_session_token(token)
        return value_or(dataset, "group_id", "A") == value_or(account, "group_id", "not-A")
    return False


def _snapshot(dataset, target_type, target_key):
    """Capture a scalar field's current value for the before→after display."""
    if target_type == "scalar" and target_key and dataset.get(target_key) is not None:
        return str(dataset.get(target_key))
    return None


@router.get(
    "/datasets/{dataset_id}/review",
    summary="Get the review conversation (role-filtered)",
    responses={
        200: _ok("Conversation", {"rounds": [], "comments": []}),
        404: {"model": ErrorResponse},
    },
)
def get_review(
    dataset_id: DatasetId,
    account=Depends(get_current_account),
    token: str | None = Depends(get_token),
    db=Depends(get_db),
    service: ReviewService = Depends(_get_review_service),
):
    dataset = _resolve_review_dataset(db, dataset_id)
    is_reviewer = _is_reviewer_for(db, token, dataset)
    is_owner = bool(account) and account["uuid"] == dataset["account_uuid"]
    if not is_reviewer and not is_owner:
        raise ForbiddenError("Not allowed.")

    conversation = service.conversation(
        dataset["container_uuid"],
        include_pending=is_reviewer,
        include_internal=is_reviewer,
        include_resolved=is_reviewer,
    )
    return JSONResponse(content=jsonable_encoder(conversation))


@router.post(
    "/datasets/{dataset_id}/review/comments",
    summary="Add a pending comment (reviewer)",
    responses={201: _ok("Created", {"id": 1}), 403: {"model": ErrorResponse}},
)
def create_comment(
    dataset_id: DatasetId,
    body: CommentCreateRequest,
    ctx: dict = Depends(resolve_reviewer_context),
    db=Depends(get_db),
    service: ReviewService = Depends(_get_review_service),
):
    dataset = _resolve_review_dataset(db, dataset_id)
    _check_group(ctx, dataset)
    comment_id = service.add_comment(
        dataset["container_uuid"],
        ctx["account"]["uuid"],
        body.target_type,
        body.body,
        target_key=body.target_key,
        target_label=body.target_label,
        field_value_snapshot=_snapshot(dataset, body.target_type, body.target_key),
    )
    return JSONResponse(content={"id": comment_id}, status_code=201)


@router.patch(
    "/datasets/{dataset_id}/review/comments/{comment_id}",
    summary="Edit a pending comment's opening message (reviewer)",
    responses={204: {"description": "Edited"}, 403: {"model": ErrorResponse}},
)
def edit_comment(
    dataset_id: DatasetId,
    comment_id: str,
    body: CommentEditRequest,
    ctx: dict = Depends(resolve_reviewer_context),
    db=Depends(get_db),
    service: ReviewService = Depends(_get_review_service),
):
    _check_group(ctx, _resolve_review_dataset(db, dataset_id))
    service.edit_comment(comment_id, body.body)
    return Response(status_code=204)


@router.delete(
    "/datasets/{dataset_id}/review/comments/{comment_id}",
    summary="Delete a pending comment (reviewer)",
    responses={204: {"description": "Deleted"}, 403: {"model": ErrorResponse}},
)
def delete_comment(
    dataset_id: DatasetId,
    comment_id: str,
    ctx: dict = Depends(resolve_reviewer_context),
    db=Depends(get_db),
    service: ReviewService = Depends(_get_review_service),
):
    _check_group(ctx, _resolve_review_dataset(db, dataset_id))
    service.delete_comment(comment_id)
    return Response(status_code=204)


@router.post(
    "/datasets/{dataset_id}/review/comments/{comment_id}/replies",
    summary="Reply to a comment (reviewer or author)",
    responses={201: _ok("Created", {"id": 1}), 403: {"model": ErrorResponse}},
)
def reply_to_comment(
    dataset_id: DatasetId,
    comment_id: str,
    body: ReplyRequest,
    account=Depends(require_auth),
    token: str | None = Depends(get_token),
    db=Depends(get_db),
    service: ReviewService = Depends(_get_review_service),
):
    dataset = _resolve_review_dataset(db, dataset_id)
    is_owner = account["uuid"] == dataset["account_uuid"]
    if not is_owner and not _is_reviewer_for(db, token, dataset):
        raise ForbiddenError("Not allowed.")
    event_id = service.add_event(comment_id, account["uuid"], "reply", body.body)
    return JSONResponse(content={"id": event_id}, status_code=201)


@router.patch(
    "/datasets/{dataset_id}/review/comments/{comment_id}/replies/{reply_id}",
    summary="Edit your own reply (reviewer or author)",
    responses={204: {"description": "Edited"}, 403: {"model": ErrorResponse}},
)
def edit_reply(
    dataset_id: DatasetId,
    comment_id: str,
    reply_id: str,
    body: ReplyRequest,
    account=Depends(require_auth),
    token: str | None = Depends(get_token),
    db=Depends(get_db),
    service: ReviewService = Depends(_get_review_service),
):
    dataset = _resolve_review_dataset(db, dataset_id)
    if account["uuid"] != dataset["account_uuid"] and not _is_reviewer_for(db, token, dataset):
        raise ForbiddenError("Not allowed.")
    # The service only touches a reply the caller authored.
    service.edit_event(reply_id, account["uuid"], body.body)
    return Response(status_code=204)


@router.delete(
    "/datasets/{dataset_id}/review/comments/{comment_id}/replies/{reply_id}",
    summary="Delete your own reply (reviewer or author)",
    responses={204: {"description": "Deleted"}, 403: {"model": ErrorResponse}},
)
def delete_reply(
    dataset_id: DatasetId,
    comment_id: str,
    reply_id: str,
    account=Depends(require_auth),
    token: str | None = Depends(get_token),
    db=Depends(get_db),
    service: ReviewService = Depends(_get_review_service),
):
    dataset = _resolve_review_dataset(db, dataset_id)
    if account["uuid"] != dataset["account_uuid"] and not _is_reviewer_for(db, token, dataset):
        raise ForbiddenError("Not allowed.")
    service.delete_event(reply_id, account["uuid"])
    return Response(status_code=204)


@router.post(
    "/datasets/{dataset_id}/review/comments/{comment_id}/addressed",
    summary="Mark a comment addressed (author)",
    responses={204: {"description": "Updated"}, 403: {"model": ErrorResponse}},
)
def mark_addressed(
    dataset_id: DatasetId,
    comment_id: str,
    body: AddressedRequest,
    account=Depends(require_auth),
    db=Depends(get_db),
    service: ReviewService = Depends(_get_review_service),
):
    _require_owner(account, _resolve_review_dataset(db, dataset_id))
    service.set_addressed(comment_id, account["uuid"], body.addressed)
    return Response(status_code=204)


@router.post(
    "/datasets/{dataset_id}/review/comments/{comment_id}/resolve",
    summary="Resolve or reopen a comment (reviewer)",
    responses={204: {"description": "Updated"}, 403: {"model": ErrorResponse}},
)
def resolve_comment(
    dataset_id: DatasetId,
    comment_id: str,
    body: ResolveRequest,
    ctx: dict = Depends(resolve_reviewer_context),
    db=Depends(get_db),
    service: ReviewService = Depends(_get_review_service),
):
    _check_group(ctx, _resolve_review_dataset(db, dataset_id))
    service.set_resolved(comment_id, ctx["account"]["uuid"], body.resolved)
    return Response(status_code=204)


@router.put(
    "/datasets/{dataset_id}/review/notes",
    summary="Save draft general/internal notes (reviewer)",
    responses={204: {"description": "Saved"}, 403: {"model": ErrorResponse}},
)
def save_notes(
    dataset_id: DatasetId,
    body: NotesRequest,
    ctx: dict = Depends(resolve_reviewer_context),
    db=Depends(get_db),
    service: ReviewService = Depends(_get_review_service),
):
    dataset = _resolve_review_dataset(db, dataset_id)
    _check_group(ctx, dataset)
    service.save_notes(
        dataset["container_uuid"], ctx["account"]["uuid"], body.general_notes, body.internal_notes
    )
    return Response(status_code=204)


@router.post(
    "/datasets/{dataset_id}/review/submit",
    summary="Submit the review round with an outcome (reviewer)",
    responses={
        200: _ok("Submitted", {"outcome": "request_changes"}),
        403: {"model": ErrorResponse},
    },
)
def submit_review(
    dataset_id: DatasetId,
    body: SubmitRequest,
    ctx: dict = Depends(resolve_reviewer_context),
    db=Depends(get_db),
    service: ReviewService = Depends(_get_review_service),
):
    dataset = _resolve_review_dataset(db, dataset_id)
    _check_group(ctx, dataset)
    key = dataset["container_uuid"]

    # A draft round always exists at submit (create an empty one if the reviewer
    # only typed notes in this call).
    service.open_draft_round(key, ctx["account"]["uuid"])

    if body.outcome == "request_changes":
        pending = service.conversation(key, include_pending=True, include_internal=True)
        if not pending["comments"] and not (body.general_notes or "").strip():
            raise InvalidInputError(
                "Request-changes needs at least one comment or general notes.", "EmptyReview"
            )

    service.submit_round(
        key, body.outcome, general_notes=body.general_notes, internal_notes=body.internal_notes
    )

    if body.outcome == "approve":
        from djehuty.api.v3.datasets.publishing import _perform_publish

        author_account = db.account_by_uuid(dataset["account_uuid"])
        return _perform_publish(db, author_account, dataset, ctx["account"], dataset_id)

    if body.outcome == "reject":
        from djehuty.api.v3.datasets.publishing import _perform_decline

        author_account = db.account_by_uuid(dataset["account_uuid"])
        return _perform_decline(db, author_account, dataset)

    # request_changes: stays under review; notify the author once.
    _notify_request_changes(db, dataset)
    db.cache.invalidate_by_prefix("reviews")
    return JSONResponse(content={"outcome": "request_changes"}, status_code=200)


@router.post(
    "/datasets/{dataset_id}/review/send-back",
    summary="Author: notify the reviewer that comments were addressed",
    responses={204: {"description": "Reviewer notified"}, 403: {"model": ErrorResponse}},
)
def send_back(
    dataset_id: DatasetId,
    account=Depends(require_auth),
    db=Depends(get_db),
    _service: ReviewService = Depends(_get_review_service),
):
    dataset = _resolve_review_dataset(db, dataset_id)
    _require_owner(account, dataset)
    _notify_sent_back(db, dataset)
    return Response(status_code=204)


def _notify_request_changes(db, dataset):
    """E-mail the author that changes were requested (template: Commit 5)."""
    from djehuty.services import email as email_module

    try:
        owner = db.account_by_uuid(dataset["account_uuid"])
        email_module.send_templated_email(
            db,
            [owner["email"]],
            f"Changes requested: {dataset['title']}",
            "review_request_changes",
            base_url=config.base_url,
            support_email=config.support_email_address,
            title=dataset["title"],
            container_uuid=dataset["container_uuid"],
        )
    except (TypeError, IndexError, KeyError) as error:
        logger.error("Unable to send request-changes e-mail: %s.", error)


def _notify_sent_back(db, dataset):
    """E-mail the assigned reviewer that the author addressed comments."""
    from djehuty.services import email as email_module

    try:
        review = db.reviews(dataset_uri=dataset["uri"])[0]
        assigned = db.account_by_uuid(uri_to_uuid(review["assigned_to"]))
        if assigned:
            email_module.send_templated_email(
                db,
                [assigned["email"]],
                f"Comments addressed: {dataset['title']}",
                "review_sent_back",
                base_url=config.base_url,
                title=dataset["title"],
                container_uuid=dataset["container_uuid"],
            )
    except (TypeError, IndexError, KeyError) as error:
        logger.error("Unable to send sent-back e-mail: %s.", error)
