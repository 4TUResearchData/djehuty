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
[pytest](https://docs.pytest.org/). Tests run against a live instance
backed by a Virtuoso SPARQL store loaded with test data.

### Prerequisites

Install the test dependencies and the Playwright browser:

```bash
pip install --requirement requirements-dev.txt
playwright install --with-deps chromium
```

### Running locally

Set up the SPARQL store and application in this order:

1. Start Virtuoso with a clean installation (container or local instance)
2. Run `001-setup_permissions.sql` via isql
3. Start djehuty with the initialize flag:
   `djehuty web --initialize --config-file djehuty.xml`
4. Run `002-seed-test-data.sql` via isql
5. Ready to run the e2e tests

The seed scripts are in `docker/dev/sparql-init/`. Note that
`002-seed-test-data.sql` depends on the `dev@djehuty.com` account
that is created by `--initialize` in step 3.

Then run:

```bash
cd e2e
E2E_BASE_URL=http://localhost:8080 python -m pytest tests/ -v
```

Useful options:

```bash
# Run a specific marker (smoke, auth, dataset, admin, …)
python -m pytest tests/ -v -m smoke

# Run a single test by name
python -m pytest tests/ -v -k test_homepage
```

### CI

Tests run automatically on every push via GitHub Actions. The workflow
starts a Virtuoso service container, loads the test data, starts the
application, and runs the full suite. Screenshots are captured on failure
and uploaded as artifacts.

---
### Contact information
- **Maintainers**: g.kuhn@tudelft.nl
- **Security issues**: djehuty@4tu.nl
