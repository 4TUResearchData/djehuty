"""
This module provides convenience functions for handling RDF.
"""

from rdflib import Literal, Namespace, URIRef

def add (graph, subject, predicate, value, datatype=None):
    """Adds the triplet SUBJECT PREDICATE VALUE if VALUE is set."""
    if value is not None:
        if datatype in ("url", "uri"):
            graph.add ((subject, predicate, URIRef(value)))
        else:
            graph.add((subject, predicate, Literal(value, datatype=datatype)))

def sparql_filter (name, value, escape=False):
    """Returns a FILTER statement that can be added to a SPARQL query."""
    query   = ""
    literal = f"\"{value}\"" if escape else value
    symbol  = f"STR(?{name})" if escape else f"?{name}"

    if value is not None:
        query += f"FILTER ({symbol}={literal})\n"

    return query

def sparql_bound_filter (name):
    """Returns a FILTER statement to test whether a variable is BOUND."""
    return f"FILTER (BOUND(?{name}))\n"

def sparql_suffix (order, order_direction, limit=None, offset=None):
    """Returns a query suffix including order, limit and offset."""

    if order_direction is None:
        order_direction = "DESC"
    else:
        order_direction = order_direction.upper()

    query = ""
    if order and order_direction:
        if order[0] != '?':
            order = f"?{order}"
        query += f"ORDER BY {order_direction}({order})"

    if limit is not None:
        query += f"\nLIMIT {limit}"

    if offset is not None:
        query += f"\nOFFSET {offset}"

    return query

ROW = Namespace("origin://djehuty#")
SG  = Namespace("https://sparqling-genomics.org/0.99.12/")
COL = Namespace("sg://0.99.12/table2rdf/Column/")
