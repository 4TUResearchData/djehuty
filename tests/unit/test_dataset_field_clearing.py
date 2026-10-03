"""Unit tests for clearing optional metadata fields on a dataset.

When a depositor empties a field, the web UI sends null and update_dataset
passes None to update_dataset.sparql, whose DELETE block must still remove the
existing triple.  Guarding that DELETE line on "is not none" silently keeps the
old value, which is the defect reported in issue #77 for 'Derived From'.

Because the DELETE is unconditional, a caller that updates only part of a
dataset has to re-send the fields it wants to keep.  The DOI reservation path
does that.
"""

import os

import pytest
from jinja2 import Environment, FileSystemLoader

from djehuty.services import datacite

TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "src",
    "djehuty",
    "web",
    "resources",
    "sparql_templates",
)

# Optional fields a depositor can empty in the deposit form
# Each one must be removable
CLEARABLE_FIELDS = [
    "resource_doi",
    "resource_title",
    "time_coverage",
    "format",
    "geolocation",
    "longitude",
    "latitude",
    "data_link",
    "derived_from",
    "same_as",
    "organizations",
]

## Every variable the template reads
TEMPLATE_VARIABLES = [
    "account_uuid",
    "agreed_to_deposit_agreement",
    "agreed_to_publish",
    "codecheck_certificate_doi",
    "container_doi",
    "contributors",
    "data_link",
    "defined_type",
    "defined_type_name",
    "derived_from",
    "description",
    "doi",
    "embargo_reason",
    "embargo_title",
    "embargo_type",
    "embargo_until_date",
    "eula",
    "first_online_date",
    "format",
    "geolocation",
    "git_code_hosting_url",
    "git_repository_name",
    "group_id",
    "has_linked_file",
    "is_metadata_record",
    "language",
    "latitude",
    "license_remarks",
    "license_url",
    "longitude",
    "metadata_reason",
    "organizations",
    "publisher",
    "requested_codecheck",
    "resource_doi",
    "resource_title",
    "same_as",
    "time_coverage",
    "title",
]


def render(**overrides):
    """Render update_dataset.sparql with all optional fields cleared."""

    environment = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)
    parameters = dict.fromkeys(TEMPLATE_VARIABLES)
    parameters.update(
        {
            "state_graph": "djehuty://test",
            "dataset_uri": "dataset:1234",
            "disable_collaboration": True,
            "modified_date": "2026-01-01T00:00:00Z",
            "is_embargoed": False,
            "is_restricted": False,
        }
    )
    parameters.update(overrides)
    return environment.get_template("update_dataset.sparql").render(parameters)


def blocks(query):
    """Return the DELETE and INSERT blocks of QUERY."""

    delete_block, remainder = query.split("INSERT {", 1)
    insert_block = remainder.split("WHERE {", 1)[0]
    return delete_block, insert_block


@pytest.mark.parametrize("field", CLEARABLE_FIELDS)
def test_clearing_a_field_removes_its_triple(field):
    delete_block, insert_block = blocks(render())
    assert f"djht:{field} " in delete_block, f"clearing '{field}' leaves its old value in place"
    assert f"djht:{field} " not in insert_block, f"clearing '{field}' writes back an empty value"


def test_setting_derived_from_replaces_the_old_value():
    delete_block, insert_block = blocks(
        render(derived_from='"https://example.org/original"^^xsd:string')
    )
    assert "djht:derived_from " in delete_block
    assert "djht:derived_from " in insert_block


def test_the_title_is_never_dropped_by_an_empty_update():
    """The title is required, so an update without one must leave it alone."""

    delete_block, insert_block = blocks(render())
    assert "djht:title " not in delete_block
    assert "djht:title " not in insert_block


class _DoiDb:
    """A database that reports an existing 'derived_from' on the dataset."""

    def __init__(self):
        self.update_kwargs = None

    def derived_from(self, item_uri, **kwargs):
        return ["https://example.org/original"]

    def update_dataset(self, dataset_uuid, account_uuid, **kwargs):
        self.update_kwargs = kwargs
        return True


def test_reserving_a_doi_keeps_derived_from(monkeypatch):
    """'derived_from' is absent from the record 'datasets' returns, so the DOI
    reservation has to read it back rather than let update_dataset drop it."""

    monkeypatch.setattr(datacite.config, "datacite_prefix", "10.5074")
    monkeypatch.setattr(
        datacite, "datacite_reserve_doi", lambda doi=None: {"data": {"id": "10.5074/cont-1"}}
    )
    db = _DoiDb()
    doi = datacite.reserve_and_save_doi(
        db,
        "acct-1",
        {
            "uuid": "ds-1",
            "container_uuid": "cont-1",
            "uri": "dataset:ds-1",
            "container_doi": "10.5074/cont-1",
        },
    )
    assert doi == "10.5074/cont-1"
    assert db.update_kwargs["derived_from"] == "https://example.org/original"
