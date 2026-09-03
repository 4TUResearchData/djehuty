# Deploying `djehuty`

There are three supported ways to deploy `djehuty`. They all run the same program with the same configuration file but they differ in it's method.

| Method | Best for |
|--------|----------|
| [Helm chart](#kubernetes-helm-chart) | Kubernetes clusters |
| [Container image](#containers) | A single host running a container runtime |
| [Python package](#python-package-pip-uv-pipx) | A virtual machine or bare-metal host managed by `systemd` |

For local development, none of the above: run `just dev`, which brings up `djehuty` and Virtuoso in containers with live reload. See the [README](https://github.com/4TUResearchData/djehuty/blob/main/README.md) file.

## Before you start

Whichever method you pick, the same four things have to be in place.

**A configuration file.** Copy
[`etc/djehuty/djehuty-example-config.json`](https://github.com/4TUResearchData/djehuty/blob/main/etc/djehuty/djehuty-example-config.json) and adjust it. Every option is described in [Configuring `djehuty`](running-djehuty.md). JSON is the recommended format; XML still works but is deprecated and will be removed in December 2026.

**A SPARQL 1.1 store.** `djehuty` keeps all of its state in an RDF store and needs both the query and the *update* endpoint. We run [Virtuoso open-source edition](https://github.com/openlink/virtuoso-opensource); [Jena Fuseki](https://jena.apache.org/documentation/fuseki2/) works as well. The store must grant SPARQL Update rights to the user `djehuty` connects as.

**Persistent storage.** The `storage-root` directory holds uploaded files, the query cache and profile images. It must survive restarts, and only one `djehuty` process may write to it so keep the deployment at a single replica unless you have arranged shared storage yourself.

**A TLS terminator in front.** `djehuty` speaks plain HTTP only, by design. Put a reverse proxy or ingress in front of it and set `use-x-forwarded-for` so client IP addresses are logged correctly.

The first start also has to seed the database with the reference data `djehuty` builds on: subject categories, languages, the licences a depositor can pick from, and the review states a dataset moves through. That is what `djehuty web --initialize` does. The flag is safe to leave on permanently; the seeding is skipped once the database is initialized and leaving it on is what keeps schema updates being applied on later releases.

## What `production` mode requires

Setting `production` to `1` turns on extra startup checks. `djehuty` logs an error and refuses to start unless all three of these hold:

- **An identity provider is configured**: SAML or ORCID, under `authentication`. Without one there is no way to log in.
- **An e-mail server is configured**: at minimum `email/server` and `email/from`. Notifications, review requests and second-factor codes all depend on it.
- **At least one account has the `may-process-feedback` privilege.** Feedback from the form has to reach someone.

Outside production mode the same conditions are only warnings, which is why an instance that runs fine with `production` set to `0` can fail to start the
moment you flip it to `1`.

## Kubernetes (Helm chart)

The charts live in [4TUResearchData/helm-charts](https://github.com/4TUResearchData/helm-charts)
and are published at <https://4turesearchdata.github.io/helm-charts/>. The `djehuty` chart deploys `djehuty` itself and, by default, bundles the `virtuoso` chart as a subchart, so a single `helm install` gives you a complete stack. For Helm itself (how releases, values files and repositories work) see the [Helm documentation](https://helm.sh/docs/).

!!! warning "Pre-release"
    The charts have not had a stable release yet. Values, templates and defaults may change between versions. Pin a chart version (`--version`) and read the diff before upgrading.

### Install

```bash
helm repo add 4turesearchdata https://4turesearchdata.github.io/helm-charts
helm repo update

helm install djehuty 4turesearchdata/djehuty \
  --namespace djehuty --create-namespace \
  --values values.yaml
```

Without a values file you get a working throwaway instance: bundled Virtuoso, a 5 GiB `ReadWriteOnce` volume for `/data`, no ingress, and the database seeded on first boot. Reach it with a port-forward:

```bash
kubectl -n djehuty port-forward svc/djehuty-djehuty 8080:8080
```

### A values file to start from

Everything the chart accepts, with its defaults and inline comments, comes from the chart itself. Once the repository is added (see [Install](#install)), run this from anywhere. `4turesearchdata/djehuty` names the chart in the repository, not a directory:

```bash
helm show values 4turesearchdata/djehuty > values.yaml
```

This command prints chart-level info such as `image`, `ingress`, `persistence`, `secrets` and is documented in place by the comments in the chart.

The `config:` key is where `djehuty`'s own configuration goes. The chart wraps whatever you put there in the top-level `djehuty` object and writes the result to `/etc/djehuty/config.json`. So an option that appears in [`djehuty-example-config.json`](https://github.com/4TUResearchData/djehuty/blob/main/etc/djehuty/djehuty-example-config.json) as

```json
{ "djehuty": { "site-name": "Example Repository" } }
```

is written in the values file as (the same keys and nesting, one level in, in YAML rather than JSON)

```yaml
config:
  site-name: "Example Repository"
```

Every option in [Configuring `djehuty`](running-djehuty.md) can be set this way, except two that the chart fills in itself:

- `rdf-store` is always built from the `rdfStore.*` values, so setting it under `config:` has no effect.
- `base-url` is derived from the ingress host when you leave it empty.

Quota tables, privileged accounts and menu definitions tend to be regenerated on their own schedule, and you do not want a chart release for each change. The chart's `config.includes` mounts existing ConfigMaps or Secrets and merges them into the running configuration at startup; the [chart README](https://github.com/4TUResearchData/helm-charts/blob/main/charts/djehuty/README.md) documents the JSON shape of each fragment.

### Secrets

Keep sensitive values out of the ConfigMap. In `config:` you can write `${env:NAME}` or `${file:/path}`; `djehuty` resolves the reference itself when it reads the configuration at startup. Short strings go in `secrets.env`, which the chart exposes as environment variables. Multi-line material such as PEM keys and certificates goes in `secrets.files`, mounted at `/etc/djehuty/secrets/`.

To use a Secret you manage yourself, set `secrets.existingSecret` to its name. The entries under `secrets.env` and `secrets.files` then only declare which keys and filenames to wire into the pod; their values are ignored.

### Using an external SPARQL store

To point at a store you already run, disable the bundled subchart:

```bash
helm install djehuty 4turesearchdata/djehuty \
  --set virtuoso.enabled=false \
  --set rdfStore.sparqlUri=http://sparql.example.internal:8890/sparql \
  --set rdfStore.sparqlUpdateUri=http://sparql.example.internal:8890/sparql \
  --set rdfStore.stateGraph=https://data.example.org
```

When `virtuoso.enabled` is true, the two URIs are derived from the subchart's Service and you should leave them empty.

### Upgrading and uninstalling

Back up the RDF store first, and read [CHANGELOG.md](https://github.com/4TUResearchData/djehuty/blob/main/CHANGELOG.md) for anything in the release that needs manual action. Then:

```bash
helm repo update
helm upgrade djehuty 4turesearchdata/djehuty --values values.yaml
```

Bump `image.tag` in the values file to move to a new `djehuty` release; the chart version and the `djehuty` version move independently.

To uninstall run
```bash
helm uninstall djehuty --namespace djehuty
```
Make sure to back up anything you care about before uninstalling.

## Containers

Images are published to the GitHub Container Registry:

```
ghcr.io/4turesearchdata/djehuty
```

### Image tags

| Tag | What it points at |
|-----|-------------------|
| `latest` | The most recent release. |
| `XX.X`, `XX.X.Y` | A specific release, e.g. `26.4` or `26.4.1`. Use this in production so you upgrade when you choose to. |
| `dev` | Built from the tip of `main` on every push. Unreleased code. |
| `sha-<commit>` | The exact commit on `main` that produced the image. |

!!! note "Docker Hub is no longer updated"
    Older releases were mirrored to [Docker Hub](https://hub.docker.com/r/4turesearchdata/djehuty), which stopped receiving updates after `25.6`. Pull from GHCR.

The image runs as the non-root user `djehuty` (UID 7001), exposes port 8080, and its default command is:

```
djehuty web --initialize --config-file /etc/djehuty/config.json
```

So a deployment amounts to mounting a configuration file at that path and a writable volume at the `storage-root` you configured. The image bundles `python3-saml`, so SAML authentication works out of the box. `pyvips` is not bundled, therefore enabling the IIIF Image API requires building your own image on top of this one, installing the `libvips` system library and the `pyvips` package.

### Running it

Mount a configuration file at `/etc/djehuty/config.json` and a writable volume at the `storage-root` it declares:

```bash
docker run -d --name djehuty \
  -p 8080:8080 \
  -v /opt/djehuty/config.json:/etc/djehuty/config.json:ro \
  -v /opt/djehuty/data:/data \
  ghcr.io/4turesearchdata/djehuty:26.4.1
```

The SPARQL store has to be reachable from the container. How you arrange that is a matter of how you run containers, not of `djehuty`.

Start from
[`djehuty-example-config.json`](https://github.com/4TUResearchData/djehuty/blob/main/etc/djehuty/djehuty-example-config.json), but three of its defaults do not survive the move into a container:

- **`bind-address`** must be `0.0.0.0`. The example uses `127.0.0.1`, which means the container only listens to itself and nothing outside can reach it.
- **`storage-root`** must be an absolute path on your mounted volume, such as `/data`. The example's relative `./data` resolves inside the image's `/app`, which the `djehuty` user cannot write to. The same goes for `cache-root`.
- **`base-url`** is the address users see - your public URL, not the container's own address or port.

`${env:NAME}` and `${file:/path}` work here too, so secrets can come from environment variables or mounted files rather than the configuration file itself.

### With Compose

[`docker/docker-compose.yaml`](https://github.com/4TUResearchData/djehuty/blob/main/docker/docker-compose.yaml) in the repository brings up `djehuty` and Virtuoso together. Copy it as a
starting point and change two things:

- Replace the locally-built `djehuty:latest` with a pinned tag from GHCR.
- Point the volume paths at your own configuration file and data directory.

A fresh Virtuoso needs SPARQL Update permissions before `djehuty` can write to it. Load them once - the Helm chart does this for you, but a store you bring yourself needs them:

```sql
DB.DBA.RDF_DEFAULT_USER_PERMS_SET ('nobody', 7);
DB.DBA.RDF_DEFAULT_USER_PERMS_SET ('SPARQL', 7);
GRANT SPARQL_UPDATE TO "SPARQL";
GRANT EXECUTE ON "DB.DBA.SPARQL_INSERT_DICT_CONTENT" TO "SPARQL";
GRANT EXECUTE ON "DB.DBA.L_O_LOOK" TO "SPARQL";
```

### Upgrading

Back up the RDF store, read [CHANGELOG.md](https://github.com/4TUResearchData/djehuty/blob/main/CHANGELOG.md),then move to the new tag and recreate the container. Because the image's command keeps `--initialize`, any schema updates the release carries are applied when the container starts.

## Python package (pip, uv, pipx)

`djehuty` is on PyPI as [`djehuty`](https://pypi.org/project/djehuty/) and requires Python 3.10 or newer.

```bash
pip install djehuty          # into a virtual environment
uv tool install djehuty      # or as an isolated tool
pipx install djehuty
```

That gives you the `djehuty` command. Verify with `djehuty --version`.

### Optional dependencies

Two features need packages that are not installed by default, because they pull in system libraries most deployments do not need. `djehuty` logs which one is missing when a configured feature cannot start.

| Feature | Package | System libraries |
|---------|---------|------------------|
| SAML 2.0 authentication | `python3-saml` | `libxmlsec1`, `pkg-config` |
| IIIF Image API | `pyvips` | `libvips` |

Install the system libraries with your distribution's package manager first, then `pip install python3-saml` or `pip install pyvips` into the same environment.

### Running it

Put the configuration file you prepared somewhere the account running `djehuty` can read it. `/etc/djehuty/djehuty.json` below is only a convention; you can use whatever path you like.

```bash
djehuty web --initialize --config-file /etc/djehuty/djehuty.json
```

Keep `--initialize` on for subsequent runs too. The seeding step is skipped once the database is initialized, and the flag is what makes `djehuty` apply schema updates from a new release at startup.

To run it as a service, adapt
[`etc/djehuty.service`](https://github.com/4TUResearchData/djehuty/blob/main/etc/djehuty.service):

Three things in the shipped unit need changing before it will suit a current install:

- It points at `/usr/bin/djehuty`. Use wherever your install put the binary - `which djehuty` will tell you, and it differs between a system-wide `pip install`, `uv tool install` and a virtual environment.
- It passes `--config-file=/etc/djehuty/djehuty.xml`, the deprecated XML format. Point it at your JSON configuration instead.

Run the unit as a dedicated unprivileged user that owns `storage-root`.

Put `nginx` in front for TLS. There is a working server block in [Running `djehuty` behind an `nginx` reverse-proxy](running-djehuty.md#running-djehuty-behind-an-nginx-reverse-proxy).

### Upgrading

Back up the RDF store, read [CHANGELOG.md](https://github.com/4TUResearchData/djehuty/blob/main/CHANGELOG.md), then upgrade the package and restart:

```bash
pip install --upgrade djehuty
systemctl restart djehuty
```

## Next steps

- [Configuring `djehuty`](running-djehuty.md) — every configuration option, including identity providers, DOI registration, storage locations and branding.
- [Contributing](contributing.md) — the development environment and a tour of the source code.
