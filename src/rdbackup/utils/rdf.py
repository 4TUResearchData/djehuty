"""
This module provides convenience functions for handling RDF.
"""

from rdflib import Literal, Namespace

def add (graph, subject, predicate, value):
    """Adds the triplet SUBJECT PREDICATE VALUE if VALUE is set."""
    if value is not None:
        graph.add((subject, predicate, Literal(value)))

ROW = Namespace("origin://rdbackup#")
SG  = Namespace("https://sparqling-genomics.org/0.99.12/")
COL = Namespace("sg://0.99.12/table2rdf/Column/")
