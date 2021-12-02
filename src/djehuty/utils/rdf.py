"""
This module provides convenience functions for handling RDF.
"""

from rdflib import Literal, Namespace

def add (graph, subject, predicate, value):
    """Adds the triplet SUBJECT PREDICATE VALUE if VALUE is set."""
    if value is not None:
        graph.add((subject, predicate, Literal(value)))


def sparql_filter (name, value, escape=False):
    query   = ""
    literal = f"\"{value}\"" if escape else value
    if value is not None:
        query += f"FILTER (?{name}={literal})\n"

    return query

def sparql_suffix (order, order_direction, limit=None, offset=None):
    if order_direction is None:
        order_direction = "DESC"
    else:
        order_direction = order_direction.upper()

    order = "?id" if order is not None else f"?{order}"

    query = f"ORDER BY {order_direction}({order})"

    if limit is not None:
        query += f"\nLIMIT {limit}"

    if offset is not None:
        query += f"\nOFFSET {offset}"

    return query

ROW = Namespace("origin://djehuty#")
SG  = Namespace("https://sparqling-genomics.org/0.99.12/")
COL = Namespace("sg://0.99.12/table2rdf/Column/")
