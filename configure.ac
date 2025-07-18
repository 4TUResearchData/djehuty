AC_INIT(djehuty, 25.6)
AM_INIT_AUTOMAKE([foreign tar-ustar])
AM_PATH_PYTHON([3.9])
AC_CONFIG_FILES([
  guix.scm
  Makefile
  src/Makefile
  pyproject.toml
  rpmbuild/SPECS/djehuty.spec
])

dnl Check for presence of 'pdflatex', 'bibtex', and 'htlatex'.
dnl ---------------------------------------------------------------------------
AC_CHECK_PROG(PDFLATEX, pdflatex, pdflatex)
AC_CHECK_PROG(BIBTEX, bibtex, bibtex)
AC_CHECK_PROG(HTLATEX, htlatex, htlatex)

if test "x$BIBTEX" = "x"; then
  AC_MSG_WARN([Unable to create the user manual.])
else
  if test "x$PDFLATEX" = "x"; then
    AC_MSG_WARN([Unable to create PDF version of the user manual.])
  fi
  if test "x$HTLATEX" = "x"; then
    dnl Do a single-shot guess to find htlatex on a mingw64/msys2 install.
    AC_CHECK_FILE("/mingw64/bin/htlatex.bat", [AC_SUBST(HTLATEX, htlatex.bat)])
    if test "x$HTLATEX" = "x"; then
      AC_MSG_WARN([Unable to create HTML version of the user manual.])
    fi
  fi
fi

AM_CONDITIONAL([HAVE_PDFLATEX], [test -n "$PDFLATEX"])
AM_CONDITIONAL([HAVE_HTLATEX],  [test -n "$HTLATEX"])
AM_CONDITIONAL([HAVE_BIBTEX],   [test -n "$BIBTEX"])

AM_COND_IF([HAVE_PDFLATEX],
           [AC_CONFIG_FILES([
              doc/Makefile
              doc/djehuty.sty])])

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

dnl Package-specific configurable options
dnl ---------------------------------------------------------------------------

AC_ARG_VAR(BASE_URL, [The URL on which the instance will run.  This is only
                      used to align the documentation.])

dnl Default value for BASE_URL
: "${BASE_URL=https://data.4tu.nl}"

dnl Check for presence of 'git'.
dnl ---------------------------------------------------------------------------
AC_CHECK_PROG(GIT, git, git)
AC_PROG_SED
AC_OUTPUT
