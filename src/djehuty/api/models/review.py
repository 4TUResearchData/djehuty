"""Pydantic request models for the field-level review conversation API."""

from typing import Literal

from pydantic import BaseModel, Field


class CommentCreateRequest(BaseModel):
    """A reviewer's new comment anchored to a field/entity/section."""

    target_type: str = Field(
        description="scalar | author | category | collaborator | references | tags | …"
    )
    target_key: str | None = Field(
        default=None,
        description="Field token or entity UUID; null for section-level targets.",
    )
    target_label: str | None = Field(
        default=None,
        description="Human label of the target (e.g. 'Title', 'Funding: Horizon 2020'), "
        "shown in the author's view without needing the entity list.",
    )
    body: str = Field(description="The reviewer's comment on this field.")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"target_type": "scalar", "target_key": "title", "body": "Please clarify."}
            ]
        }
    }


class CommentEditRequest(BaseModel):
    """Edit the opening message of a pending comment."""

    body: str = Field(description="Replacement text for the comment's opening message.")


class ReplyRequest(BaseModel):
    """A reply added to an existing comment thread (reviewer or author)."""

    body: str = Field(description="The reply text.")


class AddressedRequest(BaseModel):
    """Author toggle: mark a comment addressed (or clear it)."""

    addressed: bool = Field(default=True)


class ResolveRequest(BaseModel):
    """Reviewer toggle: resolve (or reopen) a comment."""

    resolved: bool = Field(default=True)


class NotesRequest(BaseModel):
    """Draft general (shared) and internal (reviewer-only) notes for the round."""

    general_notes: str | None = Field(default=None)
    internal_notes: str | None = Field(default=None)


class SubmitRequest(BaseModel):
    """Submit the round with an outcome."""

    outcome: Literal["request_changes", "approve", "reject"]
    general_notes: str | None = Field(default=None)
    internal_notes: str | None = Field(default=None)

    model_config = {"json_schema_extra": {"examples": [{"outcome": "request_changes"}]}}
