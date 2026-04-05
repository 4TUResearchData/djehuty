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

### Code quality

New and modified code must follow PEP 8. To lint and auto-format only the
files you changed (compared to `main`), run:

```bash
just lint
```

This uses [ruff](https://docs.astral.sh/ruff/) to fix style issues and
format your changes. Review the result with `git diff` before committing.

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
---
### Contact information
- **Maintainers**: g.kuhn@tudelft.nl
- **Security issues**: djehuty@4tu.nl
