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
  guix.scm                                  \
  requirements.txt                          \
  setup.cfg                                 \
  setup.py

dist-rpm: source-dist
	mkdir -p rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
	rm -f rpmbuild/SOURCES/*
	ln -s $(abs_top_srcdir)/dist/djehuty-@VERSION@.tar.gz rpmbuild/SOURCES/djehuty-@VERSION@.tar.gz
	rpmbuild --define "_topdir $(abs_top_srcdir)/rpmbuild" -ba $(abs_top_srcdir)/rpmbuild/SPECS/djehuty.spec

source-dist:
	@PYTHON@ setup.py sdist --formats=gztar

binary-dist:
	@PYTHON@ setup.py bdist --formats=gztar

all-local:
	@PYTHON@ setup.py build --build-base $(shell readlink -f $(builddir))/build

install-exec-local:
	@PYTHON@ setup.py install                 \
        --prefix $(DESTDIR)$(prefix)        \
        --single-version-externally-managed \
        --record $(DESTDIR)$(pkgpythondir)/install_files.txt

uninstall-local:
	cat $(DESTDIR)$(pkgpythondir)/install_files.txt | xargs rm -rf
	rm -rf $(DESTDIR)$(pkgpythondir)
