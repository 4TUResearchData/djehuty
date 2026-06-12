# Release Process

Releases are automated by GitHub Actions. Pushing a version tag builds the artifacts and waits for a maintainer approval.

Once approved, the container image is pushed to GHCR, the package is published to PyPI, and a GitHub Release is drafted.

## How to release

1. **Bump the version** in `pyproject.toml` (e.g. `version = "26.3"`) and `configure.ac` (e.g `AC_INIT(djehuty, 26.3)`).

   > [!Note]
   > `configure.ac` will be discontinued on October 31, 2026

2. **Add the release section at the top of `CHANGELOG.md`.** `CHANGELOG.md` is
   the single source of truth for release notes. Maintainers only edit this
   file. Use the same heading style as previous entries:

   ```markdown
   ## [v26.3]

   The third release of 2026 consists of N commits made by N authors.

   ### New features
   - One-line description. ([abc1234](https://github.com/4TUResearchData/djehuty/commit/abc1234…))
   ```

   > [!Note]
   > Allowed section names: `New features`, `UI revisions`, `Security`, `Documentation`, `Bugfixes`, `Incremental improvements`, `Technical debt`.

3. **Sync `doc/news.tex`** so the LaTeX/HTML documentation includes the new release. The `news` recipe reads the top entry of `CHANGELOG.md` and inserts it above the existing first release in `doc/news.tex`:
   ```sh
   just news
   ```

   > [!Note]
   > Re-running is safe — the script refuses to insert a release that is already present.

4. Open a PR with the `pyproject.toml`, `CHANGELOG.md`, and `doc/news.tex`
   changes and merge it to `main`.

   > [!WARNING]
   > Wait the PR is mergerd to go for step 5

5. After the Release PR is merged, **tag the merge commit and push the tag.** The tag must match `vX.Y` or `vX.Y.Z`
   (e.g. `v26.3`, `v26.3.1`) and the numeric part must match the version in `pyproject.toml`:
   ```sh
   git checkout main
   git pull
   git tag v26.3
   git push origin v26.3
   ```

6. **Approve the release.** In the `Release` workflow on GitHub Actions, the `approve` job waits on the `release` environment for a maintainer approval.  
   Approving it unblocks the GHCR push, the PyPI publish, and the
   GitHub Release in one go. Nothing is published before approval.

## What gets published

- Container image `ghcr.io/4TUResearchData/djehuty:<tag>> and `:latest`
- GitHub Release with auto-generated notes, sdist + wheel attached
- PyPI package `djehuty` (sdist + wheel) via [Trusted Publisher](https://docs.pypi.org/trusted-publishers/) — no API token needed
