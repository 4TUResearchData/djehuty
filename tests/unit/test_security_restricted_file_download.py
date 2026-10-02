"""Security regression: an anonymous ``dataset_files`` lookup must not return a
file that belongs to a restricted (indefinitely embargoed) dataset version, even
when the file UUID is known. Public-version files stay downloadable, and the
owner still sees their own restricted files.

Uses the real ``SparqlInterface`` against an in-memory rdflib store (same
approach as ``test_group_reconcile``), so no Virtuoso is needed.
"""

import tempfile

import pytest
from rdflib import RDFS, XSD, Graph, URIRef

from djehuty.utils import rdf
from djehuty.web.config import config
from djehuty.web.database import SparqlInterface


@pytest.fixture
def db():
    config.endpoint = "memory://test"
    config.update_endpoint = None
    config.state_graph = "https://data.4tu.nl/portal/test"
    interface = SparqlInterface()
    interface.setup_sparql_endpoint()
    interface.cache.storage = tempfile.mkdtemp()
    # Attaching a file walks container_items, which relies on this ontology triple.
    graph = Graph()
    graph.add((rdf.DJHT["DatasetContainer"], RDFS.subClassOf, rdf.DJHT["Container"]))
    interface.add_triples_from_graph(graph)
    return interface


def _dataset_with_file(db, owner, restricted):
    _container, version = db.insert_dataset(title="t", account_uuid=owner)
    file_uuid = db.insert_file(
        name="f.bin",
        size=1,
        is_link_only=0,
        dataset_uri=rdf.uuid_to_uri(version, "dataset"),
        account_uuid=owner,
    )
    if restricted:
        graph = Graph()
        rdf.add(
            graph,
            URIRef(rdf.uuid_to_uri(version, "dataset")),
            rdf.DJHT["embargo_type"],
            "file",
            XSD.string,
        )
        db.add_triples_from_graph(graph)
    return file_uuid


def test_restricted_file_hidden_from_anonymous(db):
    owner = db.insert_account(email="o@4tu.nl", first_name="O", last_name="W")
    public_file = _dataset_with_file(db, owner, restricted=False)
    restricted_file = _dataset_with_file(db, owner, restricted=True)

    assert db.dataset_files(file_uuid=public_file, account_uuid=None)
    assert db.dataset_files(file_uuid=restricted_file, account_uuid=None) == []


def test_owner_still_sees_restricted_file(db):
    owner = db.insert_account(email="o@4tu.nl", first_name="O", last_name="W")
    restricted_file = _dataset_with_file(db, owner, restricted=True)
    assert db.dataset_files(file_uuid=restricted_file, account_uuid=owner)
