"""Unit tests for the tombstone page served for retracted datasets."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import DictLoader, Environment

from djehuty.web import wsgi
from djehuty.web.wsgi import WebServer

TEMPLATE = Path(wsgi.__file__).parent / "resources" / "html_templates" / "410.html"
LAYOUT = "<head>{% block headers %}{% endblock %}</head><body>{% block body %}{% endblock %}</body>"
CONTAINER = "cccccccc-cccc-cccc-cccc-cccccccccccc"

ITEM = {
    "uri": "dataset:1",
    "title": "Penguins <b>&</b> more",
    "doi": "10.4121/x.v1",
    "container_doi": "10.4121/x",
    "publisher": "4TU.ResearchData",
}
AUTHORS = [{"full_name": "Ada Lovelace"}, {"full_name": "Grace Hopper"}]


def _render(**context):
    environment = Environment(
        autoescape=True,
        loader=DictLoader(
            {"layout.html": LAYOUT, "410.html": TEMPLATE.read_text(encoding="utf-8")}
        ),
    )
    return environment.get_template("410.html").render(**context)


class TestTombstoneTemplate:
    def test_versioned_page_cites_the_version_doi(self):
        html = _render(item=ITEM, authors=AUTHORS, version="1")
        assert '<link rel="cite-as" href="https://doi.org/10.4121/x.v1">' in html
        assert '<meta name="DC.identifier" content="https://doi.org/10.4121/x.v1">' in html
        assert '<a href="https://doi.org/10.4121/x.v1">https://doi.org/10.4121/x.v1</a>' in html
        assert "(version 1)" in html

    def test_container_page_cites_the_container_doi(self):
        html = _render(item=ITEM, authors=AUTHORS, version=None)
        assert 'rel="cite-as" href="https://doi.org/10.4121/x"' in html
        assert "(version" not in html

    def test_names_title_authors_and_unavailability(self):
        html = _render(item=ITEM, authors=AUTHORS, version="1")
        assert "Ada Lovelace; Grace Hopper" in html
        assert "no longer available" in html

    def test_citation_has_the_publication_year_and_retraction_date(self):
        item = dict(
            ITEM,
            retracted_published_date="2026-04-01T12:00:00",
            retracted_date="2026-11-09T15:49:29",
        )
        html = _render(item=item, authors=AUTHORS, version="1")
        assert "Grace Hopper (2026)." in html
        assert "retracted by the repository administrators on 2026-11-09 and" in html

    def test_citation_without_dates_has_no_year_or_retraction_date(self):
        html = _render(item=ITEM, authors=AUTHORS, version="1")
        assert "Grace Hopper." in html
        assert "(20" not in html
        assert "administrators and is no longer available" in html

    def test_title_is_escaped(self):
        html = _render(item=ITEM, authors=AUTHORS, version="1")
        assert "<b>&</b>" not in html
        assert "Penguins &lt;b&gt;&amp;&lt;/b&gt; more" in html

    def test_generic_page_without_item(self):
        html = _render(item=None, authors=[], version=None)
        assert "has been retracted" in html
        assert "cite-as" not in html


def _server(datasets):
    """A WebServer stand-in. DATASETS maps a lookup kind to the dataset it finds."""
    calls = []
    server = SimpleNamespace(calls=calls)
    server.default_error_handling = lambda request, methods, content_type: None
    server.error_404 = lambda request: "404"
    server.error_410 = lambda request, item=None, version=None: ("410", item, version)

    def lookup(identifier, **parameters):
        calls.append(parameters)
        if parameters["is_published"] is None:
            return datasets["retracted"]
        return datasets["public"]

    server._WebServer__dataset_by_id_or_uri = lookup
    return server


class TestUiDatasetFallback:
    def test_fallback_looks_up_the_requested_version(self):
        retracted = {"uri": "dataset:1", "is_public": 0}
        server = _server({"public": None, "retracted": retracted})

        response = WebServer.ui_dataset(server, object(), CONTAINER, "1")

        assert response == ("410", retracted, "1")
        assert server.calls[-1]["version"] == "1"

    def test_missing_dataset_is_404(self):
        server = _server({"public": None, "retracted": None})
        assert WebServer.ui_dataset(server, object(), CONTAINER, "1") == "404"

    @pytest.mark.parametrize("flag", [1, None])
    def test_public_record_in_fallback_is_404(self, flag):
        record = {"uri": "dataset:1"}
        if flag is not None:
            record["is_public"] = flag
        server = _server({"public": None, "retracted": record})
        assert WebServer.ui_dataset(server, object(), CONTAINER, "1") == "404"


class TestError410:
    def _error_410_server(self, authors):
        rendered = {}
        server = SimpleNamespace(rendered=rendered)
        server.accepts_html = lambda request, strict=False: True
        server.db = SimpleNamespace(authors=lambda **kwargs: authors)

        def render(request, template, **context):
            rendered.update(template=template, **context)
            return SimpleNamespace(status_code=200)

        server._WebServer__render_template = render
        return server

    def test_item_and_authors_reach_the_template(self):
        server = self._error_410_server(AUTHORS)
        response = WebServer.error_410(server, object(), ITEM, "1")
        assert response.status_code == 410
        assert server.rendered["item"] is ITEM
        assert server.rendered["authors"] == AUTHORS
        assert server.rendered["version"] == "1"

    def test_generic_page_does_not_query_authors(self):
        server = self._error_410_server(None)
        response = WebServer.error_410(server, object())
        assert response.status_code == 410
        assert server.rendered["authors"] == []
