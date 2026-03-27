"""
Helpers for creating and querying quota requests via the API.
"""

from playwright.sync_api import Page

from config import SPARQL_URL, SPARQL_GRAPH


def create_quota_request(page: Page, quota_gb: int = 10, reason: str = "E2E test quota request") -> None:
    """Create a quota request via the profile API.

    The page must be authenticated.
    """
    response = page.request.post(
        "/v3/profile/quota-request",
        data={"new-quota": quota_gb, "reason": reason},
    )
    assert response.ok, f"Quota request failed: {response.status} {response.text()}"


def get_pending_quota_request_uuid() -> str | None:
    """Query SPARQL for a pending (unresolved) quota request UUID."""
    import requests

    query = f"""
        PREFIX djht: <https://ontologies.data.4tu.nl/djehuty/0.0.1/>
        SELECT ?uuid WHERE {{
          GRAPH <{SPARQL_GRAPH}> {{
            ?request a djht:QuotaRequest .
            ?request djht:status "unresolved" .
          }}
          BIND(STRAFTER(STR(?request), "quota_request:") AS ?uuid)
        }} LIMIT 1
    """
    resp = requests.get(
        SPARQL_URL,
        params={"query": query},
        headers={"Accept": "application/sparql-results+json"},
    )
    resp.raise_for_status()
    bindings = resp.json()["results"]["bindings"]
    if bindings:
        return bindings[0]["uuid"]["value"]
    return None
