"""Unit tests for who may soft delete, restore and permanently delete a draft

These drive the real ``SparqlInterface`` against an in-memory rdflib store
(same approach as ``test_group_reconcile.py``), so the SPARQL templates are
exercised rather than a fake that always reports success.
"""

import tempfile
import uuid

import pytest
from rdflib import XSD, Graph, URIRef

from djehuty.utils import rdf
from djehuty.web.config import config
from djehuty.web.database import SparqlInterface

OWNER = str(uuid.uuid4())
SUPERVISOR = str(uuid.uuid4())
COLLABORATOR = str(uuid.uuid4())
STRANGER = str(uuid.uuid4())


@pytest.fixture
def db():
    """A SparqlInterface backed by a fresh in-memory store per test."""
    config.endpoint = "memory://test"
    config.update_endpoint = None
    config.state_graph = "https://data.4tu.nl/portal/test"
    config.disable_collaboration = False
    interface = SparqlInterface()
    interface.setup_sparql_endpoint()
    interface.cache.storage = tempfile.mkdtemp()
    return interface


@pytest.fixture
def draft(db):
    container_uuid, dataset_uuid = db.insert_dataset(title="draft", account_uuid=OWNER)
    group_uuid = db.insert_group("TU Delft", False, True, 28586, 28585, "tudelft.nl")
    db.insert_group_member(group_uuid, SUPERVISOR, True)

    criteria = Graph()
    rdf.add(
        criteria,
        URIRef(f"dataset:{dataset_uuid}"),
        rdf.DJHT["association_criteria"],
        "tudelft.nl",
        XSD.string,
    )
    db.add_triples_from_graph(criteria)
    return container_uuid, dataset_uuid


def _share_with_remove(db, dataset_uuid):
    return db.insert_collaborator(
        dataset_uuid,
        COLLABORATOR,
        OWNER,
        metadata_read=True,
        metadata_edit=True,
        metadata_remove=True,
        data_read=True,
        data_edit=True,
        data_remove=False,
    )


def _is_deleted(db, dataset_uuid):
    return db.sparql.query(
        f"ASK {{ GRAPH <{config.state_graph}> {{ <dataset:{dataset_uuid}> "
        f'<{rdf.DJHT["is_deleted"]}> "true"^^<{XSD.boolean}> }} }}'
    ).askAnswer


def _has_draft(db, draft):
    container_uuid, dataset_uuid = draft
    return db.sparql.query(
        f"ASK {{ GRAPH <{config.state_graph}> {{ <container:{container_uuid}> "
        f"<{rdf.DJHT['draft']}> <dataset:{dataset_uuid}> }} }}"
    ).askAnswer


def _soft_delete(db, draft, account_uuid):
    container_uuid, dataset_uuid = draft
    return db.soft_delete_dataset_draft(container_uuid, dataset_uuid, account_uuid, OWNER)


def _restore(db, draft, account_uuid):
    container_uuid, dataset_uuid = draft
    return db.restore_dataset_draft(container_uuid, dataset_uuid, account_uuid, OWNER)


def _delete_permanently(db, draft, account_uuid):
    container_uuid, dataset_uuid = draft
    return db.delete_dataset_draft(container_uuid, dataset_uuid, account_uuid, OWNER)


@pytest.mark.parametrize("account_uuid", [OWNER, SUPERVISOR])
def test_owner_and_supervisor_can_soft_delete_and_restore(db, draft, account_uuid):
    _soft_delete(db, draft, account_uuid)
    assert _is_deleted(db, draft[1])

    _restore(db, draft, account_uuid)
    assert not _is_deleted(db, draft[1])


@pytest.mark.parametrize("account_uuid", [OWNER, SUPERVISOR])
def test_owner_and_supervisor_can_delete_permanently(db, draft, account_uuid):
    _delete_permanently(db, draft, account_uuid)
    assert not _has_draft(db, draft)


def test_collaborator_with_metadata_remove_cannot_soft_delete(db, draft):
    _share_with_remove(db, draft[1])

    _soft_delete(db, draft, COLLABORATOR)
    assert not _is_deleted(db, draft[1])


def test_collaborator_with_metadata_remove_cannot_restore(db, draft):
    _share_with_remove(db, draft[1])
    _soft_delete(db, draft, OWNER)

    _restore(db, draft, COLLABORATOR)
    assert _is_deleted(db, draft[1])


def test_collaborator_with_metadata_remove_cannot_delete_permanently(db, draft):
    _share_with_remove(db, draft[1])

    _delete_permanently(db, draft, COLLABORATOR)
    assert _has_draft(db, draft)


def test_stranger_cannot_soft_delete(db, draft):
    _soft_delete(db, draft, STRANGER)
    assert not _is_deleted(db, draft[1])


def test_dashboard_offers_removal_to_supervisor(db, draft):
    records = db.datasets(account_uuid=SUPERVISOR, is_published=False)
    assert [record["is_supervisor"] for record in records] == [True]


def test_dashboard_withholds_removal_from_collaborator(db, draft):
    _share_with_remove(db, draft[1])

    records = db.datasets(account_uuid=COLLABORATOR, is_published=False)
    assert [record["is_supervisor"] for record in records] == [False]
