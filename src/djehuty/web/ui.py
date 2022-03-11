"""This module contains the command-line interface for the 'web' subcommand."""

import logging
import os
import xml.etree.ElementTree as ET
from werkzeug.serving import run_simple
from djehuty.web import database
from djehuty.web import wsgi

class ConfigFileNotFound(Exception):
    """Raised when the database is not queryable."""

def config_value (xml_root, path, command_line=None, fallback=None):
    """Procedure to get the value a config item should have at run-time."""

    ## Prefer command-line arguments.
    if command_line:
        return command_line

    ## Read from the configuration file.
    if xml_root:
        item = xml_root.find(path)
        if item is not None:
            return item.text

    ## Fall back to the fallback value.
    return fallback

## ----------------------------------------------------------------------------
## Starting point for the command-line program
## ----------------------------------------------------------------------------

def main (address=None, port=None, state_graph=None, storage=None,
          base_url=None, config_file=None, use_debugger=False,
          use_reloader=False, run_internal_server=True):
    """The main entry point for the 'web' subcommand."""
    try:
        server = wsgi.ApiServer ()

        ## Set configuration from a file.
        xml_root = None
        if config_file is not None:
            tree = ET.parse(config_file)
            xml_root = tree.getroot()
            if xml_root.tag != "djehuty":
                raise ConfigFileNotFound

        address                 = config_value (xml_root, "bind-address", address, "127.0.0.1")
        port                    = int(config_value (xml_root, "port", port, 8080))
        server.base_url         = config_value (xml_root, "base-url", base_url,
                                                f"http://{address}:{port}")
        server.db.storage       = config_value (xml_root, "storage-root", storage)
        server.db.cache.storage = f"{server.db.storage}/cache"
        server.db.endpoint      = config_value (xml_root, "rdf-store/sparql-uri")
        server.db.state_graph   = config_value (xml_root, "rdf-store/state-graph", state_graph)
        use_reloader            = config_value (xml_root, "live-reload", use_reloader)
        use_debugger            = config_value (xml_root, "debug-mode", use_debugger)
        maximum_workers         = int(config_value (xml_root, "maximum-workers", None, 1))

        if use_reloader:
            use_reloader = bool(int(use_reloader))
        if use_debugger:
            use_debugger = bool(int(use_debugger))

        if xml_root:
            orcid = xml_root.find("authentication/orcid")
            if orcid:
                server.orcid_client_id     = config_value (orcid, "client-id")
                server.orcid_client_secret = config_value (orcid, "client-secret")
                server.orcid_endpoint      = config_value (orcid, "endpoint")

            privileges = xml_root.find("privileges")
            if privileges:
                for account in privileges:
                    try:
                        account_id = int(account.attrib["id"])
                        server.db.privileges[account_id] = {
                            "may_impersonate": bool(int(config_value (account, "may-impersonate", None, False))),
                            "may_review":      bool(int(config_value (account, "may-review", None, False)))
                        }
                    except KeyError as error:
                        logging.error ("Missing %s attribute for a privilege configuration.", error)
                    except ValueError as error:
                        logging.error ("Privilege configuration error: %s", error)

        if not server.db.cache.cache_is_ready():
            logging.error("Failed to set up cache layer.")

        server.db.load_state()

        if not run_internal_server:
            return server

        if os.environ.get('WERKZEUG_RUN_MAIN'):
            logging.info("Reloaded.")
        else:
            logging.info("Running on %s", server.base_url)
            logging.info("State graph set to:  %s.", server.db.state_graph)
            logging.info("Storage path set to: %s.", server.db.storage)

        run_simple (address, port, server,
                    threaded=(maximum_workers <= 1),
                    processes=maximum_workers,
                    use_debugger=use_debugger,
                    use_reloader=use_reloader)

    except database.UnknownDatabaseState:
        logging.error ("Please make sure the database is up and running.")
    except ConfigFileNotFound:
        logging.error ("%s does not look like a Djehuty configuration file.",
                       config_file)
    except ET.ParseError:
        logging.error ("%s does not contain valid XML.", config_file)
    except FileNotFoundError:
        logging.error ("Could not open '%s'.", config_file)

    return None

## ----------------------------------------------------------------------------
## Starting point for uWSGI
## ----------------------------------------------------------------------------

def application (env, start_response):
    """The main entry point for the WSGI."""

    logging.basicConfig(format='[ %(levelname)s ] %(asctime)s: %(message)s',
                        level=logging.INFO)

    config_file = os.getenv ("DJEHUTY_CONFIG_FILE")

    if config_file is None:
        start_response('200 OK', [('Content-Type','text/html')])
        return [b"<p>Please set the <code>DJEHUTY_CONFIG_FILE</code> environment variable.</p>"]

    server = main (config_file=config_file, run_internal_server=False)
    return server (env, start_response)
