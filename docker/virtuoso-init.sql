-- Grant SPARQL_UPDATE role to the SPARQL user (allows INSERT/DELETE via /sparql endpoint)
DB.DBA.USER_GRANT_ROLE ('SPARQL', 'SPARQL_UPDATE', 0);

-- Allow any graph to be written via SPARQL
DB.DBA.RDF_DEFAULT_USER_PERMS_SET ('nobody', 7);
DB.DBA.RDF_DEFAULT_USER_PERMS_SET ('SPARQL', 7);
