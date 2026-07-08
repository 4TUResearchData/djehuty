"""
Security regression test: session name escaping.

The session "name" field must be escaped before it reaches the SPARQL store, so
that no value can be interpreted as query syntax rather than data.

The test edits a session through the normal API with a name that includes a
unique marker, then queries the triple store to assert that (a) the marker was
stored only as the session name and (b) it produced no additional triples.
"""

import re
import uuid

import pytest
import requests
from playwright.sync_api import Page

from config import SPARQL_URL, SPARQL_GRAPH


def _sparql_select(query: str) -> list[dict]:
    """Execute a SPARQL SELECT and return bindings as a list of dicts."""
    response = requests.get(
        SPARQL_URL,
        params={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        timeout=30,
    )
    response.raise_for_status()
    bindings = response.json()["results"]["bindings"]
    return [{k: v["value"] for k, v in row.items()} for row in bindings]


@pytest.mark.security
@pytest.mark.auth
class TestSessionNameInjection:
    """The session name must not be usable to inject SPARQL."""

    def test_session_name_cannot_inject_triples(self, authenticated_page: Page):
        # A unique marker. It must only ever appear as the session name; it
        # must never become the subject of a triple of its own.
        canary = f"urn:djehuty-sectest-canary:{uuid.uuid4()}"

        # A name that, if used unescaped, would be parsed as extra triples
        # rather than a single string value. Kept under the 255-char limit.
        payload = (
            f'x"^^xsd:string . <{canary}> <urn:djehuty-sectest:p> "INJECTED"^^xsd:string . '
            '?session djht:name "z'
        )
        assert len(payload) <= 255

        # Create a fresh editable session; the app redirects to its edit page.
        authenticated_page.goto("/my/sessions/new")
        authenticated_page.wait_for_url("**/my/sessions/*/edit**")
        match = re.search(r"/my/sessions/([0-9a-f-]{36})/edit", authenticated_page.url)
        assert match, f"could not obtain session uuid from {authenticated_page.url}"
        session_uuid = match.group(1)

        try:
            # Send the malicious name through the normal edit-session API.
            response = authenticated_page.request.put(
                f"/my/sessions/{session_uuid}/edit",
                data={"name": payload},
            )
            # The request may be accepted (name stored, escaped) or rejected,
            # but it must never result in the injected triple.
            assert response.status in (200, 205, 400), (
                f"unexpected status {response.status}"
            )

            # (a) The canary triple must not exist in ANY graph.
            injected = _sparql_select(
                f"SELECT ?p ?o WHERE {{ GRAPH ?g {{ <{canary}> ?p ?o }} }}"
            )
            assert injected == [], f"SPARQL injection succeeded: {injected}"

            # (b) If accepted, the payload must be stored verbatim as the name,
            # proving it was escaped and treated as a single data literal.
            if response.status in (200, 205):
                rows = _sparql_select(
                    "PREFIX djht: <https://ontologies.data.4tu.nl/djehuty/0.0.1/> "
                    f"SELECT ?name WHERE {{ GRAPH <{SPARQL_GRAPH}> {{ "
                    f"<session:{session_uuid}> djht:name ?name }} }}"
                )
                assert rows, "session name was not stored"
                assert rows[0]["name"] == payload, (
                    "stored name differs from input; escaping altered the value"
                )
        finally:
            # Best-effort cleanup of the throwaway session.
            authenticated_page.request.get(f"/my/sessions/{session_uuid}/delete")
