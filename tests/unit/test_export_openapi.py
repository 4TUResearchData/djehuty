"""Unit tests for the static API documentation export (djehuty.api.export_openapi).

Pins the properties the published documentation depends on: one document per
API version plus a combined one, each filtered to its own paths, each pointing
at an absolute server, and an index page that references the schemas next to it
by relative URL.
"""

import json
import re

import pytest

from djehuty.api.export_openapi import build_documents, write_documents, write_index
from djehuty.application import API_VERSIONS

SERVER_URL = "https://example.org"


def _stems():
    return {"swagger", *(f"swagger-{version}" for version in API_VERSIONS)}


def _index_urls(out_dir):
    """Return the schema URLs the generated page tells Swagger UI to load."""
    html = (out_dir / "index.html").read_text(encoding="utf-8")
    match = re.search(r"urls: (\[.*?\])", html)
    assert match, "the generated page declares no urls array"
    return [entry["url"] for entry in json.loads(match.group(1))]


@pytest.fixture(scope="module")
def documents():
    return build_documents(SERVER_URL)


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    out_dir = tmp_path_factory.mktemp("api")
    write_documents(out_dir, SERVER_URL)
    write_index(out_dir, SERVER_URL)
    return out_dir


@pytest.fixture(scope="module")
def exported_without_server(tmp_path_factory):
    out_dir = tmp_path_factory.mktemp("api-no-server")
    write_documents(out_dir)
    write_index(out_dir)
    return out_dir


def test_documents_cover_the_combined_schema_and_every_version(documents):
    assert set(documents) == _stems()


def test_each_version_document_holds_only_that_version(documents):
    for version in API_VERSIONS:
        paths = documents[f"swagger-{version}"]["paths"]
        assert paths, f"no paths were kept for {version}"
        assert all(path.startswith(f"/{version}") for path in paths)


def test_version_documents_are_strict_subsets_of_the_combined_one(documents):
    # A filter that matched everything (an "/v" prefix, say) would still pass
    # the per-version check above, so also assert something was left out.
    combined = set(documents["swagger"]["paths"])
    for version in API_VERSIONS:
        assert set(documents[f"swagger-{version}"]["paths"]) < combined


def test_every_document_points_at_the_given_server(documents):
    for schema in documents.values():
        assert [server["url"] for server in schema["servers"]] == [SERVER_URL]


def test_documents_name_no_instance_by_default():
    # djehuty is deployed by more than one institution, so an export that was
    # not told where the API lives must not guess.
    for schema in build_documents().values():
        assert "servers" not in schema


def test_index_offers_try_it_out_only_with_a_server(exported, exported_without_server):
    # Without a server the published page has no API to reach, so the submit
    # button would fail on every endpoint.
    with_server = (exported / "index.html").read_text(encoding="utf-8")
    without_server = (exported_without_server / "index.html").read_text(encoding="utf-8")
    assert "supportedSubmitMethods" not in with_server
    assert "supportedSubmitMethods: []" in without_server


def test_written_documents_are_valid_openapi_json(exported):
    for stem in _stems():
        schema = json.loads((exported / f"{stem}.json").read_text(encoding="utf-8"))
        assert schema["openapi"]
        assert schema["paths"]


def test_index_offers_every_version_and_the_combined_schema(exported):
    expected = {"swagger.json", *(f"swagger-{version}.json" for version in API_VERSIONS)}
    assert set(_index_urls(exported)) == expected


def test_index_references_only_files_that_exist(exported):
    # write_index and write_documents agree on file names by convention only,
    # so renaming one side without the other must fail here.
    for url in _index_urls(exported):
        assert (exported / url).is_file(), f"the page references a missing {url}"


def test_index_urls_are_relative(exported):
    # The directory is published under /api/ on one host and /djehuty/api/ on
    # another, so the page must not name the schemas by absolute path or URL.
    for url in _index_urls(exported):
        assert not url.startswith("/"), url
        assert "://" not in url, url
