AUTOMAKE_OPTIONS        = subdir-objects
SUBDIRS                 = src

# Help make tarballs more reproducible.
export TAR_OPTIONS      = --owner=0 --group=0 --numeric-owner

# Only attempt to build the documentation when PDFLATEX is available.
if HAVE_PDFLATEX
SUBDIRS                += doc
endif

EXTRA_DIST              =                   \
  LICENSE                                   \
  MANIFEST.in                               \
  README.md                                 \
  etc/djehuty.service                       \
  etc/djehuty/djehuty-example-config.xml    \
  requirements.txt                          \
  pyproject.toml                            \
  tests/admin_panel.py                      \
  tests/create_article.py                   \
  tests/create_collection.py                \
  tests/depositor_panel.py                  \
  tests/run_backup.py                       \
  tests/ui_pages.py                         \
  tests/validators.py

dist-rpm: dist
	mkdir -p rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
	rm -f rpmbuild/SOURCES/*
	ln -s $(abs_top_srcdir)/djehuty-@VERSION@.tar.gz rpmbuild/SOURCES/djehuty-@VERSION@.tar.gz
	rpmbuild --define "_topdir $(abs_top_srcdir)/rpmbuild" -ba $(abs_top_srcdir)/rpmbuild/SPECS/djehuty.spec

if HAVE_DOCKER
dist-docker: dist
	@DOCKER@ image build --no-cache                         \
           --build-arg="PURPOSE=release"                  \
           --build-arg="BRANCH=main"                      \
           --build-arg="VERSION=@VERSION@"                \
           -t docker.io/4turesearchdata/djehuty:@VERSION@ \
           docker/

publish-docker: dist-docker
	@DOCKER@ push docker.io/4turesearchdata/djehuty:@VERSION@
endif

dist-pypi:
	@PYTHON@ -m build

source-dist:
	@PYTHON@ -m build --skip-dependency-check --no-isolation --sdist \
           -C=--global-option=sdist                                \
           -C=--global-option=--owner=root                         \
           -C=--global-option=--group=root                         \
           -C=--global-option=--formats=gztar

binary-dist:
	@PYTHON@ -m build --skip-dependency-check --no-isolation --wheel \
           -C=--global-option=bdist                                \
           -C=--global-option=--owner=root                         \
           -C=--global-option=--group=root                         \
           -C=--global-option=--formats=gztar

all-local:
	@PYTHON@ -m build --outdir $(shell readlink -f $(builddir))/build

install-exec-local:
	@PYTHON@ -m pip install --prefix $(DESTDIR)$(prefix) \
        --disable-pip-version-check                    \
        --no-cache-dir .

uninstall-local:
	rm -rf $(DESTDIR)$(pkgpythondir)

lint:
	@pylint src/djehuty/* > pylint.log || true
	@printf "Wrote 'pylint.log'.\n"

coverity-report:
	@cov-build --dir cov-int --no-command --fs-capture-search .

publish-pypi: dist-pypi
	@PYTHON@ -m twine upload --repository pypi dist/djehuty-@VERSION@.tar.gz dist/djehuty-@VERSION@-py3-none-any.whl

publish-test-pypi: dist-pypi
	@PYTHON@ -m twine upload --repository testpypi dist/djehuty-@VERSION@.tar.gz dist/djehuty-@VERSION@-py3-none-any.whl
