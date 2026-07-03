"""
Shared git repository helpers.

Extracted from ``djehuty.web.wsgi`` so the FastAPI git endpoints (REST
helpers + smart-HTTP protocol) can serve repositories identically to
the legacy implementation.

All functions take whatever state they need as arguments (``db``,
``account_uuid``, ``dataset_id``) and do not depend on the legacy
``ApiServer`` instance.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime

import pygit2

from djehuty.utils.constants import filetypes_by_extension
from djehuty.utils.convenience import value_or, value_or_none
from djehuty.web.config import config

_log = logging.getLogger(__name__)


def repository_url_for_dataset(dataset: dict) -> str | None:
    """Return the Git URL when a repository exists for DATASET or None otherwise.

    Mirrors ``ApiServer.__git_repository_url_for_dataset``.
    """
    git_repository_url = None
    if dataset.get("defined_type_name") == "software":
        try:
            if os.path.exists(os.path.join(config.storage, f"{dataset['git_uuid']}.git")):
                git_repository_url = f"{config.base_url}/v3/datasets/{dataset['git_uuid']}.git"
        except KeyError:
            pass

    return git_repository_url


def default_branch_guess(repository: "pygit2.Repository") -> str | None:
    """Return the repository's default branch, or guess one and persist it.

    Mirrors ``ApiServer.__git_repository_default_branch_guess``.
    """
    branch_name: str | None = None

    head_reference = repository.references.get("HEAD")
    try:
        head_reference = head_reference.resolve() if head_reference else None
    except pygit2.GitError as error:  # pylint: disable=no-member
        _log.error(
            "Failed to resolve git repository HEAD for '%s': %s",
            repository.path,
            error,
        )
        head_reference = None
    except KeyError as error:
        _log.error(
            "HEAD points to non-existing branch for '%s': %s",
            repository.path,
            error,
        )
        head_reference = None

    if head_reference is not None:
        try:
            name = head_reference.name
            if name.startswith("refs/heads/"):
                branch_name = name[11:]
        except AttributeError:
            pass

    if branch_name is None:
        branches = list(repository.branches.local)
        if branches:
            branch_name = branches[0]
            if "master" in branches:
                branch_name = "master"
            elif "main" in branches:
                branch_name = "main"
            set_default_branch(repository, branch_name)

    return branch_name


def set_default_branch(repository: "pygit2.Repository", branch_name: str) -> bool:
    """Set the symbolic HEAD reference for the repository."""
    if branch_name is None:
        return False
    try:
        repository.set_head(f"refs/heads/{branch_name}")
        repository.references.compress()
        return True
    except (pygit2.GitError, KeyError) as error:  # pylint: disable=no-member
        _log.error(
            "Failed to set default branch '%s' on '%s': %s",
            branch_name,
            repository.path,
            error,
        )
        return False


def add_or_update_git_uuid_for_dataset(db, dataset: dict, account_uuid: str) -> bool:
    """Assign (or refresh) the Git UUID for DATASET.

    Mirrors ``ApiServer.__add_or_update_git_uuid_for_dataset``.
    """
    if "uuid" not in dataset:
        _log.error("Refusing to update Git UUID for dataset without UUID.")
        return False

    succeeded, git_uuid = db.update_dataset_git_uuid(dataset["uuid"], account_uuid)
    if not succeeded:
        _log.error("Updating the Git UUID of '%s' failed.", dataset["uuid"])
        return False

    _log.info("Updated the Git UUID of '%s'.", dataset["uuid"])
    dataset["git_uuid"] = git_uuid
    return True


def repository_by_dataset_id(
    db, account_uuid: str, dataset_id, action: str = "read"
) -> "pygit2.Repository | None":
    """Resolve a dataset to its git repository (or ``None`` if unavailable).

    Returns ``None`` for any failure: dataset not found / not owned,
    insufficient collaborative ``data_{action}`` permission, git repo directory
    missing, etc. The caller maps this to 404 like the legacy handlers do --
    note legacy deliberately hides a git permission denial as 404, not 403.
    """
    from djehuty.utils.convenience import parses_to_int

    try:
        if parses_to_int(dataset_id):
            datasets = db.datasets(
                dataset_id=int(dataset_id),
                account_uuid=account_uuid,
                is_published=False,
                limit=1,
            )
        else:
            datasets = db.datasets(
                container_uuid=str(dataset_id),
                account_uuid=account_uuid,
                is_published=False,
                limit=1,
            )
        dataset = datasets[0]
    except (IndexError, AttributeError, TypeError):
        _log.error("No Git repository for dataset %s.", dataset_id)
        return None

    # AS-IS: a collaborator needs data_{action} (read/edit). On denial legacy
    # returns None -- the caller renders 404, not 403. Owners are unaffected.
    from djehuty.services.permissions import is_permitted

    if not is_permitted(db, account_uuid, dataset, "dataset", f"data_{action}"):
        return None

    # Pre-Djehuty datasets may not have a Git UUID. We therefore
    # assign one when needed.
    if "git_uuid" not in dataset:
        if not add_or_update_git_uuid_for_dataset(db, dataset, account_uuid):
            _log.error("Failed to add 'git_uuid' for dataset.")
            return None

    git_directory = os.path.join(config.storage, f"{dataset['git_uuid']}.git")
    if not os.path.exists(git_directory):
        _log.error("No Git repository at '%s'", git_directory)
        return None

    return pygit2.Repository(git_directory)


def create_repository(git_uuid: str) -> bool:
    """Create the on-disk bare repository for GIT_UUID when it does not exist.

    Mirrors ``ApiServer.__git_create_repository``: initialises a bare
    repository and enables receive-pack over smart-HTTP in its config file.
    Refuses a git_uuid that is not a UUID, so a caller cannot turn it into a
    path outside ``config.storage``.
    """
    from djehuty.web import validator

    if not validator.is_valid_uuid(git_uuid):
        return False
    git_directory = os.path.join(config.storage, f"{git_uuid}.git")
    if not os.path.exists(git_directory):
        initial_repository = pygit2.init_repository(git_directory, True)
        if not initial_repository:
            return False
        try:
            with open(os.path.join(git_directory, "config"), "a", encoding="utf-8") as git_config:
                git_config.write("\n[http]\n  receivepack = true\n")
        except FileNotFoundError:
            _log.error("%s/config does not exist.", git_directory)
            return False
        except OSError:
            _log.error("Could not open %s/config", git_directory)
            return False

    return True


def head_reference_target(repository: "pygit2.Repository"):
    """Return (HEAD reference, target) or (None, None) when unresolvable.

    Mirrors ``ApiServer.__git_head_reference_target``.
    """
    head_reference = repository.references.get("HEAD")
    try:
        head_reference = head_reference.resolve()
    except (KeyError, pygit2.GitError):  # pylint: disable=no-member
        return None, None

    return head_reference, head_reference.target


def files_by_type(tree, path: str = "", output: dict | None = None) -> dict:
    """Return per-language lists of file statistics for the repository TREE.

    Mirrors ``ApiServer.__git_files_by_type``.
    """
    if output is None:
        output = {}

    for entry in tree:
        # Walk the directory tree.
        if isinstance(entry, pygit2.Tree):  # pylint: disable=no-member
            files_by_type(list(entry), f"{path}{entry.name}/", output)
            continue

        # Submodules are represented as commits.
        if isinstance(entry, pygit2.Commit):  # pylint: disable=no-member
            continue

        record = {"filename": f"{path}{entry.name}", "size": entry.size}

        # Skip over binary files and large files.
        if entry.is_binary or entry.size > 5000000:
            extension = "binary" if entry.is_binary else "large-text-file"
            output.setdefault(extension, []).append(record)
            continue

        # Count newlines, plus one for a last line without a newline.
        record["lines"] = entry.data.count(b"\n")
        if entry.data != b"" and entry.data[-1:] != b"\n":
            record["lines"] += 1

        _, extension = os.path.splitext(entry.name)
        extension = "no-extension" if extension == "" else extension.lstrip(".").lower()
        language = value_or_none(filetypes_by_extension, extension)
        if language is None:
            language = "Other"
        output.setdefault(language, []).append(record)

    return output


def languages_summary(db, git_uuid: str, repository: "pygit2.Repository") -> str:
    """Return the languages summary for a repository as a JSON string.

    Mirrors the computation and caching of
    ``ApiServer.api_v3_dataset_git_languages``, including the
    double-JSON-encoded cache entries it writes.
    """
    head, target = head_reference_target(repository)

    # No target means it's an empty repository.
    if target is None:
        return json.dumps({"Other": 0})

    cache_key = f"{git_uuid}_{target}"
    cache_prefix = "git_languages"
    cached_value = db.cache.cached_value(cache_prefix, cache_key)
    if cached_value:
        return cached_value

    commit = head.peel()
    if not isinstance(commit, pygit2.Commit):  # pylint: disable=no-member
        return json.dumps({"Other": 0})

    statistics = files_by_type(commit.tree)

    # Drop the binary count from the statistics, because we only
    # generate a summary with line counts below.
    statistics.pop("binary", None)

    summary = {}
    for extension in statistics:
        num_bytes_for_extension = 0
        for entry in statistics[extension]:
            num_lines = value_or(entry, "lines", 0)
            num_bytes = value_or(entry, "size", 0)
            # Remove minified sources by the heuristic that the average
            # line length must be smaller than 300 bytes long.  This seems
            # to come close to how Github reports the statistics.
            if num_lines > 0 and num_bytes / num_lines < 300:
                num_bytes_for_extension += num_bytes

        summary[extension] = num_bytes_for_extension

    sorted_summary = dict(sorted(summary.items(), key=lambda item: item[1], reverse=True))
    db.cache.cache_value(cache_prefix, cache_key, json.dumps(sorted_summary))
    return json.dumps(sorted_summary)


def contributors(db, git_uuid: str, repository: "pygit2.Repository") -> list | None:
    """Return contributors with their commit statistics, or None when empty.

    Mirrors ``ApiServer.__git_contributors``: GitHub-style records keyed by
    author e-mail with per-week additions/deletions/commit counts.
    """
    _, target = head_reference_target(repository)
    if target is None:
        return []

    history = repository.walk(target, pygit2.enums.SortMode.REVERSE)
    cache_key = f"{git_uuid}_{target}"
    cache_prefix = "git_contributors"
    cached_value = db.cache.cached_value(cache_prefix, cache_key)
    if cached_value:
        return cached_value

    commits = list(history)
    if not commits:
        return None

    # Accounting for the initial commit.
    records: dict = {}
    previous_commit = commits[0]
    stats = files_by_type(previous_commit.tree)
    total_lines = 0
    for extension in stats:
        for entry in stats[extension]:
            total_lines += value_or(entry, "lines", 0)

    week = datetime.fromtimestamp(previous_commit.commit_time).isocalendar()
    week = int(datetime.fromisocalendar(week[0], week[1], 1).timestamp())

    records[previous_commit.author.email] = {
        "total": 1,
        "additions": total_lines,
        "deletions": 0,
        "weeks": {week: {"w": week, "a": total_lines, "d": 0, "c": 1}},
        "author": {
            "name": previous_commit.author.name,
            "email": previous_commit.author.email,
        },
    }

    # Walk the repository's history.
    for commit in commits[1:]:
        stats = repository.diff(previous_commit, commit).stats
        week = datetime.fromtimestamp(commit.commit_time).isocalendar()
        week = int(datetime.fromisocalendar(week[0], week[1], 1).timestamp())
        if commit.author.email not in records:
            records[commit.author.email] = {
                "total": 0,
                "additions": 0,
                "deletions": 0,
                "weeks": {week: {"w": week, "c": 0, "a": 0, "d": 0}},
                "author": {"name": commit.author.name, "email": commit.author.email},
            }
        record = records[commit.author.email]
        if "weeks" in record and week in record["weeks"]:
            record["weeks"][week]["c"] += 1
            record["weeks"][week]["a"] += stats.insertions
            record["weeks"][week]["d"] += stats.deletions
        else:
            record["weeks"][week] = {
                "w": week,
                "c": 1,
                "a": stats.insertions,
                "d": stats.deletions,
            }
        record["total"] += 1
        record["additions"] += stats.insertions
        record["deletions"] += stats.deletions

        previous_commit = commit

    # Flatten the structure.
    flattened = list(records.values())
    for contributor in flattened:
        contributor["weeks"] = list(contributor["weeks"].values())

    db.cache.cache_value(cache_prefix, cache_key, flattened)
    return flattened
