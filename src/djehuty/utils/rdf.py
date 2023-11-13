"""
This module provides convenience functions for handling RDF.
"""

import re
import uuid
from rdflib import Literal, Namespace, URIRef, XSD

BLANK = Namespace("blank:")
ROW   = Namespace("djehuty:")
DJHT  = Namespace("https://ontologies.data.4tu.nl/djehuty/0.0.1/")

## Pre-compiled patterns for determining the SPARQL query type.
COMMENTS_PATTERN = re.compile(r"(^|\n)\s*#.*?\n")
PREFIX_PATTERN   = re.compile(
    r"((?P<base>(\s*BASE\s*<.*?>)\s*)|(?P<prefixes>(\s*PREFIX\s+.+:\s*<.*?>)\s*))*"
)
QUERY_PATTERN    = re.compile(
    r"(?P<queryType>(CONSTRUCT|SELECT|ASK|DESCRIBE|INSERT|DELETE|CREATE|CLEAR|DROP|LOAD|COPY|MOVE|ADD))",
    re.VERBOSE | re.IGNORECASE,
)

def query_type (query):
    """
    Returns two values. The first value is 'update' for state-modifying
    queries, 'gather' for read-only queries, None when parsing failed.
    The second value is the more precise query type, like SELECT, INSERT
    or DELETE, or None when parsing failed.

    The implementation is based on SPARQLWrapper's implementation.
    """

    query_wo_comments = re.sub(COMMENTS_PATTERN, "\n\n", query)
    simplified_query  = re.sub(PREFIX_PATTERN, "", query_wo_comments.strip())
    try:
        sparql_type = str(QUERY_PATTERN.search(simplified_query).group("queryType").upper())
        if sparql_type in [ "SELECT", "CONSTRUCT", "ASK" ]:
            return "gather", sparql_type
        if sparql_type in [ "INSERT", "DELETE", "CLEAR", "DROP", "LOAD"]:
            return "update", sparql_type
    except AttributeError:
        pass

    return None, None

def add (graph, subject, predicate, value, datatype=None):
    """Adds the triplet SUBJECT PREDICATE VALUE if VALUE is set."""
    if value is not None:
        if isinstance (value, str) and value == "" and datatype == XSD.integer:
            return None

        if datatype in ("url", "uri"):
            graph.add ((subject, predicate, URIRef(value)))
        else:
            graph.add((subject, predicate, Literal(value, datatype=datatype)))

    return None

def urify_value (value):
    """Returns a string including smaller-than and greater-than brackets."""
    if isinstance(value, str) and value.startswith ("<"):
        return value

    return f"<{value}>"

def sparql_filter (name, value, escape=False, is_uri=False):
    """Returns a FILTER statement that can be added to a SPARQL query."""
    query   = ""
    if value is None:
        return query

    if is_uri:
        query  += f"FILTER (?{name} = {urify_value(value)})\n"
    else:
        # Wrapping the xsd:string in STR ensures compatibility with Virtuoso.
        literal = f"STR({escape_value (value, XSD.string)})" if escape else value
        symbol  = f"STR(?{name})" if escape else f"?{name}"
        query  += f"FILTER ({symbol}={literal})\n"

    return query

def escape_value (value, datatype=None):
    """Returns VALUE wrapped in double quotes with type annotation DATATYPE."""
    if value is None:
        return None

    return Literal(value, datatype=datatype).n3()

def escape_string_value (value):
    """Returns VALUE wrapped in double quotes and annotated as xsd:string."""
    return escape_value (value, datatype=XSD.string)

def escape_date_value (value):
    """Returns VALUE wrapped in double quotes and annotated as xsd:date."""
    return escape_value (value, datatype=XSD.date)

def escape_datetime_value (value):
    """Returns VALUE wrapped in double quotes and annotated as xsd:dateTime."""
    return escape_value (value, datatype=XSD.dateTime)

def escape_boolean_value (value):
    """Returns VALUE wrapped in double quotes and annotated as xsd:date."""
    return escape_value (value, datatype=XSD.boolean)

def sparql_in_filter (name, values, escape=False, is_uri=False, negate=False):
    """Returns a FILTER statement for a list of values."""
    query   = ""
    # This is a deliberate loose check. We catch [], "", and None this way.
    if not values:
        return query

    compare = "NOT IN" if negate else "IN"
    if is_uri:
        query += f"FILTER (?{name} {compare} ({','.join(map(urify_value, values))}))\n"
    else:
        symbol = f"STR(?{name})" if escape else f"?{name}"
        escape_function = escape_string_value if escape else str
        query += f"FILTER (({symbol}) {compare} ({','.join(map(escape_function, values))}))\n"

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

    query = f"INSERT DATA {{ GRAPH <{state_graph}> {{ {body} }} }}"

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

def uri_to_uuid (uri):
    """Returns the UUID of a URI created by 'unique_node' or 'blank_node'."""
    if uri is None:
        return None

    return uri[uri.find(":") + 1:]

def uuid_to_uri (uuid_value, datatype):
    """Returns a string of the full uri for UUID of type DATATYPE."""
    if uuid_value is None:
        return None

    return f"{datatype}:{uuid_value}"

def uris_from_records (records, prefix, uuid_index=None):
    """Returns URIRefs for a list of RECORDS of type PREFIX."""

    ## The UUID is sometimes a property of record, as in record["uuid"],
    ## while at other times the UUID is the record itself.

    if uuid_index is not None:
        return list(map (lambda record: URIRef(uuid_to_uri (
            record[uuid_index], prefix)), records))

    return list(map (lambda record: URIRef(
        uuid_to_uri (record, prefix)), records))
