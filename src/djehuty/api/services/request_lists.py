"""Request-input list parsers shared by the API endpoints.

Faithful ports of the djehuty.web.wsgi ``__*_list_from_request_input``
helpers; each returns ``(records, errors)`` exactly like the legacy methods.
"""

from rdflib import URIRef

from djehuty.utils.convenience import parses_to_int
from djehuty.utils.rdf import uuid_to_uri
from djehuty.web import validator


def author_list_from_request_input(parameters, db, created_by=None):
    """Return a list of author URIs and a list of error messages."""
    errors = []
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

        author_uuid = db.insert_author(**record)
        if author_uuid is None:
            return None, [{"field_name": "authors", "message": "Unable to create author record."}]
        authors.append(URIRef(uuid_to_uri(author_uuid, "author")))

    return authors, None


def simple_list_from_request_input(parameters, name, key):
    """Return a list of single-key records and a list of error messages."""
    errors = []
    records = validator.array_value(parameters, name, error_list=errors)
    if errors:
        return None, errors
    if records is None:
        return [], None

    for index, record in enumerate(records):
        records[index] = {key: record}
    return records, None


def reference_list_from_request_input(parameters):
    """Return a list of reference records and a list of error messages."""
    return simple_list_from_request_input(parameters, "references", "url")


def tag_list_from_request_input(parameters, field_name="tags"):
    """Return a list of tag records and a list of error messages."""
    return simple_list_from_request_input(parameters, field_name, "tag")


def category_list_from_request_input(parameters, db):
    """Return a list of category records and a list of error messages."""
    errors = []
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
