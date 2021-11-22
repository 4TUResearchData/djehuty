"""This module contains the command-line interface for the 'api' subcommand."""

from werkzeug.serving import run_simple
from rdbackup.api import wsgi

def main (address, port, use_debugger=False, use_reloader=False):
    """The main entry point for the 'api' subcommand."""
    server = wsgi.ApiServer ()
    run_simple (address, port, server,
                use_debugger=use_debugger,
                use_reloader=use_reloader)
