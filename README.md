djehuty
=========

This Python package provides the repository system for 4TU.ResearchData and Nikhef.

## Security

To report a vulnerability, please see [SECURITY.md](./SECURITY.md).

## Development environment

### Prerequisites

- [Git](https://git-scm.com/downloads)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Docker](https://docs.docker.com/get-docker/) (with Compose)
- [just](https://github.com/casey/just#installation)

### Getting started

```bash
git clone https://github.com/4TUResearchData/djehuty.git
cd djehuty/
```

### Running the development environment

To spin up a fully working local instance, run:

```bash
just dev
```

This builds and starts Docker containers for djehuty and
[Virtuoso](https://github.com/openlink/virtuoso-opensource) (SPARQL store).
On first run, the database is automatically initialized with categories,
licences, and a dev account with full admin privileges — no extra setup needed.

Once running:

- **Djehuty**: http://localhost:8080 (auto-login, no auth setup needed)
- **Virtuoso SPARQL**: http://localhost:8890/sparql (useful for troubleshooting)

Edit any Python file under `src/` and the server reloads automatically.

To start the development environment with a Virtuoso database backup
(e.g. to test against specific production data):

```bash
just db_backup=path/to/prod-2025-10-09_#1.bp dev
```

Point `db_backup` at any one of the backup files. All siblings sharing
the same prefix in that directory are applied in order, so a full backup
plus its incrementals (e.g. `prod-2025-10-09_#1.bp`, `…_#2.bp`,
`…_#3.bp`) are restored together.

To stop and remove the development environment, run `just clean`.
To see all available commands, run `just --list`.

## Running in production

Djehuty needs a SPARQL 1.1 endpoint such as
[Virtuoso OSE](https://github.com/openlink/virtuoso-opensource) or
[Jena Fuseki](https://jena.apache.org/documentation/fuseki2/) to
store its state.

Copy the [example configuration](./etc/djehuty/djehuty-example-config.xml)
and adjust it for your environment:

```bash
cp etc/djehuty/djehuty-example-config.xml djehuty.xml
```

### First run

Upon first run, `djehuty` needs to initialize the database with categories,
licences and accounts.  To do so, pass the `--initialize` option to the
`djehuty web` command:

```bash
djehuty web --initialize --config-file djehuty.xml
```

### Subsequent runs

After the database has been initialized, you can remove the `--initialize`
option:
```bash
djehuty web --config-file=djehuty.xml
```
## Running the tests

The project includes an end-to-end test suite built with
[Playwright](https://playwright.dev/python/) and
[pytest](https://docs.pytest.org/). Tests run against a live djehuty +
Virtuoso stack seeded with test data — all in containers, so no host
Python or browser setup is required.

```bash
just test
```

That single command builds the test image (with Playwright and
chromium), brings up Virtuoso and djehuty, loads the SPARQL
permissions, runs `--initialize`, applies the seed dataset, and runs
the suite inside the docker network. Coverage data lands in
`docker/coverage/`; failure screenshots in `docker/test-results/`.

Filter the run with any pytest argument:

```bash
just test -m smoke              # one marker
just test -k test_homepage      # by keyword
just test tests/test_auth.py    # specific file
```

### Marker isolation

CI runs each marker (`smoke`, `auth`, `dataset`, `admin`, `embargo`,
`citation`, `versioning`, …) in its own job with a fresh stack, so a
test never sees data left over from another marker. `just test` runs
everything against one shared stack, which is faster but means a few
state-sensitive tests can fail locally that pass in CI. When that
happens, run the affected marker on its own:

```bash
just clean   # drop volumes for a truly fresh stack
just test -m citation
```

### CI

Tests run automatically on every push via GitHub Actions. Each runner
in the matrix invokes `just test -m <marker>` against the same compose
stack used locally, so a green `just test` on your laptop reproduces
what CI sees. Screenshots are captured on failure and uploaded as
artifacts; coverage from each shard is combined into a single report.

---
### Contact information
- **Maintainers**: g.kuhn@tudelft.nl
- **Security issues**: djehuty@4tu.nl
