FROM python:3.14-slim-bookworm@sha256:a70519002c49552ea0a853de47599cf40479b001bd7a624f1112eaf44dcaccc7

LABEL authors="Nikhef, 4TU.ResearchData"
LABEL org.opencontainers.image.version="${VERSION}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       git \
       libxmlsec1-dev \
       pkg-config \
       curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.21@sha256:ff07b86af50d4d9391d9daf4ff89ce427bc544f9aae87057e69a1cc0aa369946 /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1

# Install dependencies first (cached layer).
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Build and install djehuty from the source (non-editable, so the release image
# ships it in site-packages rather than as an editable link to /app/src).
# Dependencies still come from the locked uv.lock resolved above.
COPY src/ ./src/
COPY README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# Optional SAML login support. python3-saml is not a locked dependency (it is
# only needed when SAML auth is configured), so it is installed separately,
# after the project sync that would otherwise prune it.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /app/.venv python3-saml

ENV PATH="/app/.venv/bin:$PATH"

# Run as a non-root user with an OpenShift-friendly /data, matching the
# read-only / cap-drop posture in docker/docker-compose.yaml. The /bin/djehuty
# shim keeps the existing compose/helm `command:` working unchanged.
RUN useradd -mg users -d /opt/djehuty -u 7001 djehuty \
    && mkdir -p /data && chown -R djehuty:0 /data && chmod -R g=u /data \
    && printf '#!/bin/sh\nexec /app/.venv/bin/djehuty "$@"\n' > /bin/djehuty \
    && chmod +x /bin/djehuty

USER djehuty

EXPOSE 8080

CMD ["djehuty", "web", "--initialize", "--config-file", "/etc/djehuty/config.json"]
