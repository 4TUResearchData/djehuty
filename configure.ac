AC_INIT(djehuty, 24.3-dev)
AM_INIT_AUTOMAKE([foreign tar-ustar])
AM_PATH_PYTHON([3.7])
AC_CONFIG_FILES([
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

dnl Check for presence of 'git'.
dnl ---------------------------------------------------------------------------
AC_CHECK_PROG(GIT, git, git)

AC_OUTPUT
