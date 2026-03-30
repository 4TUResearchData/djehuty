-- Seed a published dataset for E2E search tests.
--
-- This script inserts a minimal published dataset directly into the
-- SPARQL store so search, filter, sort, and view-mode tests have data
-- to work with.  It looks up the dev account by email so the UUIDs
-- match whatever --initialize created.
--
-- Run after the application has been started with --initialize (which
-- creates the dev@djehuty.com account and the category/license data).

SPARQL
PREFIX djht: <https://ontologies.data.4tu.nl/djehuty/0.0.1/>
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>

INSERT {
  GRAPH <djehuty://local> {
    # -- Container ----------------------------------------------------------
    <container:e2e-search-container-0001>
        rdf:type                          djht:DatasetContainer ;
        djht:account                      ?account ;
        djht:dataset_id                   900001 ;
        djht:latest_published_version     <dataset:e2e-search-dataset-0001> ;
        djht:published_versions           <blank:e2e-search-publist-0001> ;
        djht:first_online_date            "2026-01-15T12:00:00"^^xsd:dateTime ;
        djht:total_downloads              0 ;
        djht:total_views                  0 ;
        djht:total_shares                 0 ;
        djht:total_cites                  0 .

    # -- Published versions list (single entry) -----------------------------
    <blank:e2e-search-publist-0001>
        rdf:type                          rdf:List ;
        rdf:first                         <dataset:e2e-search-dataset-0001> ;
        rdf:rest                          rdf:nil ;
        djht:index                        0 .

    # -- Dataset (the published version) ------------------------------------
    <dataset:e2e-search-dataset-0001>
        rdf:type                          djht:Dataset ;
        djht:container                    <container:e2e-search-container-0001> ;
        djht:title                        "Search Test Seed Dataset"^^xsd:string ;
        djht:description                  "<p>Dataset seeded for search E2E tests.</p>"^^xsd:string ;
        djht:defined_type                 3 ;
        djht:defined_type_name            "Dataset"^^xsd:string ;
        djht:language                     "en"^^xsd:string ;
        djht:publisher                    "4TU.ResearchData"^^xsd:string ;
        djht:is_public                    "true"^^xsd:boolean ;
        djht:is_active                    1 ;
        djht:is_latest                    "true"^^xsd:boolean ;
        djht:is_editable                  "false"^^xsd:boolean ;
        djht:is_under_review              "false"^^xsd:boolean ;
        djht:version                      1 ;
        djht:group_id                     28586 ;
        djht:created_date                 "2026-01-15T12:00:00"^^xsd:dateTime ;
        djht:modified_date                "2026-01-15T12:00:00"^^xsd:dateTime ;
        djht:published_date               "2026-01-15T12:00:00"^^xsd:dateTime ;
        djht:posted_date                  "2026-01-15T12:00:00"^^xsd:dateTime ;
        djht:submission_date              "2026-01-15T12:00:00"^^xsd:dateTime ;
        djht:tags                         <blank:e2e-search-tags-0001> ;
        djht:authors                      <blank:e2e-search-authors-0001> ;
        djht:categories                   <blank:e2e-search-cats-0001> .

    # -- Tags list ----------------------------------------------------------
    <blank:e2e-search-tags-0001>
        rdf:type                          rdf:List ;
        rdf:first                         "e2e-test"^^xsd:string ;
        rdf:rest                          rdf:nil ;
        djht:index                        0 .

    # -- Authors list -------------------------------------------------------
    <blank:e2e-search-authors-0001>
        rdf:type                          rdf:List ;
        rdf:first                         <author:e2e-search-author-0001> ;
        rdf:rest                          rdf:nil ;
        djht:index                        0 .

    <author:e2e-search-author-0001>
        rdf:type                          djht:Author ;
        djht:first_name                   "Test"^^xsd:string ;
        djht:last_name                    "Author"^^xsd:string ;
        djht:full_name                    "Test Author"^^xsd:string ;
        djht:is_active                    "true"^^xsd:boolean ;
        djht:is_public                    "true"^^xsd:boolean .

    # -- Categories list (Mathematical Sciences = 13431) --------------------
    <blank:e2e-search-cats-0001>
        rdf:type                          rdf:List ;
        rdf:first                         ?category ;
        rdf:rest                          rdf:nil ;
        djht:index                        0 .
  }
}
WHERE {
  GRAPH <djehuty://local> {
    ?account  rdf:type       djht:Account ;
              djht:email     "dev@djehuty.com"^^xsd:string .
    ?category rdf:type       djht:Category ;
              djht:id        13431 .
  }
};
