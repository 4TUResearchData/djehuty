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

# Run linter
lint:
    uv run pylint src/djehuty/* > pylint.log || true
    @printf "Wrote 'pylint.log'.\n"

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
dist-docker: sdist
    uv export --frozen --no-dev --no-hashes -o docker/requirements.lock
    docker image build --no-cache \
        --build-arg="PURPOSE=release" \
        --build-arg="BRANCH=main" \
        --build-arg="VERSION={{ version }}" \
        -t docker.io/4turesearchdata/djehuty:{{ version }} \
        docker/
    rm -f docker/requirements.lock

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
    {{ dev_compose }} down -v 2>/dev/null || true

# Run Coverity scan
coverity-report:
    cov-build --dir cov-int --no-command --fs-capture-search .

# --- Development environment ---

dev_compose := "docker compose -f docker/docker-compose.dev.yml"

# Start development environment (auto-initializes on first run)
dev:
    {{ dev_compose }} up --build
