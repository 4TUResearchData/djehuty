"""Author matching for the new HTTP implementation."""

from djehuty.utils.convenience import normalize_orcid


def active_author_matching_identifiers(db, email=None, orcid_id=None, exclude_author_uuid=None):
    """Return an active author matching an email address or ORCID."""
    if email:
        email = email.strip().casefold()
    orcid_id = normalize_orcid(orcid_id)

    if orcid_id:
        matches = db.authors(orcid_id=orcid_id, is_active=True, order="uuid", limit=1)
        if matches and matches[0]["uuid"] != exclude_author_uuid:
            return matches[0]

    if email:
        matches = db.authors(email=email, is_active=True, order="uuid", limit=1)
        if matches and matches[0]["uuid"] != exclude_author_uuid:
            return matches[0]

    return None
