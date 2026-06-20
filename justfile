# Extract version from pyproject.toml
version := `grep -m1 '^version' pyproject.toml | sed 's/.*= *"\(.*\)"/\1/'`

base_url := env("BASE_URL", "https://data.4tu.nl")

# Default recipe: build the Python package
build:
    uv build --out-dir build

# Install the package
install prefix="":
    uv pip install {{ if prefix != "" { "--prefix " + prefix } else { "" } }} \
        --no-cache .

# Uninstall the package
uninstall:
    uv pip uninstall djehuty

# Build source distribution
sdist:
    uv build --sdist

# Build wheel
wheel:
    uv build --wheel

# Build RPM package
dist-rpm: sdist
    mkdir -p rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
    rm -f rpmbuild/SOURCES/*
    ln -s "$(pwd)/dist/djehuty-{{ version }}.tar.gz" rpmbuild/SOURCES/djehuty-{{ version }}.tar.gz
    sed -e 's/@VERSION@/{{ version }}/g' rpmbuild/SPECS/djehuty.spec.in > rpmbuild/SPECS/djehuty.spec
    rpmbuild --define "_topdir $(pwd)/rpmbuild" -ba rpmbuild/SPECS/djehuty.spec

# Build Docker image
dist-docker:
    docker image build --no-cache \
        --build-arg="VERSION={{ version }}" \
        -t docker.io/4turesearchdata/djehuty:{{ version }} \
        -f docker/Dockerfile \
        .

# Push Docker image to registry
publish-docker: dist-docker
    docker push docker.io/4turesearchdata/djehuty:{{ version }}

# Publish to PyPI
publish-pypi: build
    uv publish --publish-url https://upload.pypi.org/legacy/ \
        dist/djehuty-{{ version }}.tar.gz \
        dist/djehuty-{{ version }}-py3-none-any.whl

# Publish to Test PyPI
publish-test-pypi: build
    uv publish --publish-url https://test.pypi.org/legacy/ \
        dist/djehuty-{{ version }}.tar.gz \
        dist/djehuty-{{ version }}-py3-none-any.whl

# Generate Guix package definition
guix:
    sed -e 's/@VERSION@/{{ version }}/g' guix.scm.in > guix.scm

# Append the top CHANGELOG.md release section to doc/news.tex
news:
    python3 doc/changelog_to_news.py

# Build PDF documentation
docs-pdf:
    cd doc && \
    sed -e 's/@VERSION@/{{ version }}/g' -e 's|@BASE_URL@|{{ base_url }}|g' djehuty.sty.in > djehuty.sty && \
    pdflatex -interaction=nonstopmode djehuty.tex && \
    bibtex djehuty || true && \
    pdflatex -interaction=nonstopmode djehuty.tex && \
    pdflatex -interaction=nonstopmode djehuty.tex && \
    printf "Generated djehuty.pdf.\n"

# Build HTML documentation
docs-html: docs-pdf
    cd doc && \
    cp -r ../src/djehuty/web/resources/static/fonts . && \
    htlatex djehuty.tex "" "" "" " -interaction=nonstopmode" && \
    sed -e 's#class="endfloat" />#class="endfloat">#g' \
        -e 's#class="newline" />#class="newline">#g' \
        -e 's#<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"  #<!DOCTYPE html>#g' \
        -e 's#  "http://www.w3.org/TR/html4/loose.dtd"> ##g' \
        -e 's#<br />#<br>#g' djehuty.html > index.html && \
    printf "Generated index.html.\n"

# Clean documentation build artifacts
docs-clean:
    cd doc && rm -rf \
        djehuty.aux djehuty.bbl djehuty.blg djehuty.log djehuty.out \
        djehuty.toc djehuty.xref djehuty.4ct djehuty.4tc djehuty.dvi \
        djehuty.idv djehuty.tmp djehuty.lg djehuty.lof djehuty.lot \
        djehuty.pdf djehuty.css djehuty.html djehuty.sty \
        djehuty2.html djehuty3.html djehuty4.html \
        djehuty5.html djehuty6.html djehuty7.html \
        index.html missfont.log texput.log \
        figures/*-.png

# Clean all build artifacts and dev environment
clean: docs-clean
    rm -rf build/ dist/ src/djehuty.egg-info/ pylint.log
    # Restore-time overlay written by `just db_backup=... dev`; pairs with
    # the dev volume teardown below so the next `just dev` boots clean.
    rm -f etc/djehuty/*.local.json
    {{ e2e_compose }} down -v --remove-orphans 2>/dev/null || true

# Run Coverity scan
coverity-report:
    cov-build --dir cov-int --no-command --fs-capture-search .

# --- Development environment ---

dev_compose := "docker compose -f docker/docker-compose.dev.yml"
e2e_compose := dev_compose + " -f docker/docker-compose.e2e.yml"

db_backup := ""
state_graph := "https://data.4tu.nl"

# Start dev environment. Restore a DB backup: just db_backup=<file> dev
dev:
    #!/usr/bin/env bash
    set -euo pipefail

    if [ -n "{{ db_backup }}" ]; then
        BACKUP_FILE="$(cd "$(dirname "{{ db_backup }}")" && pwd)/$(basename "{{ db_backup }}")"
        if [ ! -f "${BACKUP_FILE}" ]; then
            echo "Error: Backup file '${BACKUP_FILE}' not found"
            exit 1
        fi

        # Extract restore name: "prod-2025-10-09_#1.bp" -> "prod-2025-10-09_#"
        BACKUP_DIR="$(dirname "${BACKUP_FILE}")"
        BACKUP_BASENAME="$(basename "${BACKUP_FILE}")"
        RESTORE_NAME="$(echo "${BACKUP_BASENAME}" | sed 's/[0-9]*\.bp$//')"
        echo "Backup dir:   ${BACKUP_DIR}"
        echo "Restore name: ${RESTORE_NAME}"
        echo "Backup files found:"
        ls -1 "${BACKUP_DIR}/${RESTORE_NAME}"*.bp 2>/dev/null | sed 's|^|    |' \
            || { echo "    (none matching ${RESTORE_NAME}*.bp)"; exit 1; }
        echo "State graph:  {{ state_graph }}"

        echo "==> Ensuring virtuoso.ini exists (initializing if needed)..."
        {{ dev_compose }} up -d virtuoso
        {{ dev_compose }} stop virtuoso

        echo "==> Removing old database files (keeping virtuoso.ini)..."
        {{ dev_compose }} run --rm --no-deps --entrypoint sh virtuoso -c \
            'rm -f /database/virtuoso.db /database/virtuoso.lck /database/virtuoso.log \
                   /database/virtuoso.pxa /database/virtuoso.trx /database/virtuoso-temp.db'

        echo "==> Restoring backup (full + incrementals)..."
        {{ dev_compose }} run --rm --no-deps \
            -v "${BACKUP_DIR}:/backups:ro" \
            --entrypoint /opt/virtuoso-opensource/bin/virtuoso-t \
            virtuoso \
            +configfile /database/virtuoso.ini \
            +restore-backup "${RESTORE_NAME}" \
            +backup-dirs /backups \
            +foreground

        # Write the restore-time override into a gitignored *.local.json copy
        # so the tracked dev config stays clean. The container reads it via
        # DJEHUTY_CONFIG (forwarded into the djehuty service's command). python3
        # edits the JSON state-graph so we avoid GNU/BSD sed differences.
        echo "==> Writing restore-time config override..."
        DEV_CONFIG="etc/djehuty/djehuty-dev-config.json"
        LOCAL_CONFIG="etc/djehuty/djehuty-dev-config.local.json"
        cp "${DEV_CONFIG}" "${LOCAL_CONFIG}"
        python3 -c "import json,sys; p=sys.argv[1]; d=json.load(open(p)); d['djehuty']['rdf-store']['state-graph']=sys.argv[2]; json.dump(d, open(p,'w'), indent=2)" \
            "${LOCAL_CONFIG}" "{{ state_graph }}"
        echo "    ${LOCAL_CONFIG} (state-graph: {{ state_graph }})"
        export DJEHUTY_CONFIG="/config/djehuty/djehuty-dev-config.local.json"
    fi

    echo "==> Starting development environment..."
    {{ dev_compose }} up --build

# Run unit tests locally (fast, no container). Emits .coverage.* for the coverage pipeline.
test-unit *args="":
    uv run --group dev coverage run -m pytest tests/unit -v {{ args }}

# Run e2e tests in containers (pass extra pytest args, e.g. -m smoke)
test *args="":
    {{ e2e_compose }} run --rm --build tests \
        pytest -W always -rw tests/ -v --tb=short \
        --reruns=1 --reruns-delay=5 \
        --screenshot=only-on-failure \
        --output=/app/test-results {{ args }}
