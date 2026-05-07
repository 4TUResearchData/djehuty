-- Permissions required for djehuty to use Virtuoso as its SPARQL store.
-- Loaded by Virtuoso on first boot via the initdb.d mount.

-- Allow nobody and the SPARQL user to read/write any RDF graph.
DB.DBA.RDF_DEFAULT_USER_PERMS_SET ('nobody', 7);
DB.DBA.RDF_DEFAULT_USER_PERMS_SET ('SPARQL', 7);

-- Allow INSERT/DELETE via the /sparql endpoint.
GRANT SPARQL_UPDATE TO "SPARQL";

-- Procedures used by djehuty when writing RDF dictionaries.
GRANT EXECUTE ON "DB.DBA.SPARQL_INSERT_DICT_CONTENT" TO "SPARQL";
GRANT EXECUTE ON "DB.DBA.L_O_LOOK" TO "SPARQL";
