djehuty
=========

`djehuty` is a research data repository system developed by
[4TU.ResearchData](https://data.4tu.nl/). It is the software behind
[data.4tu.nl](https://data.4tu.nl/), where researchers deposit, publish and
cite datasets, software and other research output, and is also used by
[Nikhef](https://www.nikhef.nl/).

It handles the full life cycle of a deposit: authenticating researchers through
their institution, collecting metadata and files, sending submissions for
review, minting persistent identifiers with DataCite and the Handle system, and
serving the published record to readers and to machines over an API. State is
kept as RDF in a SPARQL 1.1 store rather than a relational database, so the
catalogue is a queryable knowledge graph.

`djehuty` is a Python package, distributed on
[PyPI](https://pypi.org/project/djehuty/) and as a container image, and it can
be deployed on Kubernetes with the
[Helm charts](https://github.com/4TUResearchData/helm-charts). Another
institution can run its own instance: the branding, menus, identity provider
and storage back-ends are all configuration.

## Documentation

The documentation source lives in [`docs/`](./docs/) and is published to GitHub
Pages at
[4turesearchdata.github.io/djehuty](https://4turesearchdata.github.io/djehuty/).

An older manual, generated from LaTeX sources in [`doc/`](./doc/), is still
served at [djehuty.4tu.nl](https://djehuty.4tu.nl/). It is being replaced by the
Markdown site above; new documentation should be written in `docs/`.

| Page | What it covers |
|------|----------------|
| [Introduction](./docs/introduction.md) | What djehuty is and what it does |
| [Configuring and running djehuty](./docs/running-djehuty.md) | Every configuration option |
| [Deployment](./docs/deployment.md) | Deploying with Helm, containers or the Python package |
| [Knowledge graph](./docs/knowledge-graph.md) | The RDF data model |
| [Contributing](./docs/contributing.md) | Development workflow and a tour of the source code |
| [API](./docs/api.md) | The HTTP API |

### Building the documentation

The site is built with [MkDocs](https://www.mkdocs.org/) using the
[Material](https://squidfunk.github.io/mkdocs-material/) theme. You need
[uv](https://docs.astral.sh/uv/getting-started/installation/) and
[just](https://github.com/casey/just#installation); the Python dependencies come
from the `docs` group in `pyproject.toml` and are installed automatically.

To preview while you write, with live reload on every save:

```bash
just docs-md-serve
```

That serves the site at http://localhost:8000 and rebuilds whenever a file under
`docs/` changes.

To build the static site into `site/`:

```bash
just docs-md
```

Remove the build output again with `just docs-clean`.

Editing the docs is a pull request like any other — the pages are Markdown, so a
typo fix can be made straight from the GitHub web interface. On merge to `main`,
the [docs workflow](./.github/workflows/docs.yml) rebuilds the site and
publishes it to GitHub Pages, so there is no manual publishing step.

## Installing and running

Djehuty needs a SPARQL 1.1 endpoint such as
[Virtuoso OSE](https://github.com/openlink/virtuoso-opensource) or
[Jena Fuseki](https://jena.apache.org/documentation/fuseki2/) to
store its state.

See the [deployment guide](./docs/deployment.md) for the three supported ways
to deploy it (Helm chart, container image, or Python package) along with what
a production configuration requires and how to upgrade.

## Contributing

Contributions are welcome — code, documentation, bug reports and ideas alike.
[CONTRIBUTING.md](./CONTRIBUTING.md) covers how to set up a development
environment, run the test suite, and the conventions we follow for branches,
commits and pull requests.

## Security

To report a vulnerability, please see [SECURITY.md](./SECURITY.md).

## License

`djehuty` is distributed under the GNU Affero General Public License v3.0 or
later. See [LICENSE](./LICENSE).

---
### Contact information
- **General**: info@djehuty.4tu.nl
- **Maintainers**: a.e.wilczynska@tudelft.nl, g.kuhn@tudelft.nl, k.f.deAraujo@tudelft.nl
- **Security issues**: security@djehuty.4tu.nl
