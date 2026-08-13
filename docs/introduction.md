# Introduction

`djehuty` is the data repository system developed by 4TU.ResearchData and Nikhef.
The name finds its inspiration in
[Thoth](https://en.wikipedia.org/wiki/Thoth), the Egyptian entity that
introduced the idea of writing.

## Obtaining the source code

The source code can be downloaded at the
[Releases](https://github.com/4TUResearchData/djehuty/releases)
page. Make sure to download the `djehuty-<version>.tar.gz` file.

Or, directly download the tarball using the command-line:

```bash
curl -LO https://github.com/4TUResearchData/djehuty/releases/download/v<version>/djehuty-<version>.tar.gz
```

After obtaining the tarball, it can be unpacked using the `tar` command:

```bash
tar zxvf djehuty-<version>.tar.gz
```

## Installing the prerequisites

`djehuty` needs Python (version 3.10 or higher) and Git to be installed.
Additionally, a couple of Python packages need to be installed. The following
sections describe installing the prerequisites on various GNU/Linux
distributions. The figure below displays the complete run-time dependencies
from `djehuty` to `glibc`.

![Run-time dependencies when constructed with the packages from GNU Guix](figures/references-graph.svg)

`djehuty` stores its information in a
[SPARQL 1.1](https://www.w3.org/TR/sparql11-query/) endpoint. We recommend
either [Blazegraph](https://blazegraph.com/) or
[Virtuoso open-source edition](http://vos.openlinksw.com/owiki/wiki/VOS).

If you prefer not to install dependencies manually, `djehuty` is also available
as [container images](#pre-built-containers), which bundle all required dependencies and are suitable for both development and production deployments.

### Optional installation requirements depending on configuration

For specific features `djehuty` may require additional packages to be
installed. Whether this is the case depends on the run-time configuration.
When an optional package is required `djehuty` will report which one in its
logs. There are two such features: SAML authentication needs `python3-saml`,
and the IIIF Image API needs `pyvips`.

Both also need system libraries to be present. See [Optional dependencies](deployment.md#optional-dependencies) in the deployment guide for which ones, and how to install them.

## Installation instructions

This section covers obtaining and installing the software. For running it in
production - on Kubernetes, in containers, or as a service on a host - see the [deployment guide](deployment.md).

### Development

The recommended way to run `djehuty` for development is with
[just](https://github.com/casey/just#installation) and Docker:

```bash
just dev
```

This spins up `djehuty` and a Virtuoso SPARQL store in containers, initializes
the database, and starts a live-reloading server at http://localhost:8080. See
[README.md](https://github.com/4TUResearchData/djehuty/blob/main/README.md) for the full development workflow.

### From PyPI

```bash
pip install djehuty
```

Or to install from a local checkout:

```bash
pip install .
```

### From source

After obtaining the source code (see [Obtaining the source code](#obtaining-the-source-code))
and installing the required tools (see [Installing the prerequisites](#installing-the-prerequisites)),
building involves running the following commands:

```bash
cd djehuty-<version>
autoreconf -vif # Only needed if the "./configure" step does not work.
./configure
make
make install
```

To run the `make install` command, super user privileges may be required.
Specify a `--prefix` to the `configure` script to install the tools to a
user-writeable location to avoid needing super user privileges.

After installation, the `djehuty` program will be available.

## Pre-built containers

4TU.ResearchData publishes a container image for each `djehuty` release to the
GitHub Container Registry as `ghcr.io/4turesearchdata/djehuty`. See
[Containers](deployment.md#containers) in the deployment guide for the
available tags and how to run the image.

## RPM packages

> **Deprecated:** RPM packages are no longer provided. We recommend installing
> `djehuty` via [PyPI](https://pypi.org/project/djehuty/) or using the
> [container images](#pre-built-containers) instead.

4TU.ResearchData previously provided RPM packages built for Enterprise Linux 9.
RPM packages for more distributions were
[built via Copr](https://copr.fedorainfracloud.org/coprs/4turesearchdata/djehuty).
