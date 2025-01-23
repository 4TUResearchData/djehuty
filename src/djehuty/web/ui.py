"""This module contains the command-line interface for the 'web' subcommand."""

import logging
import sys
import os
import socket
import shutil
import json
from defusedxml import ElementTree
from werkzeug.serving import run_simple
from rdflib.plugins.stores import berkeleydb
from djehuty.web import wsgi
from djehuty.utils import convenience
import djehuty.backup.database as backup_database
from djehuty.web.config import config

# Even though we don't use these imports in 'ui', the state of
# SAML2_DEPENDENCY_LOADED is important to catch the situation
# in which this dependency is required due to the run-time configuration.
try:
    from onelogin.saml2.auth import OneLogin_Saml2_Auth  # pylint: disable=unused-import
    from onelogin.saml2.errors import OneLogin_Saml2_Error  # pylint: disable=unused-import
    SAML2_DEPENDENCY_LOADED = True
except (ImportError, ModuleNotFoundError):
    SAML2_DEPENDENCY_LOADED = False

PYVIPS_ERROR_MESSAGE = None
try:
    import pyvips  # pylint: disable=unused-import
    PYVIPS_DEPENDENCY_LOADED = True
except (ImportError, ModuleNotFoundError):
    PYVIPS_DEPENDENCY_LOADED = False
except OSError as pyvips_oserror_message:
    PYVIPS_DEPENDENCY_LOADED = False
    PYVIPS_ERROR_MESSAGE = pyvips_oserror_message

# The 'uwsgi' module only needs to be available when deploying using uwsgi.
# To catch potential run-time problems early on in the situation that the
# uwsgi module is required, we set UWSGI_DEPENDENCY_LOADED here without
# actually using the module itself. It merely provides a mechanism to detect
# a run-time configuration error.
try:
    import uwsgi  # pylint: disable=unused-import
    UWSGI_DEPENDENCY_LOADED = True
except ModuleNotFoundError:
    UWSGI_DEPENDENCY_LOADED = False

class ConfigFileNotFound(Exception):
    """Raised when the database is not queryable."""

class UnsupportedSAMLProtocol(Exception):
    """Raised when an unsupported SAML protocol is used."""

class DependencyNotAvailable(Exception):
    """Raised when a required software dependency isn't available."""

class MissingConfigurationError(Exception):
    """Raised when a crucial piece of configuration is missing."""

def config_value (xml_root, path, command_line=None, fallback=None, return_node=False):
    """Procedure to get the value a config item should have at run-time."""

    ## Prefer command-line arguments.
    if command_line:
        return command_line

    ## Read from the configuration file.
    if xml_root:
        item = xml_root.find(path)
        if item is not None:
            if return_node:
                return item
            return item.text

    ## Fall back to the fallback value.
    return fallback

def read_boolean_value (xml_root, path, default_value, logger):
    """Parses a boolean option and sets DESTINATION if the option is present."""
    try:
        parsed = config_value (xml_root, path, None, None)
        if parsed is not None:
            return bool(int(parsed))
    except (ValueError, TypeError):
        logger.error ("Erroneous value for '%s' - assuming '%s'.", path, default_value)

    return default_value

def read_raw_xml (xml_root, path, default_value=None):
    """
    Return the inner XML for PATH in XML_ROOT as a string or
    DEFAULT_VALUE upon failure.
    """
    try:
        length = len(path) + 2 # Add two for the < and >.
        node = config_value (xml_root, path, None, None, return_node=True)
        if node is not None:
            # Attributes are rendered in the raw XML. We need to
            # remove it to get the inner XML.
            attributes = node.attrib
            attributes_rendered_length = 0
            for key in attributes.keys():
                # Account for the key length and the '='.
                attributes_rendered_length += len(key) + 1
                # Account for the length of the value.
                value = attributes.get(key)
                attributes_rendered_length += len(value)
                # Account for the quotes.
                if isinstance(value, str):
                    attributes_rendered_length += 2
            # Account for the closing '>'.
            if attributes_rendered_length > 0:
                attributes_rendered_length += 1

            # Get the raw XML so it can be used verbatim.
            text = ElementTree.tostring (node, encoding="unicode")
            # Strip the <path></path> bits and surrounding whitespace.
            text = text.strip()[(length + attributes_rendered_length):(-1 * (length + 1))].strip()
            return text, attributes
    except TypeError:
        pass

    return default_value, None

def read_storage_locations (xml_root):
    """Procedure to read storage locations."""

    storage = xml_root.find ("storage")
    if not storage:
        return None

    for location in storage:
        if location.tag != "location":
            continue
        quirks = location.attrib.get("quirks") == "1"
        config.storage_locations.append({ "path": location.text, "quirks": quirks })

    return None

def read_quotas_configuration (xml_root):
    """Read quota information from XML_ROOT."""

    quotas = xml_root.find("quotas")
    if not quotas:
        return None

    # Set the default quota for non-members.
    try:
        config.default_quota = int(quotas.attrib["default"])
    except (ValueError, TypeError):
        pass

    # Set specific quotas for member institutions and accounts.
    for quota_specification in quotas:
        email  = quota_specification.attrib.get("email")
        domain = quota_specification.attrib.get("domain")
        value  = None
        try:
            value = int(quota_specification.text)
        except (ValueError, TypeError):
            pass

        # Organization-wide quotas
        if domain is not None:
            config.group_quotas[domain] = value

        # Account-specific quotas
        elif email is not None:
            config.account_quotas[email.lower()] = value

    return None

def read_sram_configuration (xml_root):
    """Read the SRAM configuration from XML_ROOT."""

    sram = xml_root.find("authentication/saml/sram")
    if not sram:
        return None

    config.sram_organization_api_token = config_value (sram, "organization-api-token", fallback = config.sram_organization_api_token)
    config.sram_collaboration_id = config_value (sram, "collaboration-id", fallback = config.sram_collaboration_id)
    return None

