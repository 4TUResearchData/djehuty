"""Shared helpers for the v3 physical-samples sub-resources."""

from typing import Annotated

from fastapi import Path

from djehuty.web.config import config

# Physical samples are not versioned: the "container" is the sample's identity.
# container_uuid is that version-independent id — the public
# /physical_sample/<id> URL and the IGSN both use it.
PhysicalSampleId = Annotated[
    str,
    Path(
        description=(
            "The physical sample's version-independent container UUID — the "
            "public /physical_sample/<id> URL and the IGSN use it."
        )
    ),
]


def _resolve_physical_sample(
    db,
    container_uuid,
    account_uuid=None,
    is_published=False,
    is_latest=False,
    is_under_review=None,
    version=None,
):
    """Resolve a physical sample by container UUID, injecting ``uri``/``uuid``.

    Faithful to the legacy ``__physical_sample_by_id_or_uri``: returns None
    unless ``container_uuid`` is a valid UUID, reads the first matching record,
    and injects ``uri`` ("physical-sample:<sample_uuid>") and ``uuid`` (the
    sample_uuid). Returns None on an empty result.
    """
    from djehuty.utils.convenience import parses_to_int
    from djehuty.web import validator

    try:
        if version is not None and not parses_to_int(version):
            return None
        if not validator.is_valid_uuid(container_uuid):
            return None
        sample = db.physical_samples(
            container_uuid=container_uuid,
            is_published=is_published,
            is_latest=is_latest,
            is_under_review=is_under_review,
            account_uuid=account_uuid,
        )[0]
        sample["uri"] = f"physical-sample:{sample['sample_uuid']}"
        sample["uuid"] = sample["sample_uuid"]
        return sample
    except IndexError:
        return None


def _editable_physical_sample_draft(db, container_uuid, account_uuid):
    """Return the container's draft, creating one from the published record when
    only a published version exists (an update). Faithful to the legacy
    ``__editable_physical_sample_draft`` — returns None when neither exists.
    """
    try:
        return db.physical_samples(
            container_uuid=container_uuid,
            account_uuid=account_uuid,
            is_published=False,
            is_latest=False,
        )[0]
    except IndexError:
        pass

    # No draft yet: this is an update of a published sample. Copy the published
    # record into a fresh draft (same container, same IGSN).
    if db.create_draft_from_published_physical_sample(container_uuid, account_uuid) is None:
        return None

    try:
        return db.physical_samples(
            container_uuid=container_uuid,
            account_uuid=account_uuid,
            is_published=False,
            is_latest=False,
        )[0]
    except IndexError:
        return None


def _author_list_from_request_input(db, parameters, created_by=None):
    """Return ``(authors, errors)`` as a list of rdflib URIRefs.

    Resolves existing author UUIDs and creates new author records, faithful to
    the legacy ``__author_list_from_request_input``. ``errors`` is None on
    success.
    """
    from rdflib import URIRef

    from djehuty.utils.rdf import uuid_to_uri
    from djehuty.web import validator

    errors: list = []
    records = validator.array_value(parameters, "authors", error_list=errors)
    if errors:
        return None, errors
    if records is None:
        return [], None

    authors = []
    for record in records:
        author_uuid = validator.string_value(record, "uuid", 0, 36, False)
        if author_uuid and not validator.is_valid_uuid(author_uuid):
            return None, [{"field_name": "author.uuid", "message": "Invalid UUID for author."}]
        if author_uuid:
            authors.append(URIRef(uuid_to_uri(author_uuid, "author")))
            continue

        record = {
            "full_name": validator.string_value(record, "name", 0, 255, False, errors),
            "first_name": validator.string_value(record, "first_name", 0, 255, True, errors),
            "last_name": validator.string_value(record, "last_name", 0, 255, True, errors),
            "email": validator.string_value(record, "email", 0, 255, False, errors),
            "orcid_id": validator.string_value(record, "orcid_id", 0, 38, False, errors),
            "job_title": validator.string_value(record, "job_title", 0, 255, False, errors),
            "is_active": False,
            "is_public": True,
            "created_by": created_by,
        }
        if record["full_name"] is None:
            record["full_name"] = f"{record['first_name']} {record['last_name']}"
        if errors:
            return None, errors

        new_uuid = db.insert_author(**record)
        if new_uuid is None:
            return None, [{"field_name": "authors", "message": "Unable to create author record."}]
        authors.append(URIRef(uuid_to_uri(new_uuid, "author")))

    return authors, None


def _category_list_from_request_input(db, parameters):
    """Return ``(categories, errors)`` from a request body's ``categories``.

    Faithful to the legacy ``__category_list_from_request_input``: accepts
    numeric ids or UUIDs, verifies each exists, and normalises each to
    ``{"uuid": ...}``. ``errors`` is None on success.
    """
    from djehuty.utils.convenience import parses_to_int
    from djehuty.web import validator

    errors: list = []
    records = validator.array_value(parameters, "categories", error_list=errors)
    if errors:
        return None, errors
    if records is None:
        return [], None

    for index, record in enumerate(records):
        if parses_to_int(record):
            category = db.category_by_id(category_id=record)
            if not category:
                return None, [
                    {"field_name": "categories", "message": f"No such category '{record}'."}
                ]
            records[index] = {"uuid": category["uuid"]}
        elif validator.is_valid_uuid(record):
            if not db.category_by_id(category_uuid=record):
                return None, [
                    {"field_name": "categories", "message": f"No such category '{record}'."}
                ]
            records[index] = {"uuid": record}

    return records, None


def _account_can_use_igsn(db, account_uuid):
    """True when IGSN is enabled and the account may use it.

    The feature must be configured (a prefix is set) and enabled, and -- when an
    allow-list is configured -- the account's e-mail domain must appear in
    ``config.igsn_allowed_domains``. An empty allow-list permits every depositor.
    """
    if not (config.supports_igsn and config.igsn_enabled):
        return False
    if not config.igsn_allowed_domains:
        return True
    account = db.account_by_uuid(account_uuid)
    if account is None:
        return False
    if "domain" in account:
        return account["domain"] in config.igsn_allowed_domains
    return False
