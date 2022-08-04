# Copying and distribution of this file, with or without modification,
# are permitted in any medium without royalty provided the copyright
# notice and this notice are preserved.  This file is offered as-is,
# without any warranty.

AUTOMAKE_OPTIONS        = subdir-objects
SUBDIRS                 = .

docdir                  = ${pkgdatadir}
doc_NAME                = djehuty
doc_PDF                 = $(doc_NAME).pdf
doc_HTML                = $(doc_NAME).html
doc_TEX                 = $(doc_NAME).tex
doc_STYLE               = $(doc_NAME).sty
dist_doc_DATA           =

if HAVE_PDFLATEX
dist_doc_DATA           += $(doc_PDF)

# Run pdflatex thrice, so that the table of contents and references are
# properly set up.
$(doc_PDF):
	@$(PDFLATEX) $(doc_TEX) $(doc_STYLE) > /dev/null
	-@$(BIBTEX) $(doc_NAME) > /dev/null
	@$(PDFLATEX) $(doc_TEX) $(doc_STYLE) > /dev/null
	@$(PDFLATEX) $(doc_TEX) $(doc_STYLE) > /dev/null
	@printf "Generated $(doc_PDF).\n"
endif

EXTRA_DIST              = $(doc_TEX) $(doc_STYLE)                  \
                          introduction.tex                         \
                          knowledge-graph.tex                      \
                          references.bib                           \
                          figures/dataset.pdf                      \
                          figures/dataset-container.pdf            \
                          figures/logo.pdf                         \
                          figures/rdf-list-abbrev.pdf              \
                          figures/references-graph.pdf             \
                          figures/typed-literals-notation.pdf      \
                          figures/typed-notation.pdf


if HAVE_HTLATEX
$(doc_HTML): $(doc_PDF)
	@$(HTLATEX) $(doc_TEX) > /dev/null
	@printf "Generated $(doc_HTML).\n"

.PHONY: $(doc_NAME).css $(doc_NAME)2.html

nobase_dist_doc_DATA     = $(doc_HTML)                             \
                           $(doc_NAME)2.html                       \
                           $(doc_NAME)3.html                       \
                           $(doc_NAME)4.html                       \
                           $(doc_NAME).css
endif

docs-clean:
	$(RM) -rf $(doc_NAME).aux                                        \
      $(doc_NAME).bbl                                              \
      $(doc_NAME).blg                                              \
      $(doc_NAME).log                                              \
      $(doc_NAME).out                                              \
      $(doc_NAME).toc                                              \
      $(doc_NAME).xref                                             \
      $(doc_NAME).4ct                                              \
      $(doc_NAME).4tc                                              \
      $(doc_NAME).dvi                                              \
      $(doc_NAME).idv                                              \
      $(doc_NAME).tmp                                              \
      $(doc_NAME).lg                                               \
      $(doc_NAME).lof                                              \
      $(doc_NAME).lot                                              \
      $(doc_NAME).pdf                                              \
      $(doc_NAME).css                                              \
      $(doc_NAME).html                                             \
      $(doc_NAME)2.html                                            \
      $(doc_NAME)3.html                                            \
      $(doc_NAME)4.html                                            \
      missfont.log                                                 \
      texput.log                                                   \
      figures/dataset-.png                                         \
      figures/dataset-container-.png                               \
      figures/logo-.png                                            \
      figures/rdf-list-abbrev-.png                                 \
      figures/references-graph-.png                                \
      figures/typed-literals-notation-.png                         \
      figures/typed-notation-.png

clean-local: docs-clean
