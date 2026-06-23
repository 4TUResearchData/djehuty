"""One-shot generator for ``migrations/0001_initial.ttl``.

Serialises ``insert_static_triplets`` to the seed migration. Dev tool only;
not part of the runtime package. Run once::

    python -m djehuty.schema._generate_initial

Categories, languages and licenses get deterministic ``rdf.stable_node`` URIs
keyed on their id/shortcode/URL, so the output is reproducible and re-applying
the seed never duplicates. Delete once ``insert_static_triplets`` is gone.
"""

import os
import sys

from djehuty.backup.database import DatabaseInterface

OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "migrations", "0001_initial.ttl"
)


def main():
    """Generate the initial migration and write it to disk."""

    interface = DatabaseInterface()
    if not interface.insert_static_triplets():
        print("insert_static_triplets returned False; aborting.", file=sys.stderr)
        sys.exit(1)

    # Bind the djht: prefix for readability; everything else rdflib decides.
    interface.store.bind("djht", "https://ontologies.data.4tu.nl/djehuty/0.0.1/")

    payload = interface.store.serialize(format="turtle")
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as out:
        out.write(payload)

    print(f"Wrote {len(interface.store)} triples to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
