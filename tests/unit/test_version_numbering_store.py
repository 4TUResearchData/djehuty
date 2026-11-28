import tempfile

import pytest
from rdflib import RDFS, Graph

from djehuty.services import datacite, versioning
from djehuty.utils import rdf
from djehuty.web.config import config
from djehuty.web.database import SparqlInterface
from djehuty.web.wsgi import WebServer


@pytest.fixture
def db():
    config.endpoint = "memory://test"
    config.update_endpoint = None
    config.state_graph = "https://data.4tu.nl/portal/test"
    interface = SparqlInterface()
    interface.setup_sparql_endpoint()
    interface.cache.storage = tempfile.mkdtemp()
    graph = Graph()
    for container_type in ("DatasetContainer", "CollectionContainer"):
        graph.add((rdf.DJHT[container_type], RDFS.subClassOf, rdf.DJHT["Container"]))
    interface.add_triples_from_graph(graph)
    return interface


@pytest.fixture
def owner(db):
    return db.insert_account(email="o@4tu.nl", first_name="O", last_name="W")


ITEM_TYPES = ["dataset", "collection"]


def _draft(db, owner, item_type):
    insert = db.insert_dataset if item_type == "dataset" else db.insert_collection
    container_uuid, _ = insert(title="Versioned", account_uuid=owner)
    return container_uuid


def _publish(db, owner, item_type, container_uuid, version):
    if item_type == "collection":
        assert db.publish_collection(container_uuid, owner, version)
        return
    draft = db.datasets(container_uuid=container_uuid, is_published=False, use_cache=False)[0]
    review_uri = db.insert_review(draft["uri"])
    assert db.update_review(
        review_uri, author_account_uuid=owner, assigned_to=owner, status="assigned"
    )
    assert db.publish_dataset(container_uuid, owner, version)


def _publish_next(db, owner, item_type, container_uuid):
    version = versioning.next_version(db, container_uuid)
    _publish(db, owner, item_type, container_uuid, version)
    return version


def _new_version_draft(db, owner, item_type, container_uuid):
    if item_type == "collection":
        assert db.create_draft_from_published_collection(container_uuid)
    else:
        assert db.create_draft_from_published_dataset(container_uuid, owner)


def _published_versions(db, item_type, container_uuid):
    items = db.datasets if item_type == "dataset" else db.collections
    records = items(container_uuid=container_uuid, is_published=True, is_latest=None, limit=None)
    return sorted(record["version"] for record in records)


@pytest.mark.parametrize("item_type", ITEM_TYPES)
def test_publish_writes_the_version_it_is_given(db, owner, item_type):
    container_uuid = _draft(db, owner, item_type)
    _publish(db, owner, item_type, container_uuid, 7)
    assert _published_versions(db, item_type, container_uuid) == [7]
    assert db.highest_version(container_uuid) == 7


@pytest.mark.parametrize("item_type", ITEM_TYPES)
def test_each_publish_gets_the_next_number(db, owner, item_type):
    container_uuid = _draft(db, owner, item_type)
    assert db.highest_version(container_uuid) == 0
    assert _publish_next(db, owner, item_type, container_uuid) == 1
    _new_version_draft(db, owner, item_type, container_uuid)
    assert _publish_next(db, owner, item_type, container_uuid) == 2
    assert _published_versions(db, item_type, container_uuid) == [1, 2]
    assert db.highest_version(container_uuid) == 2


@pytest.fixture
def new_version_draft(db, owner):
    """v1 published and a draft for the next version."""
    container_uuid = _draft(db, owner, "dataset")
    _publish_next(db, owner, "dataset", container_uuid)
    _new_version_draft(db, owner, "dataset", container_uuid)
    return container_uuid


def test_draft_datacite_export_uses_the_next_version(db, new_version_draft):
    parameters = datacite.metadata_export_parameters(db, new_version_draft, from_draft=True)
    assert parameters["item"]["version"] == 2


def test_legacy_draft_datacite_export_uses_the_next_version(db, new_version_draft):
    server = WebServer()
    server.db = db
    parameters = server._WebServer__metadata_export_parameters(new_version_draft, from_draft=True)
    assert parameters["item"]["version"] == 2
