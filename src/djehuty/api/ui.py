"""This module contains the command-line interface for the 'api' subcommand."""

import logging
from werkzeug.serving import run_simple
from djehuty.api import database
from djehuty.api import wsgi

def main (address, port, state_graph, storage, base_url, use_debugger=False, use_reloader=False):
    """The main entry point for the 'api' subcommand."""
    try:
        server = wsgi.ApiServer (address, port)

        if base_url is not None:
            server.base_url = base_url

        server.db.storage     = storage
        server.db.state_graph = state_graph
        server.db.load_state()

        logging.info("State graph set to:  %s.", server.db.state_graph)
        logging.info("Storage path set to: %s.", server.db.storage)
        run_simple (address, port, server,
                    use_debugger=use_debugger,
                    use_reloader=use_reloader)
    except database.UnknownDatabaseState:
        logging.error ("Please make sure the database is up and running.")
