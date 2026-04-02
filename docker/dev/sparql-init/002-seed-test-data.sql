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
    <container:a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d>
        rdf:type                          djht:DatasetContainer ;
        djht:account                      ?account ;
        djht:dataset_id                   "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"^^xsd:string ;
        djht:latest_published_version     <dataset:b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e> ;
        djht:published_versions           <blank:c3d4e5f6-a7b8-4c9d-8e0f-1a2b3c4d5e6f> ;
        djht:first_online_date            "2026-01-15T12:00:00"^^xsd:dateTime ;
        djht:total_downloads              0 ;
        djht:total_views                  0 ;
        djht:total_shares                 0 ;
        djht:total_cites                  0 .

    # -- Published versions list (single entry) -----------------------------
    <blank:c3d4e5f6-a7b8-4c9d-8e0f-1a2b3c4d5e6f>
        rdf:type                          rdf:List ;
        rdf:first                         <dataset:b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e> ;
        rdf:rest                          rdf:nil ;
        djht:index                        0 .

    # -- Dataset (the published version) ------------------------------------
    <dataset:b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e>
        rdf:type                          djht:Dataset ;
        djht:container                    <container:a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d> ;
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
        djht:tags                         <blank:d4e5f6a7-b8c9-4d0e-8f1a-2b3c4d5e6f7a> ;
        djht:authors                      <blank:e5f6a7b8-c9d0-4e1f-8a2b-3c4d5e6f7a8b> ;
        djht:categories                   <blank:f6a7b8c9-d0e1-4f2a-8b3c-4d5e6f7a8b9c> .

    # -- Tags list ----------------------------------------------------------
    <blank:d4e5f6a7-b8c9-4d0e-8f1a-2b3c4d5e6f7a>
        rdf:type                          rdf:List ;
        rdf:first                         "e2e-test"^^xsd:string ;
        rdf:rest                          rdf:nil ;
        djht:index                        0 .

    # -- Authors list -------------------------------------------------------
    <blank:e5f6a7b8-c9d0-4e1f-8a2b-3c4d5e6f7a8b>
        rdf:type                          rdf:List ;
        rdf:first                         <author:a7b8c9d0-e1f2-4a3b-8c4d-5e6f7a8b9c0d> ;
        rdf:rest                          rdf:nil ;
        djht:index                        0 .

    <author:a7b8c9d0-e1f2-4a3b-8c4d-5e6f7a8b9c0d>
        rdf:type                          djht:Author ;
        djht:first_name                   "Test"^^xsd:string ;
        djht:last_name                    "Author"^^xsd:string ;
        djht:full_name                    "Test Author"^^xsd:string ;
        djht:is_active                    "true"^^xsd:boolean ;
        djht:is_public                    "true"^^xsd:boolean .

    # -- Categories list (Mathematical Sciences = 13431) --------------------
    <blank:f6a7b8c9-d0e1-4f2a-8b3c-4d5e6f7a8b9c>
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
