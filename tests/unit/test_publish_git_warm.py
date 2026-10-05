"""Unit tests for the publish git-statistics warm path (pins the contract).

Warming runs in-process via repository_by_git_uuid, and is a no-op for datasets
without a repository. Warm failures never surface to the caller.
"""

import djehuty.services.git as git_service
from djehuty.api.v3.datasets.publishing import _warm_git_statistics_caches


def test_in_process_warm_calls_repository_by_git_uuid(monkeypatch):
    recorded = {}
    repo = object()

    monkeypatch.setattr(git_service, "repository_url_for_dataset", lambda d: "http://x/.git")

    def _by_uuid(uuid):
        recorded["by_uuid"] = uuid
        return repo

    def _languages(db, uuid, repository):
        recorded["languages"] = (uuid, repository)
        return "{}"

    def _contributors(db, uuid, repository):
        recorded["contributors"] = (uuid, repository)
        return []

    monkeypatch.setattr(git_service, "repository_by_git_uuid", _by_uuid)
    monkeypatch.setattr(git_service, "default_branch_guess", lambda r: "main")
    monkeypatch.setattr(git_service, "languages_summary", _languages)
    monkeypatch.setattr(git_service, "contributors", _contributors)

    _warm_git_statistics_caches(db=object(), dataset={"git_uuid": "abc"})

    assert recorded["by_uuid"] == "abc"
    assert recorded["languages"][1] is repo
    assert recorded["contributors"][1] is repo


def test_warm_swallows_errors(monkeypatch):
    repo = object()
    monkeypatch.setattr(git_service, "repository_url_for_dataset", lambda d: "http://x/.git")
    monkeypatch.setattr(git_service, "repository_by_git_uuid", lambda u: repo)
    monkeypatch.setattr(git_service, "default_branch_guess", lambda r: "main")

    def _raise(db, uuid, repository):
        raise OSError("git stat failed")

    monkeypatch.setattr(git_service, "languages_summary", _raise)

    # Must not raise: warming is fire-and-forget and never changes the response.
    _warm_git_statistics_caches(db=object(), dataset={"git_uuid": "abc"})


def test_no_git_url_is_a_noop(monkeypatch):
    monkeypatch.setattr(git_service, "repository_url_for_dataset", lambda d: None)

    def _must_not_open(uuid):
        raise AssertionError("non-software datasets have no repository to warm")

    monkeypatch.setattr(git_service, "repository_by_git_uuid", _must_not_open)

    _warm_git_statistics_caches(db=object(), dataset={"git_uuid": "abc"})
