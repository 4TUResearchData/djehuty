"""Search regression: the tags list is joined only when a filter needs it.

``datasets`` used to join ``djht:tags/rdf:rest*/rdf:first`` on every search,
which multiplies intermediate solutions by the number of tags on each dataset.
The join is now rendered only when a filter actually references ``?tag``. These
tests pin both halves of that: a tag search still finds its matches, and a
search that does not mention tags returns the same datasets, each exactly once.

Uses the real ``SparqlInterface`` against an in-memory rdflib store (same
approach as ``test_security_restricted_file_download``), so no Virtuoso is
needed. The datasets are searched as published versions, which is the path the
public search endpoint takes (``is_published`` defaults to True and nothing
overrides it). ``publish_dataset`` needs scaffolding this store does not have,
so the fixture links the ``published_versions`` list node directly.
"""

import tempfile

import pytest
from rdflib import RDFS, Graph, URIRef

from djehuty.utils import rdf
from djehuty.web.config import config
from djehuty.web.database import SparqlInterface

MANY_TAGS = "Solar panel measurements"
ONE_TAG = "Solar wind survey"
NO_TAGS = "Solar eclipse notes"


def publish(db, container_uuid, version_uuid):
    """Add VERSION_UUID to the container's published_versions list."""

    node = db.wrap_in_blank_node(version_uuid, "dataset", index=1)
    graph = Graph()
    rdf.add(
        graph,
        URIRef(rdf.uuid_to_uri(container_uuid, "container")),
        rdf.DJHT["published_versions"],
        node,
        "url",
    )
    assert db.add_triples_from_graph(graph)


@pytest.fixture
def db():
    config.endpoint = "memory://test"
    config.update_endpoint = None
    config.state_graph = "https://data.4tu.nl/portal/test"
    interface = SparqlInterface()
    interface.setup_sparql_endpoint()
    interface.cache.storage = tempfile.mkdtemp()
    graph = Graph()
    graph.add((rdf.DJHT["DatasetContainer"], RDFS.subClassOf, rdf.DJHT["Container"]))
    interface.add_triples_from_graph(graph)

    owner = interface.insert_account(email="o@4tu.nl", first_name="O", last_name="W")
    # One dataset with several tags, one with a single tag, one with none.
    for title, tags in (
        (MANY_TAGS, [{"tag": "solar"}, {"tag": "energy"}, {"tag": "rooftop"}]),
        (ONE_TAG, [{"tag": "solar"}]),
        (NO_TAGS, None),
    ):
        container_uuid, version_uuid = interface.insert_dataset(
            title=title, account_uuid=owner, tags=tags
        )
        publish(interface, container_uuid, version_uuid)
    return interface


def search(db, term, scope):
    """Run a v3 search for TERM over SCOPE and return the titles found."""

    records = db.datasets(
        search_for={"search_for": [term], "operator": "OR", "scope": scope},
        limit=100,
        use_cache=False,
    )
    return [record["title"] for record in records]


def test_tag_scoped_search_still_matches(db):
    """Asserting the exact set also proves the scope is applied: all three
    datasets have 'Solar' in their title, so a tag search returning three
    would mean the scope had been ignored."""

    titles = search(db, "solar", ["tag"])
    assert sorted(titles) == sorted([MANY_TAGS, ONE_TAG])


def test_title_scoped_search_returns_each_dataset_once(db):
    """Without the tags join, the multi-tag dataset must still appear once."""

    titles = search(db, "solar", ["title"])
    assert sorted(titles) == sorted([MANY_TAGS, ONE_TAG, NO_TAGS])
    assert titles.count(MANY_TAGS) == 1


def test_tags_are_joined_only_when_a_filter_needs_them(db):
    """The optimisation itself: the join is rendered only for a tag filter."""

    queries = []

    def capture(query, *args, **kwargs):
        queries.append(query)
        return []

    db._SparqlInterface__run_query = capture

    search(db, "solar", ["title"])
    assert "djht:tags/rdf:rest" not in queries[-1]

    search(db, "solar", ["tag"])
    assert "djht:tags/rdf:rest" in queries[-1]

    search(db, "solar", None)
    assert "djht:tags/rdf:rest" in queries[-1]
