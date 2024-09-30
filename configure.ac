AC_INIT(djehuty, 24.9-dev)
AM_INIT_AUTOMAKE([foreign tar-ustar])
AM_PATH_PYTHON([3.8])
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
    AC_MSG_WARN([Unable to create HTML version of the user manual.])
  fi
fi

AM_CONDITIONAL([HAVE_PDFLATEX], [test -n "$PDFLATEX"])
AM_CONDITIONAL([HAVE_HTLATEX],  [test -n "$HTLATEX"])
AM_CONDITIONAL([HAVE_BIBTEX],   [test -n "$BIBTEX"])

AM_COND_IF([HAVE_PDFLATEX],
           [AC_CONFIG_FILES([
              doc/Makefile
              doc/djehuty.sty])])

dnl Package-specific configurable options
dnl ---------------------------------------------------------------------------

AC_ARG_VAR(BASE_URL, [The URL on which the instance will run.  This is only
                      used to align the documentation.])

dnl Default value for BASE_URL
: "${BASE_URL=https://data.4tu.nl}"

dnl Check for presence of 'git'.
dnl ---------------------------------------------------------------------------
AC_CHECK_PROG(GIT, git, git)

AC_OUTPUT