def read_saml_configuration (xml_root, logger):
    """Read the SAML configuration from XML_ROOT."""

    saml = xml_root.find("authentication/saml")
    if not saml:
        return None

    saml_version = None
    if "version" in saml.attrib:
        saml_version = saml.attrib["version"]

    if saml_version != "2.0":
        logger.error ("Only SAML 2.0 is supported.")
        raise UnsupportedSAMLProtocol

    saml_strict = bool(int(config_value (saml, "strict", None, True)))
    saml_debug  = bool(int(config_value (saml, "debug", None, False)))

    ## Attributes expected to receive from the IdP
    attributes           = saml.find ("attributes")
    if attributes is None:
        logger.error ("Missing attributes information for SAML.")
    else:
        config.saml_attribute_first_name = config_value (attributes, "first-name")
        config.saml_attribute_last_name = config_value (attributes, "last-name")
        config.saml_attribute_common_name = config_value (attributes, "common-name")
        config.saml_attribute_email = config_value (attributes, "email")
        config.saml_attribute_groups = config_value (attributes, "groups")
        config.saml_attribute_group_prefix = config_value (attributes, "group-prefix")

    ## Service Provider settings
    service_provider     = saml.find ("service-provider")
    if service_provider is None:
        logger.error ("Missing service-provider information for SAML.")

    saml_sp_x509         = config_value (service_provider, "x509-certificate")
    saml_sp_private_key  = config_value (service_provider, "private-key")

    ## Service provider metadata
    sp_metadata          = service_provider.find ("metadata")
    if sp_metadata is None:
        logger.error ("Missing service provider's metadata for SAML.")

    organization_name    = config_value (sp_metadata, "display-name")
    organization_url     = config_value (sp_metadata, "url")

    sp_tech_contact      = sp_metadata.find ("./contact[@type='technical']")
    if sp_tech_contact is None:
        logger.error ("Missing technical contact information for SAML.")
    sp_tech_email        = config_value (sp_tech_contact, "email")
    if sp_tech_email is None:
        sp_tech_email = "-"

    sp_admin_contact     = sp_metadata.find ("./contact[@type='administrative']")
    if sp_admin_contact is None:
        logger.error ("Missing administrative contact information for SAML.")
    sp_admin_email        = config_value (sp_admin_contact, "email")
    if sp_admin_email is None:
        sp_admin_email = "-"

    sp_support_contact   = sp_metadata.find ("./contact[@type='support']")
    if sp_support_contact is None:
        logger.error ("Missing support contact information for SAML.")
    sp_support_email        = config_value (sp_support_contact, "email")
    if sp_support_email is None:
        sp_support_email = "-"

    ## Identity Provider settings
    identity_provider    = saml.find ("identity-provider")
    if identity_provider is None:
        logger.error ("Missing identity-provider information for SAML.")

    saml_idp_entity_id   = config_value (identity_provider, "entity-id")
    saml_idp_x509        = config_value (identity_provider, "x509-certificate")

    sso_service          = identity_provider.find ("single-signon-service")
    if sso_service is None:
        logger.error ("Missing SSO information of the identity-provider for SAML.")

    saml_idp_sso_url     = config_value (sso_service, "url")
    saml_idp_sso_binding = config_value (sso_service, "binding")

    config.identity_provider = "saml"

    ## Create an almost-ready-to-serialize configuration structure.
    ## The SP entityId will and ACS URL be generated at a later time.
    config.saml_config = {
        "strict": saml_strict,
        "debug":  saml_debug,
        "sp": {
            "entityId": None,
            "assertionConsumerService": {
                "url": None,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
            },
            "singleLogoutService": {
                "url": None,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:2.0:nameid-format:persistent",
            "x509cert": saml_sp_x509,
            "privateKey": saml_sp_private_key
        },
        "idp": {
            "entityId": saml_idp_entity_id,
            "singleSignOnService": {
                "url": saml_idp_sso_url,
                "binding": saml_idp_sso_binding
            },
            "singleLogoutService": {
                "url": None,
                "binding": None
            },
            "x509cert": saml_idp_x509
        },
        "security": {
            "nameIdEncrypted": False,
            "authnRequestsSigned": True,
            "logoutRequestSigned": True,
            "logoutResponseSigned": True,
            "signMetadata": True,
            "wantMessagesSigned": False,
            "wantAssertionsSigned": False,
            "wantNameId" : True,
            "wantNameIdEncrypted": False,
            "wantAssertionsEncrypted": False,
            "allowSingleLabelDomains": False,
            "signatureAlgorithm": "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",
            "digestAlgorithm": "http://www.w3.org/2001/04/xmlenc#sha256",
            "rejectDeprecatedAlgorithm": True
        },
        "contactPerson": {
            "technical": {
                "givenName": "Technical support",
                "emailAddress": sp_tech_email
            },
            "support": {
                "givenName": "General support",
                "emailAddress": sp_support_email
            },
            "administrative": {
                "givenName": "Administrative support",
                "emailAddress": sp_admin_email
            }
        },
        "organization": {
            "nl": {
                "name": organization_name,
                "displayname": organization_name,
                "url": organization_url
            },
            "en": {
                "name": organization_name,
                "displayname": organization_name,
                "url": organization_url
            }
        }
    }

    del saml_sp_x509
    del saml_sp_private_key
    return None

def setup_saml_service_provider (server, logger):
    """Write the SAML configuration file to disk and set up its metadata."""
    ## python3-saml wants to read its configuration from a file,
    ## but unfortunately we can only indicate the directory for that
    ## file.  Therefore, we create a separate directory in the cache
    ## for this purpose and place the file in that directory.
    if config.identity_provider == "saml":
        if not SAML2_DEPENDENCY_LOADED:
            logger.error ("Missing python3-saml dependency.")
            logger.error ("Cannot initiate authentication with SAML.")
            raise DependencyNotAvailable

        saml_cache_dir = os.path.join(server.db.cache.storage, "saml-config")
        os.makedirs (saml_cache_dir, mode=0o700, exist_ok=True)
        if os.path.isdir (saml_cache_dir):
            filename  = os.path.join (saml_cache_dir, "settings.json")
            saml_base_url = f"{config.base_url}/saml"
            saml_idp_binding = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            # pylint: disable=unsubscriptable-object
            # PyLint assumes config.saml_config is None, but we can be certain
            # it contains a saml configuration, because otherwise
            # config.identity_provider wouldn't be set to "saml".
            config.saml_config["sp"]["entityId"] = saml_base_url
            config.saml_config["sp"]["assertionConsumerService"]["url"] = f"{saml_base_url}/login"
            config.saml_config["idp"]["singleSignOnService"]["binding"] = saml_idp_binding
            # pylint: enable=unsubscriptable-object
            config_fd = os.open (filename, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with open (config_fd, "w", encoding="utf-8") as file_stream:
                json.dump(config.saml_config, file_stream)
            config.saml_config_path = saml_cache_dir
        else:
            logger.error ("Failed to create '%s'.", saml_cache_dir)


def refresh_group_configuration (server, logger, config_files):
    """Read and apply the group configuration from CONFIG_FILES."""
    for config_file in config_files:
        tree = ElementTree.parse(config_file)
        xml_root = tree.getroot()
        if xml_root.tag != "djehuty":
            continue
        groups = xml_root.find("groups")
        if not groups:
            continue

        logger.info ("Refreshing groups configuration.")
        server.db.delete_inferred_groups()

        for group in groups:
            group_name = group.attrib["name"]
            group_id = group.attrib["id"]
            parent_id = convenience.value_or_none (group.attrib, "parent_id")
            domain = group.attrib["domain"]
            is_featured = group.attrib.get("is_featured") == "1"
            group_uuid = server.db.insert_group (group_name, True, is_featured, group_id, parent_id, domain)
            for member in group:
                is_supervisor = member.attrib.get("is_supervisor") == "1"
                email = member.attrib.get("email")
                if email is None:
                    logger.error ("Account must have 'email' attribute.")
                    continue
                email = email.lower()
                account = server.db.account_by_email(email)
                if account is not None:
                    logger.info("Account %s already exists.", email)
                    server.db.insert_group_member (group_uuid, account["uuid"], is_supervisor)
                    server.db.update_account (account["uuid"], domain=domain)
                else:
                    logger.info("Account %s does not exist.", email)
                    first_name = member.attrib.get("first_name")
                    last_name  = member.attrib.get("last_name")
                    common_name = f"{first_name} {last_name}"
                    if first_name is None and last_name is None:
                        logger.warning ("Adding account %s without name.", email)
                        common_name = None
                    account_uuid = server.db.insert_account (
                        email       = email,
                        first_name  = first_name,
                        last_name   = last_name,
                        common_name = common_name,
                        domain      = domain)
                    if account_uuid is None:
                        logger.error("Cannot find account for %s.", email)
                        continue
                    server.db.insert_group_member (group_uuid, account_uuid, is_supervisor)

def write_pem_file (file_stream, contents, format_name):
    """Writes CONTENTS to FILE_STREAM."""
    file_stream.write(f"-----BEGIN {format_name}-----\n")
    total_length = len(contents)
    start = 0
    while start < total_length:
        file_stream.write (contents[start:start+64])
        file_stream.write ("\n")
        start += 64
    file_stream.write(f"-----END {format_name}-----\n")

def setup_handle_registration (server, logger):
    """Write the Handle configuration to a file."""

    handle_cache_dir = os.path.join(server.db.cache.storage, "handle-config")
    os.makedirs (handle_cache_dir, mode=0o700, exist_ok=True)
    if not os.path.isdir (handle_cache_dir):
        logger.error ("Failed to create '%s'.", handle_cache_dir)

    config.handle_certificate_path = os.path.join (handle_cache_dir, "certificate.pem")
    config.handle_private_key_path = os.path.join (handle_cache_dir, "certificate.key")

    if config.handle_certificate is None or config.handle_private_key is None:
        return None

    config_fd = os.open (config.handle_certificate_path,
                         os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                         0o600)
    with open (config_fd, "w", encoding="utf-8") as file_stream:
        write_pem_file (file_stream, config.handle_certificate, "CERTIFICATE")

    config_fd = os.open (config.handle_private_key_path,
                         os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                         0o600)
    with open (config_fd, "w", encoding="utf-8") as file_stream:
        write_pem_file (file_stream, config.handle_private_key, "PRIVATE KEY")

    return None

def read_privilege_configuration (xml_root, logger):
    """Read the privileges configuration from XML_ROOT."""
    privileges = xml_root.find("privileges")
    if not privileges:
        return None

    for account in privileges:
        try:
            email = account.attrib["email"]
            orcid = None
            if "orcid" in account.attrib:
                orcid = account.attrib["orcid"]
            lowercase_email = email.lower()
            config.privileges[lowercase_email] = {
                "may_administer":  bool(int(config_value (account, "may-administer", None, False))),
                "may_query":       bool(int(config_value (account, "may-run-sparql-queries", None, False))),
                "may_impersonate": bool(int(config_value (account, "may-impersonate", None, False))),
                "may_review":      bool(int(config_value (account, "may-review", None, False))),
                "may_review_institution": bool(int(config_value (account, "may-review-institution", None, False))),
                "may_review_quotas": bool(int(config_value (account, "may-review-quotas", None, False))),
                "may_review_integrity": bool(int(config_value (account, "may-review-integrity", None, False))),
                "may_process_feedback": bool(int(config_value (account, "may-process-feedback", None, False))),
                "may_receive_email_notifications": bool(int(config_value (account, "may-receive-email-notifications", None, True))),
                "orcid":           orcid,
                "first_name":      account.attrib.get("first_name"),
                "last_name":       account.attrib.get("last_name"),
            }

            ## The "needs_2fa" property is set to True when the user has any
            ## extra privilege.
            config.privileges[lowercase_email]["needs_2fa"] = (not config.disable_2fa) and (
                config.privileges[lowercase_email]["may_administer"] or
                config.privileges[lowercase_email]["may_query"] or
                config.privileges[lowercase_email]["may_impersonate"] or
                config.privileges[lowercase_email]["may_review"] or
                config.privileges[lowercase_email]["may_process_feedback"] or
                config.privileges[lowercase_email]["may_review_quotas"]
            )

        except KeyError as error:
            logger.error ("Missing %s attribute for a privilege configuration.", error)
        except ValueError as error:
            logger.error ("Privilege configuration error: %s", error)

    return None

def configure_file_logging (log_file, inside_reload, logger):
    """Procedure to set up logging to a file."""
    is_writeable = False
    log_file     = os.path.abspath (log_file)
    try:
        with open (log_file, "a", encoding = "utf-8"):
            is_writeable = True
    except (PermissionError, FileNotFoundError):
        pass

    if not is_writeable:
        if not inside_reload:
            logger.warning ("Cannot write to '%s'.", log_file)
    else:
        file_handler = logging.FileHandler (log_file, 'a')
        if not inside_reload:
            logger.info ("Writing further messages to '%s'.", log_file)

        formatter    = logging.Formatter('[%(levelname)s] %(asctime)s - %(name)s: %(message)s')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        log          = logging.getLogger()
        for handler in log.handlers[:]:
            log.removeHandler(handler)
        log.addHandler(file_handler)

def read_menu_configuration (xml_root):
    """Procedure to parse the menu configuration from XML_ROOT."""
    menu = xml_root.find("menu")
    if not menu:
        return None

    for primary_menu_item in menu:
        submenu = []
        for submenu_item in primary_menu_item:
            if submenu_item.tag == "sub-menu":
                submenu.append({
                    "title": config_value (submenu_item, "title"),
                    "href":  config_value (submenu_item, "href")
                })

        config.menu.append({
            "title":   config_value (primary_menu_item, "title"),
            "submenu": submenu
        })

    return None

def read_static_pages (static_pages, server, config_dir):
    """Procedure to parse and register static pages."""
    for page in static_pages:
        uri_path        = config_value (page, "uri-path")
        filesystem_path = config_value (page, "filesystem-path")
        redirect_to     = page.find("redirect-to")

        if uri_path is not None and filesystem_path is not None:
            if not os.path.isabs(filesystem_path):
                # take filesystem_path relative to config_dir and turn into absolute path
                filesystem_path = os.path.abspath(os.path.join(config_dir, filesystem_path))

            server.static_pages[uri_path] = {"filesystem-path": filesystem_path}

        if uri_path is not None and redirect_to is not None:
            code = 302
            if "code" in redirect_to.attrib:
                code = int(redirect_to.attrib["code"])
            server.static_pages[uri_path] = {"redirect-to": redirect_to.text, "code": code}

def read_colors_configuration (xml_root):
    """Procedure to parse and set the color scheme configuration."""
    colors = xml_root.find("colors")
    if colors:
        for color in ["primary-color", "primary-color-hover",
                      "primary-color-active", "primary-foreground-color",
                      "privilege-button-color", "footer-background-color"]:
            config.colors[color] = config_value (colors, color, fallback=config.colors[color])

def read_datacite_configuration (xml_root):
    """Procedure to parse and set the DataCite API configuration."""
    datacite = xml_root.find("datacite")
    if datacite:
        config.datacite_url      = config_value (datacite, "api-url")
        config.datacite_id       = config_value (datacite, "repository-id")
        config.datacite_password = config_value (datacite, "password")
        config.datacite_prefix   = config_value (datacite, "prefix")

def read_handle_configuration (xml_root):
    """Procedure to parse and set the Handle API configuration."""
    handle = xml_root.find("handle")
    if handle:
        config.handle_url         = config_value (handle, "url")
        config.handle_certificate = config_value (handle, "certificate")
        config.handle_private_key = config_value (handle, "private-key")
        config.handle_prefix      = config_value (handle, "prefix")
        config.handle_index       = config_value (handle, "index")

def read_automatic_login_configuration (xml_root):
    """Procedure to parse and set automatic login for development setups."""
    automatic_login_email = config_value (xml_root, "authentication/automatic-login-email")
    if (automatic_login_email is not None
        and config.orcid_client_id is None
        and config.saml_config is None):
        config.identity_provider = "automatic-login"
        config.automatic_login_email = automatic_login_email

def read_orcid_configuration (xml_root):
    """Procedure to parse and set the ORCID API configuration."""
    orcid = xml_root.find("authentication/orcid")
    if orcid:
        config.orcid_client_id     = config_value (orcid, "client-id")
        config.orcid_client_secret = config_value (orcid, "client-secret")
        config.orcid_endpoint      = config_value (orcid, "endpoint")
        config.orcid_read_public_token = config_value (orcid, "read-public-token")

        # SAML takes precedence over ORCID authentication.
        if config.identity_provider != "saml":
            config.identity_provider   = "orcid"

def read_email_configuration (server, xml_root, logger):
    """Procedure to parse and set the email server configuration."""
    email = xml_root.find("email")
    if email:
        try:
            server.email.smtp_port = int(config_value (email, "port"))
            server.email.smtp_server = config_value (email, "server")
            server.email.from_address = config_value (email, "from")
            server.email.smtp_username = config_value (email, "username")
            server.email.smtp_password = config_value (email, "password")
            server.email.subject_prefix = config_value (email, "subject-prefix", None, None)
            server.email.do_starttls = bool(int(config_value (email, "starttls", None, 0)))
        except ValueError:
            logger.error ("Could not configure the email subsystem:")
            logger.error ("The email port should be a numeric value.")

def read_configuration_file (server, config_file, logger, config_files):
    """Procedure to parse a configuration file."""

    inside_reload = os.environ.get('WERKZEUG_RUN_MAIN')
    try:
        if config_file is None:
            raise FileNotFoundError

        xml_root = None
        tree = ElementTree.parse(config_file)
        if config_file is not None:
            config_files.add (config_file)
            if not inside_reload:
                logger.info ("Reading config file: %s", config_file)

        xml_root = tree.getroot()
        if not xml_root or xml_root.tag != "djehuty":
            raise ConfigFileNotFound

        config_dir = os.path.dirname(config_file)
        log_file = config_value (xml_root, "log-file", None, None)
        if log_file is not None:
            config.log_file = log_file
            configure_file_logging (log_file, inside_reload, logger)

        config.address      = config_value (xml_root, "bind-address", config.address, "127.0.0.1")
        config.port         = int(config_value (xml_root, "port", config.port, 8080))
        config.alternative_port = config_value (xml_root, "alternative-port",
                                                config.alternative_port, None)
        if config.alternative_port is not None:
            config.alternative_port = int(config.alternative_port)

        if config.base_url is None:
            config.base_url = f"http://{config.address}:{config.port}"

        config.base_url     = config_value (xml_root, "base-url", None, config.base_url)
        config.storage      = config_value (xml_root, "storage-root", None, config.storage)
        config.state_graph  = config_value (xml_root, "rdf-store/state-graph", None, config.state_graph)

        live_reload             = convenience.value_or_none (config, "live-reload")
        config.use_reloader  = config_value (xml_root, "live-reload", None, live_reload)

        debug_mode             = convenience.value_or_none (config, "debug-mode")
        config.use_debugger    = config_value (xml_root, "debug-mode", None, debug_mode)
        config.maximum_workers = int(config_value (xml_root, "maximum-workers", None, 1))

        endpoint = config_value (xml_root, "rdf-store/sparql-uri")
        if endpoint:
            config.endpoint = endpoint

        update_endpoint = config_value (xml_root, "rdf-store/sparql-update-uri")
        if update_endpoint:
            config.update_endpoint = update_endpoint

        config.show_portal_summary = read_boolean_value (xml_root, "show-portal-summary",
                                                         config.show_portal_summary, logger)

        config.show_institutions = read_boolean_value (xml_root, "show-institutions",
                                                       config.show_institutions, logger)

        config.show_science_categories = read_boolean_value (xml_root, "show-science-categories",
                                                             config.show_science_categories, logger)

        config.show_latest_datasets = read_boolean_value (xml_root, "show-latest-datasets",
                                                          config.show_latest_datasets, logger)

        config.maintenance_mode = read_boolean_value (xml_root, "maintenance-mode",
                                                      config.maintenance_mode, logger)

        config.disable_2fa = read_boolean_value (xml_root, "disable-2fa",
                                                 config.disable_2fa, logger)

        config.allow_crawlers = read_boolean_value (xml_root, "allow-crawlers",
                                                    config.allow_crawlers, logger)

        config.enable_iiif = read_boolean_value (xml_root, "enable-iiif",
                                                 config.enable_iiif, logger)

        config.delay_inserting_log_entries = read_boolean_value (xml_root, "delay-inserting-log-entries",
                                                                 config.delay_inserting_log_entries, logger)

        ssi_psk = config_value (xml_root, "ssi-psk")
        if ssi_psk is not None:
            ssi_psk = ssi_psk.replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", "")
            config.ssi_psk = ssi_psk

        enable_query_audit_log = xml_root.find ("enable-query-audit-log")
        if enable_query_audit_log is not None:
            transactions_directory = enable_query_audit_log.attrib.get("transactions-directory")
            if transactions_directory is not None:
                config.transactions_directory = transactions_directory
            try:
                config.enable_query_audit_log = bool(int(enable_query_audit_log.text))
            except (ValueError, TypeError):
                logger.info("Invalid value for enable-query-audit-log. Ignoring.. assuming 1 (True)")

        if config.use_reloader:
            config.use_reloader = bool(int(config.use_reloader))
        if config.use_debugger:
            config.use_debugger = bool(int(config.use_debugger))

        cache_root = xml_root.find ("cache-root")
        if cache_root is not None:
            server.db.cache.storage = cache_root.text
            try:
                clear_on_start = cache_root.attrib.get("clear-on-start")
                config.clear_cache_on_start = bool(int(clear_on_start))
            except ValueError:
                logger.warning ("Invalid value for the 'clear-on-start' attribute in 'cache-root'.")
                logger.warning ("Will not clear cache on start; Use '1' to enable, or '0' to disable.")
                config.clear_cache_on_start = False
            except TypeError:
                config.clear_cache_on_start = False
        elif server.db.cache.storage is None:
            server.db.cache.storage = os.path.join (config.storage, "cache")

        profile_images_root = xml_root.find ("profile-images-root")
        if profile_images_root is not None:
            config.profile_images_storage = profile_images_root.text
        elif config.profile_images_storage is None:
            config.profile_images_storage = os.path.join (config.storage, "profile-images")

        thumbnails_root = xml_root.find ("thumbnails-root")
        if thumbnails_root is not None:
            config.thumbnail_storage = thumbnails_root.text
        elif config.thumbnail_storage is None:
            config.thumbnail_storage = os.path.join (config.storage, "thumbnails")

        iiif_cache = xml_root.find ("iiif-cache-root")
        if iiif_cache is not None:
            config.iiif_cache_storage = iiif_cache.text
        elif config.iiif_cache_storage is None:
            config.iiif_cache_storage = os.path.join (config.storage, "iiif")

        production_mode = xml_root.find ("production")
        if production_mode is not None:
            config.in_production = bool(int(production_mode.text))
            try:
                pre_production = production_mode.attrib.get("pre-production")
                if pre_production is not None:
                    config.in_preproduction = bool(int(pre_production))
            except (ValueError, TypeError):
                logger.warning ("Invalid value for the 'pre-production' attribute in 'production'.")
                logger.warning ("Pre-production mode is enabled; Use either '1' to enable, or '0' to disable.")
                config.in_preproduction = True

        secondary_storage = xml_root.find ("secondary-storage-root")
        if secondary_storage is not None:
            config.secondary_storage = secondary_storage.text
            try:
                quirks = secondary_storage.attrib.get("quirks")
                config.secondary_storage_quirks = bool(int(quirks))
            except ValueError:
                logger.warning ("Invalid value for the 'quirks' attribute in 'secondary-storage-root'.")
                logger.warning ("Quirks-mode is disabled; Use either '1' to enable, or '0' to disable.")
                config.secondary_storage_quirks = False
            except TypeError:
                config.secondary_storage_quirks = False

        use_x_forwarded_for = bool(int(config_value (xml_root, "use-x-forwarded-for", None, 0)))
        if use_x_forwarded_for:
            server.log_access = server.log_access_using_x_forwarded_for

        config.disable_collaboration = read_boolean_value (xml_root, "disable-collaboration",
                                                           config.disable_collaboration,
                                                           logger)

        sandbox_message, sandbox_message_attributes = read_raw_xml (xml_root, "sandbox-message")
        if sandbox_message:
            config.sandbox_message_css = sandbox_message_attributes.get("style")
            config.sandbox_message = sandbox_message

        notice_message, _ = read_raw_xml (xml_root, "notice-message")
        if notice_message:
            config.notice_message = notice_message

        large_footer, _ = read_raw_xml (xml_root, "large-footer")
        if large_footer:
            config.large_footer = large_footer

        small_footer, _ = read_raw_xml (xml_root, "small-footer")
        if small_footer:
            config.small_footer = small_footer

        site_name = xml_root.find ("site-name")
        if site_name is not None:
            config.site_name = site_name.text

        site_description = xml_root.find ("site-description")
        if site_description is not None:
            config.site_description = site_description.text

        site_shorttag = xml_root.find ("site-shorttag")
        if site_shorttag is not None:
            config.site_shorttag = site_shorttag.text

        support_email_address = xml_root.find ("support-email-address")
        if support_email_address is not None:
            config.support_email_address = support_email_address.text

        depositing_domains = xml_root.find ("allowed-depositing-domains")
        if depositing_domains is not None:
            for domain in depositing_domains:
                if domain.tag != "domain":
                    logger.error ("Unexpected '%s' in 'allowed-depositing-domains'.", domain.tag)
                    raise SystemExit
                if domain.text is None or domain.text.strip() == "":
                    continue
                config.depositing_domains.append (domain.text.strip())

        read_orcid_configuration (xml_root)
        read_datacite_configuration (xml_root)
        read_handle_configuration (xml_root)
        read_email_configuration (server, xml_root, logger)
        read_saml_configuration (xml_root, logger)
        read_sram_configuration (xml_root)
        read_automatic_login_configuration (xml_root)
        read_privilege_configuration (xml_root, logger)
        read_storage_locations (xml_root)
        read_quotas_configuration (xml_root)
        read_colors_configuration (xml_root)

        for include_element in xml_root.iter('include'):
            include    = include_element.text

            if include is None:
                continue

            if not os.path.isabs(include):
                include = os.path.join(config_dir, include)

            read_configuration_file (server, include, logger, config_files)

        read_menu_configuration (xml_root)

        custom_logo_path = config_value (xml_root, "custom-logo-path", None, None)
        if custom_logo_path:
            if not os.path.isabs (custom_logo_path):
                custom_logo_path = os.path.abspath(os.path.join (config_dir, custom_logo_path))
            server.add_static_root ("/static/images/logo.png", custom_logo_path, prepend=True)

        custom_favicon_path = config_value (xml_root, "custom-favicon-path", None, None)
        if custom_favicon_path:
            if not os.path.isabs (custom_favicon_path):
                custom_favicon_path = os.path.abspath(os.path.join (config_dir, custom_favicon_path))
            server.add_static_root ("/static/images/favicon.ico", custom_favicon_path, prepend=True)

        static_pages = xml_root.find("static-pages")
        if not static_pages:
            return config

        resources_root = config_value (static_pages, "resources-root", None, None)
        if not os.path.isabs(resources_root):
            # take resources_root relative to config_dir and turn into absolute path
            resources_root = os.path.abspath(os.path.join(config_dir, resources_root))
        if (server.add_static_root ("/s", resources_root) and not inside_reload):
            logger.info ("Added static root: %s", resources_root)

        read_static_pages (static_pages, server, config_dir)

        return config

    except ConfigFileNotFound as error:
        if not inside_reload:
            logger.error ("%s does not look like a Djehuty configuration file.",
                           config_file)
        raise SystemExit from error
    except ElementTree.ParseError as error:
        if not inside_reload:
            logger.error ("%s does not contain valid XML.", config_file)
        raise SystemExit from error
    except FileNotFoundError as error:
        if not inside_reload:
            if config_file is None:
                logger.error ("No configuration file specified.")
            else:
                logger.error ("Could not open '%s'.", config_file)
        raise SystemExit from error
    except UnsupportedSAMLProtocol as error:
        raise SystemExit from error

    return {}

def extract_transactions (since_datetime):
    """Extract the queries from the audit log and write them as files."""

    if config.log_file is None:
        print("No log file found to extract queries from.", file=sys.stderr)
        return False

    filename = config.log_file
    try:
        if config.transactions_directory is not None:
            directory_prefix = config.transactions_directory
            os.makedirs(directory_prefix, mode=0o700, exist_ok=True)
            if not os.path.isdir(directory_prefix):
                print (f"Failed to create '{directory_prefix}'.", file=sys.stderr)
        else:
            directory_prefix = "."

        with open (filename, "r", encoding = "utf-8") as log_file:
            print (f"Reading '{filename}'.", file=sys.stderr)
            count        = 0
            state_output = 0
            query        = ""
            timestamp_line = ""
            for line in log_file:
                if state_output == 2:
                    if line == "---\n":
                        state_output = 0
                        with open (os.path.join (directory_prefix, f"transaction_{count:08d}.sparql"),
                                   "w", encoding="utf-8") as output_file:
                            output_file.write (query)
                        query = ""
                    else:
                        now_statement = "    BIND(NOW() AS ?now)\n"
                        if now_statement == line:
                            try:
                                components = timestamp_line.split(" ")
                                date       = components[1]
                                time       = components[2].partition(",")[0]
                                replacement = (f'    BIND("{date}T{time}Z"'
                                               '^^xsd:dateTime AS ?now)\n')
                                line = line.replace (now_statement, replacement)
                            except IndexError:
                                print (f"Failed to read '{timestamp_line}'.",
                                       file=sys.stderr)

                        # Due to a bug (c7204bc), some queries contained the
                        # following line.  It's safe to re-run the query
                        # without this line.  It only cleans up some triples.
                        if line != "{self.default_prefixes}\n":
                            query += line
                elif state_output == 1 and line == "---\n":
                    state_output = 2
                elif "Query Audit Log" in line:
                    timestamp_line = line

                    if since_datetime:
                        # [INFO] 2023-07-28 20:58:35,089 -
                        log_datetime = " ".join(line.split(" ")[1:3])
                        if log_datetime < since_datetime:
                            continue

                    query += f"# {line}"
                    count += 1
                    state_output = 1
            print (f"Extracted {count} items", file=sys.stderr)
            return True
    except FileNotFoundError:
        print (f"Could not open '{filename}'.", file=sys.stderr)
        return False

def apply_transactions_from_directory (logger, server, transactions_directory):
    """Apply extracted transactions from the query audit log."""

    # Override with the value from the configuration file.
    directory = transactions_directory
    if config.transactions_directory is not None:
        directory = config.transactions_directory

    print (f"Finding transactions in '{directory}'.")
    transactions = list(filter(lambda x: (x.startswith("transaction_") and
                                          x.endswith(".sparql")),
                               os.listdir(directory)))
    transactions = sorted(transactions)

    number_of_transactions = len(transactions)
    if number_of_transactions < 1:
        print("No transactions to apply.")
        return False

    print(f"Applying {number_of_transactions} transactions.")
    try:
        for transaction_file in transactions:
            filename = os.path.join (directory, transaction_file)
            applied_filename = os.path.join (directory, f"applied_{transaction_file}")
            with open(filename, "r", encoding="utf-8") as transaction:
                query = transaction.read()
                server.db.sparql.update (query)
                server.db.sparql.commit()
                print(f"Applied {transaction.name}.")
            os.rename (filename, applied_filename)

        with open (applied_filename, "r", encoding="utf-8") as transaction:
            line           = transaction.readline()
            last_timestamp = " ".join(line.split(" ")[2:4])
            logger.setLevel(logging.INFO)
            logger.info ("Applied transactions up until %s.", last_timestamp)
        return True
    except Exception as error:  # pylint: disable=broad-exception-caught
        print ("Applying transaction failed.", file=sys.stderr)
        print (f"Exception: {type(error)}: {error}", file=sys.stderr)

    return False

def perform_rdf_export (logger, server, full_export):
    """Make an RDF export of of the currently configured SPARQL endpoint."""

    if not server.db.export_rdf (full_export):
        logger.error ("Unable to create RDF export.")
        return False

    logger.info ("Created RDF export in '%s'", config.export_directory)
    return True

## ----------------------------------------------------------------------------
## Starting point for the command-line program
## ----------------------------------------------------------------------------

def main (config_file=None, run_internal_server=True, initialize=True,
          extract_transactions_from_log=None, apply_transactions=None,
          full_rdf_export=False, public_rdf_export=False):
    """The main entry point for the 'web' subcommand."""
    try:
        convenience.add_logging_level ("AUDIT", logging.INFO + 6)
        convenience.add_logging_level ("ACCESS", logging.INFO + 5)
        convenience.add_logging_level ("STORE", logging.INFO + 4)

        ## Differentiate the logger name for uWSGI vs built-in.
        logger = None
        if run_internal_server:
            logger = logging.getLogger (__name__)
        else:
            logger = logging.getLogger ("uwsgi:djehuty.web.ui")

        perform_export = full_rdf_export or public_rdf_export
        since_datetime = None
        ## Be less verbose when only extracting Query Audit Logs or making
        ## RDF exports.
        if extract_transactions_from_log is not None:
            logger = logging.getLogger (__name__)
            logger.setLevel(logging.ERROR)
            since_datetime = extract_transactions_from_log

        if apply_transactions is not None or perform_export:
            logger = logging.getLogger (__name__)
            logger.setLevel(logging.ERROR)

        server = wsgi.WebServer ()
        config_files = set()
        read_configuration_file (server, config_file, logger, config_files)

        ## Handle extracting Query Audit Logs early on.
        if extract_transactions_from_log is not None:
            return extract_transactions (since_datetime)

        inside_reload = os.environ.get('WERKZEUG_RUN_MAIN')

        if (isinstance (config.endpoint, str) and
            config.endpoint.startswith("bdb://") and
            not berkeleydb.has_bsddb):
            logger.error(("Configured a BerkeleyDB database back-end, "
                          "but BerkeleyDB is not installed on the system "
                          "or the 'berkeleydb' Python package is missing."))
            raise DependencyNotAvailable

        if not server.db.cache.cache_is_ready() and not inside_reload:
            logger.error ("Failed to set up cache layer.")

        if config.clear_cache_on_start and not inside_reload:
            logger.info ("Clearing cache.")
            server.db.cache.invalidate_all ()

        setup_saml_service_provider (server, logger)
        if config.handle_url is not None:
            setup_handle_registration (server, logger)

        if not config.in_production and not inside_reload:
            logger.warning ("Assuming to run in a non-production environment.")
            logger.warning (("Set <production> to 1 in your configuration "
                             "file for hardened security settings."))

        if config.in_production and not os.path.isdir (config.storage):
            logger.error ("The storage directory '%s' does not exist.", config.storage)
            raise FileNotFoundError

        if config.profile_images_storage is not None and not inside_reload:
            try:
                os.makedirs (config.profile_images_storage, mode=0o700, exist_ok=True)
            except PermissionError:
                logger.error ("Cannot create %s directory.",
                              config.profile_images_storage)
                config.profile_images_storage = os.path.join (config.storage, "profile-images")
                logger.error ("Falling back to %s.", config.profile_images_storage)

        if config.thumbnail_storage is not None and not inside_reload:
            try:
                os.makedirs (config.thumbnail_storage, mode=0o700, exist_ok=True)
            except PermissionError:
                logger.error ("Cannot create %s directory.", config.thumbnail_storage)

        if not server.add_static_root ("/thumbnails", config.thumbnail_storage):
            logger.error ("Failed to setup route for thumbnails.")

        if config.iiif_cache_storage is not None and not inside_reload:
            try:
                os.makedirs (config.iiif_cache_storage, mode=0o700, exist_ok=True)
            except PermissionError:
                logger.error ("Cannot create %s directory.", config.iiif_cache_storage)

        server.db.setup_sparql_endpoint ()

        if apply_transactions is not None:
            return apply_transactions_from_directory (logger, server, apply_transactions)

        if perform_export:
            return perform_rdf_export (logger, server, full_rdf_export)

        if not run_internal_server:
            config.using_uwsgi = True
            return server

        if inside_reload:
            logger.info ("Reloaded.")
        else:
            if not config.menu:
                logger.warning ("No menu structure provided.")

            if shutil.which ("git") is None:
                logger.error ("Cannot find the 'git' executable.  Please install it.")
                if config.in_production:
                    raise DependencyNotAvailable

            if config.orcid_client_id is not None and config.orcid_read_public_token is None:
                if server.obtain_orcid_read_public_token ():
                    logger.info ("Obtained read-public token from ORCID.")

            if config.depositing_domains:
                logger.info ("Depositing is limited to the domains: %s.", config.depositing_domains)

            logger.info ("SPARQL endpoint:         %s", config.endpoint)
            if config.endpoint != config.update_endpoint:
                logger.info ("SPARQL update_endpoint:  %s", config.update_endpoint)
            logger.info ("State graph:             %s", config.state_graph)
            logger.info ("Storage path:            %s", config.storage)
            if config.storage_locations:
                for location in config.storage_locations:
                    logger.info ("Storage path:            %s", location["path"])
            logger.info ("Secondary storage path:  %s", config.secondary_storage)
            logger.info ("Cache storage path:      %s", server.db.cache.storage)
            logger.info ("Static pages loaded:     %s", len(server.static_pages))
            if config.handle_url is None:
                logger.info ("Handle registration is disabled.")
            else:
                logger.info ("Handle prefix:           %s", config.handle_prefix)

            if config.enable_iiif:
                if not PYVIPS_DEPENDENCY_LOADED:
                    logger.error ("Dependency 'pyvips' is required for IIIF.")
                    if PYVIPS_ERROR_MESSAGE is not None:
                        logging.error ("Loading 'pyvips' failed with:\n---\n%s\n---",
                                       PYVIPS_ERROR_MESSAGE)
                    raise DependencyNotAvailable
                logging.getLogger('pyvips').setLevel(logging.ERROR)

            if config.identity_provider is not None:
                logger.info ("Using %s as identity provider.",
                             config.identity_provider.upper())
            else:
                logger.error ("Missing identity provider configuration.")
                if config.in_production:
                    raise MissingConfigurationError

            if not server.email.is_properly_configured ():
                logger.warning ("Sending notification e-mails has been disabled.")
                logger.warning ("Please configure a mail server to enable it.")
                if config.in_production:
                    logger.error ("An e-mail server must be configured for production-mode.")
                    raise MissingConfigurationError

            if config.in_production and not server.db.feedback_reviewer_email_addresses():
                logger.error ("An account with 'may-process-feedback' privileges must be configured.")
                raise MissingConfigurationError

            for email_address in config.privileges:  # pylint: disable=consider-using-dict-items
                if config.privileges[email_address.lower()]["needs_2fa"]:
                    logger.info ("Enabled 2FA for %s.", email_address)

            if initialize:
                if not server.db.state_graph_is_initialized ():
                    if not server.db.sparql_is_up:
                        logger.error ("Cannot initialize because the SPARQL endpoint is down.")
                        return None

                    logger.info ("Invalidating caches ...")
                    server.db.cache.invalidate_all ()
                    logger.info ("Initializing RDF store ...")
                    rdf_store = backup_database.DatabaseInterface()

                    if not rdf_store.insert_static_triplets ():
                        logger.error ("Failed to gather static triplets")

                    if server.db.add_triples_from_graph (rdf_store.store):
                        logger.info ("Initialization completed.")

                    server.db.initialize_privileged_accounts ()
                    server.db.mark_state_graph_as_initialized ()
                    initialize = False
                else:
                    logger.warning (("Skipping initialization of the database "
                                     "because it has been initialized before."))
                    logger.warning ("Empty the state-graph to re-initialize.")

        if not inside_reload:
            refresh_group_configuration (server, logger, config_files)

            # The 'run_simple' procedure below doesn't allow to catch an
            # address-already-in-use error, so we have to test beforehand to
            # figure out if we need to use the fallback port instead.
            try:
                bind_test = socket.socket (socket.AF_INET, socket.SOCK_STREAM)
                bind_test.bind ((config.address, config.port))
                bind_test.close()
            except OSError as error:
                if config.alternative_port is not None:
                    logger.info ("Falling back to port %s.", config.alternative_port)
                    config.port = config.alternative_port
                else:
                    logger.info ("Unable to bind to port %s: %s.", config.port, error)

        run_simple (config.address, config.port, server,
                    threaded=(config.maximum_workers <= 1),
                    processes=config.maximum_workers,
                    extra_files=list(config_files),
                    use_debugger=config.use_debugger,
                    use_reloader=config.use_reloader)

    except (FileNotFoundError, DependencyNotAvailable, MissingConfigurationError):
        pass

    return None

## ----------------------------------------------------------------------------
## Starting point for uWSGI
## ----------------------------------------------------------------------------

def application (env, start_response):
    """The main entry point for the WSGI."""

    logging.basicConfig(format='[%(levelname)s] %(asctime)s - %(name)s: %(message)s',
                        level=logging.INFO)

    ## Suppress start-up info messages.
    logging.getLogger("uwsgi:djehuty.web.ui").setLevel(logging.WARNING)

    if not UWSGI_DEPENDENCY_LOADED:
        start_response('500 Internal Server Error', [('Content-Type','text/html')])
        return [b"<p>Cannot find the <code>uwsgi</code> Python module.</p>"]

    config_file = os.getenv ("DJEHUTY_CONFIG_FILE")

    if config_file is None:
        start_response('200 OK', [('Content-Type','text/html')])
        return [b"<p>Please set the <code>DJEHUTY_CONFIG_FILE</code> environment variable.</p>"]

    server = main (config_file=config_file, run_internal_server=False)
    return server (env, start_response)
