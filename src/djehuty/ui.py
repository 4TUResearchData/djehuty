"""
This module contains the entry point for the program.
"""

import argparse
import sys
import logging

import djehuty.backup.ui as backup_ui
import djehuty.api.ui as api_ui

def show_version ():
    """Show the program's version."""

    print("This is djehuty v0.0.1")
    sys.exit(0)

def show_help ():
    """Show a GNU-style help message."""

    print("""This is djehuty.\n
Available subcommands and options:

  backup:
    --help               -h Show a help message.
    --token=ARG          -t The API token to use.
    --db-host=ARG        -H The database host to connect to.
    --db-name=ARG        -d The database name to use.
    --db-username=ARG    -u The database username to use.
    --db-password=ARG    -p The database password to use.

  api:
    --help               -h Show a help message.
    --port=ARG           -p The port to start the API server on.
    --address=ARG        -a The address to bind the server on.
    --state-graph        -s The state graph in the RDF store.
    --storage            -S The storage path backing the API.
    --debug              -d Enable debugging.
    --dev-reload         -r Enable active reloading.

  Global options:
  --help                 -h  Show this message.
  --version              -v  Show versioning information.\n""")
    sys.exit(0)

def main ():
    """The main entry point of the program."""

    logging.basicConfig(format='[ %(levelname)s ] %(asctime)s: %(message)s',
                        level=logging.DEBUG)

    ## COMMAND-LINE ARGUMENTS
    ## ------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        usage    = '\n  %(prog)s [backup|api] ...',
        prog     = 'djehuty',
        add_help = False)

    subparsers = parser.add_subparsers(dest='command', help='sub-command help')

    ### BACKUP SUBCOMMAND
    ### -----------------------------------------------------------------------
    backup_parser = subparsers.add_parser('backup', help="Options for the 'backup' subcommand.")
    backup_parser.add_argument('--token',       '-t', type=str, default='')
    backup_parser.add_argument('--stats-auth',  '-s', type=str, default='')
    backup_parser.add_argument('--db-host',     '-H', type=str, default='')
    backup_parser.add_argument('--db-name',     '-d', type=str, default='')
    backup_parser.add_argument('--db-username', '-u', type=str, default='')
    backup_parser.add_argument('--db-password', '-p', type=str, default='')

    ### API SUBCOMMAND
    ### -----------------------------------------------------------------------
    api_parser = subparsers.add_parser('api', help="Options for the 'api' subcommand.")
    api_parser.add_argument('--address',    '-a', type=str, default='127.0.0.1')
    api_parser.add_argument('--port',       '-p', type=int, default=8080)
    api_parser.add_argument('--state-graph','-s', type=str, default='https://data.4tu.nl/portal')
    api_parser.add_argument('--storage',    '-S', type=str, default=None)
    api_parser.add_argument('--debug',      '-d', action='store_true')
    api_parser.add_argument('--dev-reload', '-r', action='store_true')

    ### GLOBAL ARGUMENTS
    ### -----------------------------------------------------------------------
    parser.add_argument('--help',    '-h', action='store_true')
    parser.add_argument('--version', '-v', action='store_true')

    args = parser.parse_args()
    if args.help:
        show_help()
    if args.version:
        show_version()

    if args.command == "backup":
        if (args.token == ""       or args.stats_auth == "" or
            args.db_host == ""     or args.db_name == ""    or
            args.db_username == "" or args.db_password == ""):
            print ("The 'backup' command requires multiple arguments.")
            print ("Try --help for usage options.")
        else:
            backup_ui.main (args.token, args.stats_auth, args.db_host,
                            args.db_username, args.db_password, args.db_name)

    if args.command == "api":
        api_ui.main (args.address, args.port, args.state_graph, args.storage,
                     args.debug, args.dev_reload)

    elif len(sys.argv) == 1:
        print("Try --help for usage options.")
