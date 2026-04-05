djehuty
=========

This Python package provides the repository system for 4TU.ResearchData and Nikhef.

## Security

To report a vulnerability, please see [SECURITY.md](./SECURITY.md).

## Development environment

### Prerequisites

- [Git](https://git-scm.com/downloads)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [just](https://github.com/casey/just#installation)

### Getting started

```bash
git clone https://github.com/4TUResearchData/djehuty.git && cd djehuty/
uv sync
```

To see all available build commands, run `just --list`.

## Setting up the database

Djehuty needs a SPARQL 1.1 endpoint such as
[Virtuoso OSE](https://github.com/openlink/virtuoso-opensource) or
[Jena Fuseki](https://jena.apache.org/documentation/fuseki2/) to
store its state.

## Run the web service

To start the web service, we recommend copying the
[example configuration](./etc/djehuty/djehuty-example-config.xml)
and go from there:

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
