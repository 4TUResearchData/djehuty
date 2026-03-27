"""
Account lookup helpers that query the SPARQL database directly.

These helpers bypass the UI to reliably find account UUIDs for
impersonation and access control tests.
"""

from typing import Optional

import requests

from config import SPARQL_URL, SPARQL_GRAPH, ADMIN_EMAIL


def _sparql_query(query: str) -> list[dict]:
    """Execute a SPARQL SELECT query and return the bindings as dicts."""
    response = requests.get(
        SPARQL_URL,
        params={"query": query},
        headers={"Accept": "application/sparql-results+json"},
    )
    response.raise_for_status()
    bindings = response.json()["results"]["bindings"]
    return [{k: v["value"] for k, v in row.items()} for row in bindings]


def get_accounts(limit: int = 100) -> list[dict]:
    """Return accounts as a list of dicts with ``uuid`` and ``email`` keys."""
    return _sparql_query(f"""
        PREFIX djht: <https://ontologies.data.4tu.nl/djehuty/0.0.1/>
        SELECT ?uuid ?email WHERE {{
          GRAPH <{SPARQL_GRAPH}> {{
            ?account a djht:Account .
            ?account djht:email ?email .
          }}
          BIND(STRAFTER(STR(?account), "account:") AS ?uuid)
        }} LIMIT {limit}
    """)


def get_account_uuid(email: str) -> Optional[str]:
    """Return the UUID for an account identified by email, or None."""
    rows = _sparql_query(f"""
        PREFIX djht: <https://ontologies.data.4tu.nl/djehuty/0.0.1/>
        PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
        SELECT ?uuid WHERE {{
          GRAPH <{SPARQL_GRAPH}> {{
            ?account a djht:Account .
            ?account djht:email "{email}"^^xsd:string .
          }}
          BIND(STRAFTER(STR(?account), "account:") AS ?uuid)
        }} LIMIT 1
    """)
    return rows[0]["uuid"] if rows else None


def get_non_admin_account_uuid() -> str:
    """Return the UUID of any account that is not the admin.

    Raises AssertionError if no non-admin accounts exist.
    """
    accounts = get_accounts()
    for account in accounts:
        if account["email"] != ADMIN_EMAIL:
            return account["uuid"]
    raise AssertionError("No non-admin accounts found in the database")
