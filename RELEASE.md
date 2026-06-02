# Release Process

Releases are automated by GitHub Actions. Pushing a version tag builds the artifacts and waits for a maintainer approval.

Once approved, the container image is pushed to GHCR, the package is published to PyPI, and a GitHub Release is drafted.

## How to release

1. **Bump the version** in `pyproject.toml` (e.g. `version = "26.3"`), open a PR, and merge it to `main`.

2. **Tag the merge commit and push the tag.** The tag must match `X.Y` (digits only, no `v` prefix) and match the version in `pyproject.toml`:
   ```sh
   git checkout main
   git pull
   git tag 26.3
   git push origin 26.3
   ```

3. **Approve the release.** In the `Release` workflow on GitHub Actions, the `approve` job waits on the `release` environment for a maintainer approval. Approving it unblocks the GHCR push, the PyPI publish, and the GitHub Release in one go. Nothing is published before approval.

## What gets published

- Container image `ghcr.io/4TUResearchData/djehuty:26.3` and `:latest`
- GitHub Release with auto-generated notes, sdist + wheel attached
- PyPI package `djehuty` (sdist + wheel) via [Trusted Publisher](https://docs.pypi.org/trusted-publishers/) — no API token needed
