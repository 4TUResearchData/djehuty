AC_INIT(djehuty, 26.6)
AM_INIT_AUTOMAKE([foreign tar-ustar])
AM_PATH_PYTHON([3.10])
AC_CONFIG_FILES([
  guix.scm
  Makefile
  src/Makefile
  pyproject.toml
  rpmbuild/SPECS/djehuty.spec
])

dnl Check for the presence of 'docker' or 'podman'.
dnl ---------------------------------------------------------------------------
AC_CHECK_PROG(DOCKER, docker, docker)
if test "x$DOCKER" = "x"; then
  AC_CHECK_PROG(DOCKER, podman, podman)
fi

AM_CONDITIONAL([HAVE_DOCKER], [test -n "$DOCKER"])

dnl Check for the Python 'build' module.
dnl ---------------------------------------------------------------------------
if test "x$PYTHON" != "x"; then
   $PYTHON -m build --version > /dev/null 2> /dev/null
   if test $? -ne 0; then
      AC_MSG_WARN([Unable to build tarballs due to missing Python 'build' module.])
   fi
fi

dnl Check for presence of 'git'.
dnl ---------------------------------------------------------------------------
AC_CHECK_PROG(GIT, git, git)
AC_PROG_SED

dnl Deprecation notice
dnl ---------------------------------------------------------------------------
AC_MSG_WARN([])
AC_MSG_WARN([============================================================])
AC_MSG_WARN([DEPRECATION NOTICE: The autotools build system for djehuty])
AC_MSG_WARN([will be discontinued on October 31, 2026.])
AC_MSG_WARN([Please switch to just/uv as described in the README.])
AC_MSG_WARN([============================================================])
AC_MSG_WARN([])

AC_OUTPUT
