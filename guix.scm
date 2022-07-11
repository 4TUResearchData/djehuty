;; Copyright (c) 2022 TU Delft <r.r.e.janssen@tudelft.nl>

;; This program is free software: you can redistribute it and/or modify
;; it under the terms of the GNU Affero General Public License as published by
;; the Free Software Foundation, either version 3 of the License, or
;; (at your option) any later version.

;; This program is distributed in the hope that it will be useful,
;; but WITHOUT ANY WARRANTY; without even the implied warranty of
;; MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
;; GNU Affero General Public License for more details.

;; You should have received a copy of the GNU Affero General Public
;; License along with this program.  If not, see
;; <http://www.gnu.org/licenses/>.

(use-modules (guix packages)
             ((guix licenses) #:prefix license:)
             (gnu packages python)
             (gnu packages python-xyz)
             (gnu packages python-web)
             (gnu packages rdf)
             (gnu packages version-control)
             (gnu packages)
             (guix build-system python)
             (guix download)
             (guix packages))

(define djehuty
  (package
   (name "djehuty")
   (version "0.0.1")
   (source (origin
            (method url-fetch)
            (uri (string-append
                  "file:///" (getcwd) "/" name "-" version ".tar.gz"))
            (sha256
             (base32
              "0aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"))))
   (build-system python-build-system)
   (arguments
    `(#:tests? #f))
   (propagated-inputs
    `(("git" ,git)
      ("python-jinja2" ,python-jinja2)
      ("python-rdflib" ,python-rdflib)
      ("python-pygit2" ,python-pygit2)
      ("python-requests" ,python-requests)
      ("python-sparqlwrapper" ,python-sparqlwrapper)
      ("python-urllib3" ,python-urllib3)
      ("python-werkzeug" ,python-werkzeug)))
   (home-page "https://github.com/4TUResearchData/djehuty")
   (synopsis "Data repository for 4TU.ResearchData")
   (description "This packge contains the implementation of the data
repository of 4TU.ResearchData.")
   (license license:agpl3+)))

;; Evaluate to the above recipe, so that the development
;; environment has everything to start from scratch.
djehuty
