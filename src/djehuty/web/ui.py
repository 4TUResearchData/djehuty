"""This module contains the command-line interface for the 'web' subcommand."""

import logging
import os
import xml.etree.ElementTree as ET
import shutil
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


def read_configuration_file (server, config_file, address, port, state_graph,
                             storage, base_url, use_debugger, use_reloader):
    """Procedure to parse a configuration file."""

    inside_reload = os.environ.get('WERKZEUG_RUN_MAIN')
    try:
        config   = {}
        xml_root = None
        tree = ET.parse(config_file)

        if config_file is not None and not inside_reload:
            logging.info ("Reading config file: %s", config_file)

        xml_root = tree.getroot()
        if xml_root.tag != "djehuty":
            raise ConfigFileNotFound

        config_dir = os.path.dirname(config_file)
        log_file = config_value (xml_root, "log-file", None, None)
        if log_file is not None:
            is_writeable = False
            log_file     = os.path.abspath (log_file)
            try:
                file_test = open (log_file, "a", encoding = "utf-8")
                file_test.close()
                is_writeable = True
            except PermissionError:
                pass
            except FileNotFoundError:
                pass

            if not is_writeable:
                if not inside_reload:
                    logging.warning ("Cannot write to '%s'.", log_file)
            else:
                file_handler = logging.FileHandler (log_file, 'a')
                if not inside_reload:
                    logging.info ("Writing further messages to '%s'.", log_file)

                formatter    = logging.Formatter('[ %(levelname)s ] %(asctime)s: %(message)s')
                file_handler.setFormatter(formatter)
                file_handler.setLevel(logging.INFO)
                logger       = logging.getLogger()
                for handler in logger.handlers[:]:
                    logger.removeHandler(handler)
                logger.addHandler(file_handler)

        config["address"]       = config_value (xml_root, "bind-address", address, "127.0.0.1")
        config["port"]          = int(config_value (xml_root, "port", port, 8080))
        server.base_url         = config_value (xml_root, "base-url", base_url,
                                                f"http://{config['address']}:{config['port']}")
        server.in_production    = bool(int(config_value (xml_root, "production", None,
                                                         server.in_production)))
        server.db.storage       = config_value (xml_root, "storage-root", storage)
        server.db.cache.storage = f"{server.db.storage}/cache"
        server.db.endpoint      = config_value (xml_root, "rdf-store/sparql-uri")
        server.db.state_graph   = config_value (xml_root, "rdf-store/state-graph", state_graph)
        config["use_reloader"]  = config_value (xml_root, "live-reload", use_reloader)
        config["use_debugger"]  = config_value (xml_root, "debug-mode", use_debugger)
        config["maximum_workers"] = int(config_value (xml_root, "maximum-workers", None, 1))

        if config["use_reloader"]:
            config["use_reloader"] = bool(int(config["use_reloader"]))
        if config["use_debugger"]:
            config["use_debugger"] = bool(int(config["use_debugger"]))

        if not xml_root:
            return config

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
                        "may_administer":  bool(int(config_value (account, "may-administer", None, False))),
                        "may_impersonate": bool(int(config_value (account, "may-impersonate", None, False))),
                        "may_review":      bool(int(config_value (account, "may-review", None, False)))
                    }
                except KeyError as error:
                    logging.error ("Missing %s attribute for a privilege configuration.", error)
                except ValueError as error:
                    logging.error ("Privilege configuration error: %s", error)

        for include_element in xml_root.iter('include'):
            include    = include_element.text

            if include is None:
                continue

            if not os.path.isabs(include):
                include = os.path.join(config_dir, include)

            new_config = read_configuration_file (server,
                                                  include,
                                                  config["address"],
                                                  config["port"],
                                                  server.db.state_graph,
                                                  server.db.storage,
                                                  server.base_url,
                                                  config["use_debugger"],
                                                  config["use_reloader"])
            config = { **config, **new_config }

        menu = xml_root.find("menu")
        if menu:
            for primary_menu_item in menu:
                submenu = []
                for submenu_item in primary_menu_item:
                    if submenu_item.tag == "sub-menu":
                        submenu.append({
                            "title": config_value (submenu_item, "title"),
                            "href":  config_value (submenu_item, "href")
                        })

                server.menu.append({
                    "title":   config_value (primary_menu_item, "title"),
                    "submenu": submenu
                })

            if not inside_reload:
                logging.info("Menu structure loaded")

        static_pages = xml_root.find("static-pages")
        if not static_pages:
            return config

        resources_root = config_value (static_pages, "resources-root", None, None)
        if not os.path.isabs(resources_root):
            # take resources_root relative to config_dir and turn into absolute path
            resources_root = os.path.abspath(os.path.join(config_dir, resources_root))
        if (server.add_static_root ("/s", resources_root) and not inside_reload):
            logging.info ("Added static root: %s", resources_root)

        for page in static_pages:
            uri_path        = config_value (page, "uri-path")
            filesystem_path = config_value (page, "filesystem-path")
            redirect_to     = page.find("redirect-to")

            if uri_path is not None and filesystem_path is not None:
                if not os.path.isabs(filesystem_path):
                    # take filesystem_path relative to config_dir and turn into absolute path
                    filesystem_path = os.path.abspath(os.path.join(config_dir, filesystem_path))

                server.static_pages[uri_path] = {"filesystem-path": filesystem_path}
                if not inside_reload:
                    logging.info ("Added static page: %s -> %s", uri_path, filesystem_path)
                    logging.info("Related filesystem path: %s", filesystem_path)

            if uri_path is not None and redirect_to is not None:
                code = 302
                if "code" in redirect_to.attrib:
                    code = int(redirect_to.attrib["code"])
                server.static_pages[uri_path] = {"redirect-to": redirect_to.text, "code": code}
                if not inside_reload:
                    logging.info ("Added static page: %s", uri_path)
                    logging.info ("Related redirect-to (%i) page: %s ", code, redirect_to.text)

        return config

    except ConfigFileNotFound:
        if not inside_reload:
            logging.error ("%s does not look like a Djehuty configuration file.",
                           config_file)
    except ET.ParseError:
        if not inside_reload:
            logging.error ("%s does not contain valid XML.", config_file)
    except FileNotFoundError as error:
        if not inside_reload:
            logging.error ("Could not open '%s'.", config_file)
        raise error

    return {}

