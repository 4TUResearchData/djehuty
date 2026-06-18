"""Tests that --initialize's static triplets are idempotent.

Categories and languages used to be inserted with random per-run UUIDs
(rdf.unique_node), so running --initialize more than once against the same
store duplicated them. They now use deterministic URIs (rdf.stable_node), so
re-inserting yields identical triples instead of duplicates.
"""

from rdflib import Graph, RDF

from djehuty.utils import rdf
from djehuty.backup.database import DatabaseInterface


def _accumulate_static_triplets(runs):
    """Simulate `runs` separate --initialize invocations feeding one store.

    Each invocation builds its own in-memory graph (as the real init does) and
    pushes it into a single shared 'live' graph.
    """
    live = Graph()
    for _ in range(runs):
        interface = DatabaseInterface()
        interface.insert_static_triplets()
        for triple in interface.store:
            live.add(triple)
    return live


class TestInitializeIdempotent:
    def test_stable_node_is_deterministic_and_uuid_shaped(self):
        first = rdf.stable_node("category", 13431)
        second = rdf.stable_node("category", 13431)
        assert str(first) == str(second)
        # Same prefix:<uuid> shape as unique_node, so uri_to_uuid still works.
        assert str(first).startswith("category:")
        assert rdf.unique_node("category") != first

    def test_categories_not_duplicated_across_runs(self):
        one = _accumulate_static_triplets(1)
        two = _accumulate_static_triplets(2)

        categories_one = set(one.subjects(RDF.type, rdf.DJHT["Category"]))
        categories_two = set(two.subjects(RDF.type, rdf.DJHT["Category"]))

        assert categories_two == categories_one
        # No duplicate ids either: one id triple per distinct category.
        id_triples = [o for s in categories_two
                      for o in two.objects(s, rdf.DJHT["id"])]
        assert len(id_triples) == len(categories_two)

    def test_languages_not_duplicated_across_runs(self):
        one = _accumulate_static_triplets(1)
        two = _accumulate_static_triplets(2)

        languages_one = set(one.subjects(RDF.type, rdf.DJHT["Language"]))
        languages_two = set(two.subjects(RDF.type, rdf.DJHT["Language"]))

        assert languages_two == languages_one
