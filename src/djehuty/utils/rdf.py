"""
This module provides convenience functions for handling RDF.
"""

import uuid
from rdflib import Literal, Namespace, URIRef

BLANK = Namespace("blank:")
ROW   = Namespace("djehuty:")
SG    = Namespace("https://sparqling-genomics.org/0.99.12/")
COL   = Namespace("sg://0.99.12/table2rdf/Column/")

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

def insert_query (state_graph, rdflib_graph):
    """Procedure to generate a SPARQL query to insert triplets."""

    body  = rdflib_graph.serialize(format="ntriples")
    if isinstance(body, bytes):
        body = body.decode('utf-8')

    query = f"INSERT {{ GRAPH <{state_graph}> {{ {body} }} }}"

    return query

def blank_node ():
    """Return a unique blank node."""
    identifier = str(uuid.uuid4())
    return BLANK[identifier]

def unique_node (prefix):
    """Return a unique node using PREFIX."""
    prefix_namespace = Namespace(f"{prefix}:")
    identifier       = str(uuid.uuid4())
    return prefix_namespace[identifier]
