"""Command-line interface for ``djehuty migrate``.

Reuses :func:`djehuty.web.ui.read_configuration_file` to populate the
global ``config`` singleton, then drives
:class:`djehuty.schema.migrate.MigrationRunner` based on the requested
subcommand (``status``, ``upgrade``, ``stamp``, ``verify``).
"""

import logging
import sys

from djehuty.schema.migrate import DriftDetected, MigrationRunner
from djehuty.web import wsgi
from djehuty.web.config import config
from djehuty.web.ui import read_configuration_file


def _load_runner (config_file, logger):
    """Parse the config file and return a ready-to-use MigrationRunner."""

    server       = wsgi.WebServer ()
    config_files = set ()
    read_configuration_file (server, config_file, logger, config_files)
    server.db.setup_sparql_endpoint ()
    if not server.db.sparql_is_up:
        logger.error ("SPARQL endpoint is not reachable.")
        sys.exit (1)
    return MigrationRunner.from_config (server.db, config)


def _status (runner):
    rows = runner.status ()
    if not rows:
        print ("No migrations found.")
        return 0
    width = max (len (row.identifier) for row in rows)
    print (f"{'Migration'.ljust (width)}  Applied at            Drift")
    print (f"{'-' * width}  --------------------  -----")
    for row in rows:
        applied = row.applied_at or "(pending)"
        drift   = "YES" if row.drift else ""
        print (f"{row.identifier.ljust (width)}  {applied:<20}  {drift}")
    head    = runner.head ()
    current = runner.current ()
    print ()
    print (f"Head:    {head}")
    print (f"Current: {current or '(none)'}")
    return 0


def _upgrade (runner, target):
    try:
        applied = runner.upgrade (to=target)
    except DriftDetected as error:
        print (f"Refusing to upgrade: {error}", file=sys.stderr)
        return 2
    if applied == 0:
        print ("Already at head; nothing to apply.")
    else:
        print (f"Applied {applied} migration(s).")
    return 0


def _stamp (runner, target):
    stamped = runner.stamp (to=target)
    if stamped == 0:
        print ("Nothing to stamp.")
    else:
        print (f"Stamped {stamped} migration(s).")
    return 0


def _verify (runner):
    if runner.verify ():
        print ("All applied migrations match their on-disk checksums.")
        return 0
    print ("Drift detected; see log output above.", file=sys.stderr)
    return 2


def main (subcommand, config_file=None, target=None):
    """Dispatch the ``djehuty migrate`` subcommand."""

    logger = logging.getLogger ("djehuty.migrate")

    if config_file is None:
        logger.error ("--config-file is required.")
        return 1

    runner = _load_runner (config_file, logger)

    if subcommand == "status":
        return _status (runner)
    if subcommand == "upgrade":
        return _upgrade (runner, target)
    if subcommand == "stamp":
        return _stamp (runner, target or "head")
    if subcommand == "verify":
        return _verify (runner)

    logger.error ("Unknown migrate subcommand: %s", subcommand)
    return 1
