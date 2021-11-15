import argparse
import sys
from rdbackup.backup import figshare
from rdbackup.backup import database

def show_version ():
    print(f"This is rdbackup v0.0.1")
    sys.exit(0)

def show_help ():
    """Show a GNU-style help message."""

    print("""This is rdbackup.\n
Available subcommands and options:

  backup:
    --help               -h Show a help message.
    --token=ARG          -t  The API token to use.

  api:
    --help               -h Show a help message.
    --port=ARG           -p The port to start the API server on.
    --address=ARG        -a The address to bind the server on.

  Global options:
  --help                 -h  Show this message.
  --version              -v  Show versioning information.\n""")
    sys.exit(0)

def main ():

    ## COMMAND-LINE ARGUMENTS
    ## ------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        usage    = '\n  %(prog)s [backup|api] ...',
        prog     = 'rdbackup',
        add_help = False)

    subparsers = parser.add_subparsers(dest='command', help='sub-command help')

    ### BACKUP SUBCOMMAND
    ### -----------------------------------------------------------------------
    backup_parser = subparsers.add_parser('backup', help="Options for the 'backup' subcommand.")

    backup_parser.add_argument('--token',   '-t', type=str, default='')

    ### API SUBCOMMAND
    ### -----------------------------------------------------------------------
    api_parser = subparsers.add_parser('api', help="Options for the 'api' subcommand.")
    api_parser.add_argument('--address',    '-a', type=str, default='127.0.0.1')
    api_parser.add_argument('--port',       '-p', type=int, default=8080)


    ### GLOBAL ARGUMENTS
    ### -----------------------------------------------------------------------
    parser.add_argument('--help',    '-h', action='store_true')
    parser.add_argument('--version', '-v', action='store_true')

    args    = parser.parse_args()
    if args.help:    show_help()
    if args.version: show_version()

    if args.command == "backup" and args.token == "":
        print ("The 'backup' command requires specifying a --token.")
        print("Try --help for usage options.")
    elif len(sys.argv) == 1:
        print("Try --help for usage options.")