## ----------------------------------------------------------------------------
## Starting point for the command-line program
## ----------------------------------------------------------------------------

def main (address=None, port=None, state_graph=None, storage=None,
          base_url=None, config_file=None, use_debugger=False,
          use_reloader=False, run_internal_server=True):
    """The main entry point for the 'web' subcommand."""
    try:
        server = wsgi.ApiServer ()
        config = read_configuration_file (server, config_file, address, port,
                                          state_graph, storage, base_url,
                                          use_debugger, use_reloader)

        if not server.db.cache.cache_is_ready():
            logging.error("Failed to set up cache layer.")

        if not server.in_production:
            logging.warning ("Assuming to run in a non-production environment.")
            logging.warning (("Set <production> to 1 in your configuration "
                              "file for hardened security settings."))

        if not run_internal_server:
            return server

        if os.environ.get('WERKZEUG_RUN_MAIN'):
            logging.info("Reloaded.")
        else:
            if not server.menu:
                logging.warning ("No menu structure provided.")

            if shutil.which ("git") is None:
                logging.error("Cannot find the 'git' executable.  Please install it.")

            logging.info("State graph:  %s.", server.db.state_graph)
            logging.info("Storage path: %s.", server.db.storage)
            logging.info("Running on %s", server.base_url)

        run_simple (config["address"], config["port"], server,
                    threaded=(config["maximum_workers"] <= 1),
                    processes=config["maximum_workers"],
                    use_debugger=config["use_debugger"],
                    use_reloader=config["use_reloader"])

    except FileNotFoundError:
        pass
    except database.UnknownDatabaseState:
        logging.error ("Please make sure the database is up and running.")

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
