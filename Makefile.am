dist-rpm: source-dist
	mkdir -p rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
	rm -f rpmbuild/SOURCES/*
	ln -s $(abs_top_srcdir)/dist/djehuty-@VERSION@.tar.gz rpmbuild/SOURCES/djehuty-@VERSION@.tar.gz
	rpmbuild --define "_topdir $(abs_top_srcdir)/rpmbuild" -ba $(abs_top_srcdir)/rpmbuild/SPECS/djehuty.spec


source-dist:
	@PYTHON@ setup.py sdist --formats=gztar
