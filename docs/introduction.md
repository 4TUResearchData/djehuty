# Introduction

`djehuty` is a research data repository system developed by
[4TU.ResearchData](https://data.4tu.nl/). It is the software behind
[data.4tu.nl](https://data.4tu.nl/), where researchers deposit, publish and
cite datasets, software and other research output, and is also used by
[Nikhef](https://www.nikhef.nl/). The name finds its inspiration in
[Thoth](https://en.wikipedia.org/wiki/Thoth), the Egyptian entity that
introduced the idea of writing.

`djehuty` handles the full life cycle of a deposit: authenticating researchers
through their institution, collecting metadata and files, sending submissions
for review, minting persistent identifiers with DataCite and the Handle system,
and serving the published record to readers and to machines over an API. State
is kept as RDF in a SPARQL 1.1 store rather than a relational database, so the
catalogue is a queryable knowledge graph.

`djehuty` is a Python package, distributed on [PyPI](https://pypi.org/project/djehuty/)
and as a container image, and it can be deployed on Kubernetes with the
[Helm charts](https://github.com/4TUResearchData/helm-charts). Another institution
can run its own instance: the branding, menus, identity provider and storage
back-ends are all configuration.

