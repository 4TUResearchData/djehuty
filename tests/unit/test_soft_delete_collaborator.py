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
OTHER_SUPERVISOR = str(uuid.uuid4())
MEMBER = str(uuid.uuid4())
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
def group(db):
    group_uuid = db.insert_group("TU Delft", False, True, 28586, 28585, "tudelft.nl")
    db.insert_group_member(group_uuid, SUPERVISOR, True)
    return group_uuid


@pytest.fixture
def draft(db, group):
    container_uuid, dataset_uuid = db.insert_dataset(title="draft", account_uuid=OWNER)

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


def _draft_uuids(db, account_uuid, is_deleted):
    records = db.datasets(account_uuid=account_uuid, is_published=False, is_deleted=is_deleted)
    return [record["uuid"] for record in records]


def _add_to_dataset(db, dataset_uuid, predicate, value, datatype):
    graph = Graph()
    rdf.add(graph, URIRef(f"dataset:{dataset_uuid}"), rdf.DJHT[predicate], value, datatype)
    db.add_triples_from_graph(graph)


def _dataset_triples(db, dataset_uuid):
    return set(
        db.sparql.query(
            f"SELECT ?p ?o WHERE {{ GRAPH <{config.state_graph}> "
            f"{{ <dataset:{dataset_uuid}> ?p ?o }} }}"
        )
    )


def _move_to_published_versions(db, draft):
    container_uuid, dataset_uuid = draft
    graph = f"<{config.state_graph}>"
    container = f"<container:{container_uuid}>"
    dataset = f"<dataset:{dataset_uuid}>"
    db.sparql.update(
        f"DELETE DATA {{ GRAPH {graph} {{ {container} <{rdf.DJHT['draft']}> {dataset} }} }} ;"
        f"INSERT DATA {{ GRAPH {graph} {{ "
        f"{container} <{rdf.DJHT['latest_published_version']}> {dataset} }} }}"
    )


@pytest.mark.parametrize("account_uuid", [OWNER, SUPERVISOR])
def test_owner_and_supervisor_can_soft_delete_and_restore(db, draft, account_uuid):
    _soft_delete(db, draft, account_uuid)
    assert _is_deleted(db, draft[1])

    _restore(db, draft, account_uuid)
    assert not _is_deleted(db, draft[1])


@pytest.mark.parametrize("account_uuid", [OWNER, SUPERVISOR])
def test_owner_and_supervisor_can_delete_permanently(db, draft, account_uuid):
    _soft_delete(db, draft, OWNER)

    _delete_permanently(db, draft, account_uuid)
    assert not _has_draft(db, draft)


def test_permanent_delete_requires_soft_delete(db, draft):
    _delete_permanently(db, draft, OWNER)
    assert _has_draft(db, draft)


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
    _soft_delete(db, draft, OWNER)

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


def test_supervisor_dashboard_follows_soft_delete_and_restore(db, draft):
    assert _draft_uuids(db, SUPERVISOR, is_deleted=False) == [draft[1]]
    assert _draft_uuids(db, SUPERVISOR, is_deleted=True) == []

    _soft_delete(db, draft, OWNER)
    assert _draft_uuids(db, SUPERVISOR, is_deleted=False) == []
    assert _draft_uuids(db, SUPERVISOR, is_deleted=True) == [draft[1]]

    _restore(db, draft, OWNER)
    assert _draft_uuids(db, SUPERVISOR, is_deleted=False) == [draft[1]]
    assert _draft_uuids(db, SUPERVISOR, is_deleted=True) == []


def test_owner_who_is_supervisor_sees_draft_once(db, group, draft):
    db.insert_group_member(group, OWNER, True)

    records = db.datasets(account_uuid=OWNER, is_published=False)
    assert [record["is_supervisor"] for record in records] == [True]


def test_supervisor_of_another_group_with_the_same_criteria_can_soft_delete(db, draft):
    other_group = db.insert_group("TU Delft faculty", False, False, 28587, 28586, "tudelft.nl")
    db.insert_group_member(other_group, OTHER_SUPERVISOR, True)

    _soft_delete(db, draft, OTHER_SUPERVISOR)
    assert _is_deleted(db, draft[1])


def test_supervisor_of_a_group_with_other_criteria_cannot_soft_delete(db, draft):
    other_group = db.insert_group("Erasmus", False, False, 28600, None, "eur.nl")
    db.insert_group_member(other_group, OTHER_SUPERVISOR, True)

    _soft_delete(db, draft, OTHER_SUPERVISOR)
    assert not _is_deleted(db, draft[1])


def test_group_chosen_on_the_form_does_not_grant_supervisor_rights(db, draft):
    other_group = db.insert_group("Erasmus", False, False, 28600, None, "eur.nl")
    db.insert_group_member(other_group, OTHER_SUPERVISOR, True)
    _add_to_dataset(db, draft[1], "group_id", 28600, XSD.integer)

    _soft_delete(db, draft, OTHER_SUPERVISOR)
    assert not _is_deleted(db, draft[1])


def test_group_member_without_supervisor_cannot_see_or_soft_delete(db, group, draft):
    db.insert_group_member(group, MEMBER, False)

    assert _draft_uuids(db, MEMBER, is_deleted=False) == []

    _soft_delete(db, draft, MEMBER)
    assert not _is_deleted(db, draft[1])


def test_collaborator_sees_deleted_draft_without_removal(db, draft):
    _share_with_remove(db, draft[1])
    _soft_delete(db, draft, OWNER)

    records = db.datasets(account_uuid=COLLABORATOR, is_published=False, is_deleted=True)
    assert [(record["uuid"], record["is_supervisor"]) for record in records] == [(draft[1], False)]


def test_published_version_cannot_be_soft_deleted(db, draft):
    _move_to_published_versions(db, draft)

    _soft_delete(db, draft, OWNER)
    assert not _is_deleted(db, draft[1])


def test_published_version_cannot_be_restored_or_deleted_permanently(db, draft):
    _add_to_dataset(db, draft[1], "is_deleted", True, XSD.boolean)
    _move_to_published_versions(db, draft)
    before = _dataset_triples(db, draft[1])

    _restore(db, draft, OWNER)
    _delete_permanently(db, draft, OWNER)
    assert _dataset_triples(db, draft[1]) == before


def test_soft_delete_and_restore_keep_every_triple(db, draft):
    before = _dataset_triples(db, draft[1])

    _soft_delete(db, draft, OWNER)
    assert before < _dataset_triples(db, draft[1])
    assert _has_draft(db, draft)

    _restore(db, draft, OWNER)
    assert _dataset_triples(db, draft[1]) == before


def test_soft_deleted_draft_is_only_listed_as_deleted(db, draft):
    _soft_delete(db, draft, OWNER)

    default_listing = db.datasets(account_uuid=OWNER, is_published=False)
    assert [record["uuid"] for record in default_listing] == []
    assert _draft_uuids(db, OWNER, is_deleted=True) == [draft[1]]
