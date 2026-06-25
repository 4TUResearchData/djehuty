"""One-shot generator that produces ``migrations/0001_initial.ttl``.

This script captures the exact set of static triples that the legacy
``djehuty.backup.database.DatabaseInterface.insert_static_triplets``
inserted on first start.  It is checked in so the derivation of
``0001_initial.ttl`` is reproducible, but it is not part of the runtime
package and is not invoked by the migration runner.

Run once::

    python -m djehuty.schema._generate_initial

This rewrites ``src/djehuty/schema/migrations/0001_initial.ttl`` in place.
The output uses random ``unique_node`` URIs that are pinned to the
committed file; isomorphism between the committed file and a freshly
generated graph is verified by ``tests/schema/test_initial_equivalence.py``.

This script can be deleted once ``insert_static_triplets`` is removed.
"""

import os
import sys

from djehuty.backup.database import DatabaseInterface


OUTPUT_PATH = os.path.join (os.path.dirname (os.path.abspath (__file__)),
                            "migrations", "0001_initial.ttl")


def main ():
    """Generate the initial migration and write it to disk."""

    interface = DatabaseInterface ()
    if not interface.insert_static_triplets ():
        print ("insert_static_triplets returned False; aborting.",
               file=sys.stderr)
        sys.exit (1)

    # Bind the djht: prefix for readability; everything else rdflib decides.
    interface.store.bind ("djht",
                          "https://ontologies.data.4tu.nl/djehuty/0.0.1/")

    payload = interface.store.serialize (format="turtle")
    if isinstance (payload, bytes):
        payload = payload.decode ("utf-8")

    with open (OUTPUT_PATH, "w", encoding="utf-8") as out:
        out.write (payload)

    print (f"Wrote {len(interface.store)} triples to {OUTPUT_PATH}")


if __name__ == "__main__":
    main ()
