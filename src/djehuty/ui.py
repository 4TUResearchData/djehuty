"""
This module contains the entry point for the program.
"""

import argparse
import signal
import sys
import logging
import os
import importlib.metadata

import djehuty.backup.ui as backup_ui
import djehuty.web.ui as web_ui

def show_version ():
    """Show the program's version."""

    version = importlib.metadata.version (__package__ or __name__)
    print(f"This is djehuty v{version}")
    sys.exit(0)

def show_help ():
    """Show a GNU-style help message."""

    print("""This is djehuty.\n
Available subcommands and options:

  backup:
    --help               -h Show a help message.
    --stats-auth=ARG     -a Username/password for the statistics endpoint.
    --token=ARG          -t The API token to use.
    --account-id=ARG     -i The account ID to backup.
    --api-url            -u The base URL for accessing the API. Defaults to
                            'https://api.figshare.com'.

  web:
    --help               -h Show a help message.
    --config-file=ARG    -c Load configuration from a file.
    --initialize         -i Populate the RDF store with default triples.
    --extract-transactions-from-log=ARG
                         -e Extract transactions from the log file.
                            The optional argument is a datetime to
                            start from, in the format of YYYY-MM-DD HH:MM:SS.
    --apply-transactions=ARG
                         -A Apply transactions extracted by the -e option above.
                            The optional argument is the path to the folder that
                            contains the SPARQL transaction files.  By default
                            it will look in the current working directory.
    --full-rdf-export    -f Exports all metadata as RDF triples in N3 format.
                            This feature is in BETA state. Do not rely on it
                            for a full back-up.
    --public-rdf-export  -p Exports all publically available metadata as RDF
                            triples in N3 format.  This feature is in BETA
                            state. Do not reply on it for an accurate
                            representation of publically available metadata.

  Global options:
  --help                 -h  Show this message.
  --version              -v  Show versioning information.\n""")
    sys.exit(0)

def sigint_handler (sig, frame):  # pylint: disable=unused-argument
    """Signal handler for SIGINT and SIGTERM."""
    logger = logging.getLogger(__name__)
    logger.info ("Received shutdown signal.  Goodbye!")
    sys.exit(0)

def main_inner ():
    """The main entry point of the program."""

    signal.signal(signal.SIGINT, sigint_handler)
    signal.signal(signal.SIGTERM, sigint_handler)

    logging.basicConfig(format='[%(levelname)s] %(asctime)s - %(name)s: %(message)s',
                        level=logging.INFO)

    ## COMMAND-LINE ARGUMENTS
    ## ------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        usage    = '\n  %(prog)s [backup|web] ...',
        prog     = 'djehuty',
        add_help = False)

    subparsers = parser.add_subparsers(dest='command', help='sub-command help')

    ### BACKUP SUBCOMMAND
    ### -----------------------------------------------------------------------
    backup_parser = subparsers.add_parser('backup', help="Options for the 'backup' subcommand.")
    backup_parser.add_argument('--token',       '-t', type=str, default='')
    backup_parser.add_argument('--stats-auth',  '-a', type=str, default='')
    backup_parser.add_argument('--account-id',  '-i', type=str, default=None)
    backup_parser.add_argument('--api-url',     '-u', type=str, default=None)

    ### WEB SUBCOMMAND
    ### -----------------------------------------------------------------------
    web_parser = subparsers.add_parser('web', help="Options for the 'web' subcommand.")
    web_parser.add_argument('--config-file','-c', type=str, default=None)
    web_parser.add_argument('--initialize', '-i', action='store_true')
    web_parser.add_argument('--extract-transactions-from-log', '-e', nargs='?',
                            const='', default=None)
    web_parser.add_argument('--apply-transactions', '-A', nargs='?',
                            const='', default=None)
    web_parser.add_argument('--full-rdf-export', '-f', action='store_true')
    web_parser.add_argument('--public-rdf-export', '-p', action='store_true')

    ### GLOBAL ARGUMENTS
    ### -----------------------------------------------------------------------
    parser.add_argument('--help',    '-h', action='store_true')
    parser.add_argument('--version', '-v', action='store_true')

    # When using PyInstaller and Nuitka, argv[0] seems to get duplicated.
    # In the case of Nuitka, relative paths are converted to absolute paths.
    # This bit de-duplicates argv[0] in these cases.
    try:
        if os.path.abspath(sys.argv[0]) == os.path.abspath(sys.argv[1]):
            sys.argv = sys.argv[1:]
    except IndexError:
        pass

    args = parser.parse_args()
    if args.help:
        show_help()
    if args.version:
        show_version()

    if args.command == "backup":
        if "" in (args.token, args.stats_auth):
            print ("The 'backup' command requires multiple arguments.")
            print ("Try --help for usage options.")
        else:
            backup_ui.main (args.token, args.stats_auth, args.account_id,
                            args.api_url)

    elif args.command == "web":
        web_ui.main (args.config_file, True, args.initialize,
                     args.extract_transactions_from_log,
                     args.apply_transactions, args.full_rdf_export,
                     args.public_rdf_export)

    elif len(sys.argv) == 1:
        print("Try --help for usage options.")

def main ():
    """Wrapper to catch KeyboardInterrupts for main_inner."""
    try:
        main_inner()
    except KeyboardInterrupt:
        sigint_handler (None, None)

    sys.exit(0)
