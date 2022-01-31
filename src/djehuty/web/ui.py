"""This module contains the command-line interface for the 'web' subcommand."""

import logging
from werkzeug.serving import run_simple
from djehuty.web import database
from djehuty.web import wsgi

def main (address, port, state_graph, storage, base_url, use_debugger=False, use_reloader=False):
    """The main entry point for the 'web' subcommand."""
    try:
        server = wsgi.ApiServer (address, port)

        if base_url is not None:
            server.base_url = base_url

        server.db.storage       = storage
        server.db.cache.storage = f"{storage}/cache"
        server.db.state_graph   = state_graph
        if not server.db.cache.cache_is_ready():
            logging.error("Failed to set up cache layer.")

        server.db.load_state()

        logging.info("State graph set to:  %s.", server.db.state_graph)
        logging.info("Storage path set to: %s.", server.db.storage)
        run_simple (address, port, server,
                    use_debugger=use_debugger,
                    use_reloader=use_reloader)
    except database.UnknownDatabaseState:
        logging.error ("Please make sure the database is up and running.")
