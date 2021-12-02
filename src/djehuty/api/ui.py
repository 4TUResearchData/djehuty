"""This module contains the command-line interface for the 'api' subcommand."""

import logging
from werkzeug.serving import run_simple
from djehuty.api import database
from djehuty.api import wsgi

def main (address, port, state_graph, use_debugger=False, use_reloader=False):
    """The main entry point for the 'api' subcommand."""
    try:
        server = wsgi.ApiServer ()

        server.db.state_graph = state_graph
        server.db.load_state()

        logging.info("State graph set to: %s.", server.db.state_graph)
        run_simple (address, port, server,
                    use_debugger=use_debugger,
                    use_reloader=use_reloader)
    except database.UnknownDatabaseState:
        logging.error ("Please make sure the database is up and running.")
