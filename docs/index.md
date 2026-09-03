# `djehuty`


`djehuty` is a research data repository system developed by
[4TU.ResearchData](https://data.4tu.nl/). It is utilized by
4TU.ResearchData, at [data.4tu.nl](https://data.4tu.nl/), and
[Nikhef](https://www.nikhef.nl/). Researchers use it to deposit, publish and
cite datasets, software and other research output.
The name `djehuty` finds its inspiration in [Thoth](https://en.wikipedia.org/wiki/Thoth), 
the Egyptian entity that introduced the idea of writing.

The system handles the full life cycle of a deposit: authenticating researchers
through their institution, collecting metadata and files, sending submissions
for review, minting persistent identifiers with DataCite and the Handle system,
and serving the published record to readers and to machines over an API. State
is kept as RDF in a SPARQL 1.1 store rather than a relational database, so the
catalogue is a queryable knowledge graph.

Distributed as a Python package on [PyPI](https://pypi.org/project/djehuty/)
and as a container image, it can also be deployed on Kubernetes with the
[Helm charts](https://github.com/4TUResearchData/helm-charts). Another institution
can run its own instance: the branding, menus, identity provider and storage
back-ends are all configuration.


## Documentation

1. [Configuring and running `djehuty`](running-djehuty.md) — Configuration reference and reverse-proxy setup
2. [Deployment](deployment.md) — Deploying with Helm, containers, or the Python package
3. [Knowledge graph](knowledge-graph.md) — RDF data model
4. [Contributing](contributing.md) — Development workflow and navigating the source code
5. [API](api.md) — Application Programming Interface
6. [Contact](contact.md) — Contacting the maintainers
7. [News](news.md) — Release notes
