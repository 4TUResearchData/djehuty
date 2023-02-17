"""This module implements the API server."""

from datetime import date
from threading import Lock
import os.path
import os
import logging
import json
import hashlib
import subprocess
import secrets
import re
import base64
import requests
import pygit2
import zipfly
from werkzeug.utils import redirect, send_file
from werkzeug.wrappers import Request, Response
from werkzeug.routing import Map, Rule
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.exceptions import HTTPException, NotFound, BadRequest
from rdflib import URIRef
from jinja2 import Environment, FileSystemLoader
from jinja2.exceptions import TemplateNotFound
from djehuty.web import validator
from djehuty.web import formatter
from djehuty.web import xml_formatter
from djehuty.web import database
from djehuty.web import email_handler
from djehuty.utils.convenience import pretty_print_size, decimal_coords
from djehuty.utils.convenience import value_or, value_or_none, deduplicate_list
from djehuty.utils.convenience import self_or_value_or_none, parses_to_int
from djehuty.utils.convenience import make_citation, is_opendap_url, landing_page_url
from djehuty.utils.constants import group_to_member, member_url_names
from djehuty.utils.rdf import uuid_to_uri, uri_to_uuid, uris_from_records

## Error handling for loading python3-saml is done in 'ui'.
## So if it fails here, we can safely assume we don't need it.
try:
    from onelogin.saml2.auth import OneLogin_Saml2_Auth
    from onelogin.saml2.errors import OneLogin_Saml2_Error
except (ImportError, ModuleNotFoundError):
    pass

try:
    import uwsgi
except ModuleNotFoundError:
    pass

class ApiServer:
    """This class implements the API server."""

    ## INITIALISATION
    ## ------------------------------------------------------------------------

    def __init__ (self, address="127.0.0.1", port=8080):
        self.base_url         = f"http://{address}:{port}"
        self.db               = database.SparqlInterface()
        self.email            = email_handler.EmailInterface()
        self.cookie_key       = "djehuty_session"
        self.impersonator_cookie_key = f"impersonator_{self.cookie_key}"
        self.file_list_lock  = Lock()
        self.in_production    = False
        self.in_preproduction = False
        self.using_uwsgi      = False
        self.maintenance_mode = False

        self.orcid_client_id     = None
        self.orcid_client_secret = None
        self.orcid_endpoint      = None
        self.identity_provider   = None

        self.saml_config_path    = None
        self.saml_config         = None

        self.datacite_url        = None
        self.datacite_id         = None
        self.datacite_password   = None
        self.datacite_prefix     = None
        self.log_access          = self.log_access_directly

        self.menu = []
        self.static_pages = {}

        ## Routes to all API calls.
        ## --------------------------------------------------------------------

        self.url_map = Map([
            ## ----------------------------------------------------------------
            ## UI
            ## ----------------------------------------------------------------
            Rule("/",                                         endpoint = "ui_home"),
            Rule("/login",                                    endpoint = "ui_login"),
            Rule("/account/home",                             endpoint = "ui_account_home"),
            Rule("/logout",                                   endpoint = "ui_logout"),
            Rule("/my/dashboard",                             endpoint = "ui_dashboard"),
            Rule("/my/datasets",                              endpoint = "ui_my_data"),
            Rule("/my/datasets/<dataset_id>/edit",            endpoint = "ui_edit_dataset"),
            Rule("/my/datasets/<dataset_id>/delete",          endpoint = "ui_delete_dataset"),
            Rule("/my/datasets/<dataset_id>/private_links",   endpoint = "ui_dataset_private_links"),
            Rule("/my/datasets/<dataset_id>/private_link/<private_link_id>/delete", endpoint = "ui_dataset_delete_private_link"),
            Rule("/my/datasets/<dataset_id>/private_link/new", endpoint = "ui_dataset_new_private_link"),
            Rule("/my/datasets/new",                          endpoint = "ui_new_dataset"),
            Rule("/my/datasets/<dataset_id>/new-version-draft", endpoint = "ui_new_version_draft_dataset"),
            Rule("/my/datasets/submitted-for-review",         endpoint = "ui_dataset_submitted"),
            Rule("/my/collections",                           endpoint = "ui_my_collections"),
            Rule("/my/collections/<collection_id>/edit",      endpoint = "ui_edit_collection"),
            Rule("/my/collections/<collection_id>/delete",    endpoint = "ui_delete_collection"),
            Rule("/my/collections/<collection_id>/private_links", endpoint = "ui_collection_private_links"),
            Rule("/my/collections/<collection_id>/private_link/<private_link_id>/delete", endpoint = "ui_collection_delete_private_link"),
            Rule("/my/collections/<collection_id>/private_link/new", endpoint = "ui_collection_new_private_link"),
            Rule("/my/collections/new",                       endpoint = "ui_new_collection"),
            Rule("/my/collections/<collection_id>/new-version-draft", endpoint = "ui_new_version_draft_collection"),
            Rule("/my/sessions/<session_uuid>/edit",          endpoint = "ui_edit_session"),
            Rule("/my/sessions/<session_uuid>/delete",        endpoint = "ui_delete_session"),
            Rule("/my/sessions/<session_uuid>/activate",      endpoint = "ui_activate_session"),
            Rule("/my/sessions/new",                          endpoint = "ui_new_session"),
            Rule("/my/profile",                               endpoint = "ui_profile"),
            Rule("/review/dashboard",                         endpoint = "ui_review_dashboard"),
            Rule("/review/overview",                          endpoint = "ui_review_overview"),
            Rule("/review/goto-dataset/<dataset_id>",         endpoint = "ui_review_impersonate_to_dataset"),
            Rule("/review/assign-to-me/<dataset_id>",         endpoint = "ui_review_assign_to_me"),
            Rule("/review/unassign/<dataset_id>",             endpoint = "ui_review_unassign"),
            Rule("/review/published/<dataset_id>",            endpoint = "ui_review_published"),
            Rule("/admin/dashboard",                          endpoint = "ui_admin_dashboard"),
            Rule("/admin/users",                              endpoint = "ui_admin_users"),
            Rule("/admin/exploratory",                        endpoint = "ui_admin_exploratory"),
            Rule("/admin/impersonate/<account_uuid>",         endpoint = "ui_admin_impersonate"),
            Rule("/admin/maintenance",                        endpoint = "ui_admin_maintenance"),
            Rule("/admin/maintenance/clear-cache",            endpoint = "ui_admin_clear_cache"),
            Rule("/admin/maintenance/clear-sessions",         endpoint = "ui_admin_clear_sessions"),
            Rule("/portal",                                   endpoint = "ui_portal"),
            Rule("/categories/<category_id>",                 endpoint = "ui_categories"),
            Rule("/category",                                 endpoint = "ui_category"),
            Rule("/institutions/<institution_name>",          endpoint = "ui_institution"),
            Rule("/opendap_to_doi",                           endpoint = "ui_opendap_to_doi"),
            Rule("/datasets/<dataset_id>",                    endpoint = "ui_dataset"),
            Rule("/datasets/<dataset_id>/<version>",          endpoint = "ui_dataset"),
            Rule("/private_datasets/<private_link_id>",       endpoint = "ui_private_dataset"),
            Rule("/private_collections/<private_link_id>",    endpoint = "ui_private_collection"),
            Rule("/file/<dataset_id>/<file_id>",              endpoint = "ui_download_file"),
            Rule("/collections/<collection_id>",              endpoint = "ui_collection"),
            Rule("/collections/<collection_id>/<version>",    endpoint = "ui_collection"),
            Rule("/my/collections/published/<collection_id>", endpoint = "ui_collection_published"),
            Rule("/authors/<author_id>",                      endpoint = "ui_author"),
            Rule("/search",                                   endpoint = "ui_search"),
            Rule("/ndownloader/items/<dataset_id>/versions/<version>", endpoint = "ui_download_all_files"),
            Rule("/data_access_request",                      endpoint = "ui_data_access_request"),

            ## ----------------------------------------------------------------
            ## COMPATIBILITY
            ## ----------------------------------------------------------------
            Rule("/articles/dataset/<slug>/<dataset_id>",     endpoint = "ui_compat_dataset"),
            Rule("/articles/dataset/<slug>/<dataset_id>/<version>", endpoint = "ui_compat_dataset"),
            Rule("/collections/<slug>/<collection_id>",       endpoint = "ui_compat_collection"),
            Rule("/collections/<slug>/<collection_id>/<version>", endpoint = "ui_compat_collection"),

            ## ----------------------------------------------------------------
            ## V2 API
            ## ----------------------------------------------------------------
            Rule("/v2/account/applications/authorize",        endpoint = "api_authorize"),
            Rule("/v2/token",                                 endpoint = "api_token"),
            Rule("/v2/collections",                           endpoint = "api_collections"),

            ## Private institutions
            ## ----------------------------------------------------------------
            Rule("/v2/account/institution",                   endpoint = "api_private_institution"),
            Rule("/v2/account/institution/users/<account_uuid>",endpoint = "api_private_institution_account"),
            Rule("/v2/account/institution/accounts",          endpoint = "api_private_institution_accounts"),

            ## Public articles
            ## ----------------------------------------------------------------
            Rule("/v2/articles",                              endpoint = "api_datasets"),
            Rule("/v2/articles/search",                       endpoint = "api_datasets_search"),
            Rule("/v2/articles/<dataset_id>",                 endpoint = "api_dataset_details"),
            Rule("/v2/articles/<dataset_id>/versions",        endpoint = "api_dataset_versions"),
            Rule("/v2/articles/<dataset_id>/versions/<version>", endpoint = "api_dataset_version_details"),
            Rule("/v2/articles/<dataset_id>/versions/<version>/embargo", endpoint = "api_dataset_version_embargo"),
            Rule("/v2/articles/<dataset_id>/versions/<version>/confidentiality", endpoint = "api_dataset_version_confidentiality"),
            Rule("/v2/articles/<dataset_id>/versions/<version>/update_thumb", endpoint = "api_dataset_version_update_thumb"),
            Rule("/v2/articles/<dataset_id>/files",           endpoint = "api_dataset_files"),
            Rule("/v2/articles/<dataset_id>/files/<file_id>", endpoint = "api_dataset_file_details"),

            ## Private articles
            ## ----------------------------------------------------------------
            Rule("/v2/account/articles",                      endpoint = "api_private_datasets"),
            Rule("/v2/account/articles/search",               endpoint = "api_private_datasets_search"),
            Rule("/v2/account/articles/<dataset_id>",         endpoint = "api_private_dataset_details"),
            Rule("/v2/account/articles/<dataset_id>/authors", endpoint = "api_private_dataset_authors"),
            Rule("/v2/account/articles/<dataset_id>/authors/<author_id>", endpoint = "api_private_dataset_author_delete"),
            Rule("/v2/account/articles/<dataset_id>/funding", endpoint = "api_private_dataset_funding"),
            Rule("/v2/account/articles/<dataset_id>/funding/<funding_id>", endpoint = "api_private_dataset_funding_delete"),
            Rule("/v2/account/articles/<dataset_id>/categories", endpoint = "api_private_dataset_categories"),
            Rule("/v2/account/articles/<dataset_id>/categories/<category_id>", endpoint = "api_private_delete_dataset_category"),
            Rule("/v2/account/articles/<dataset_id>/embargo", endpoint = "api_private_dataset_embargo"),
            Rule("/v2/account/articles/<dataset_id>/files",   endpoint = "api_private_dataset_files"),
            Rule("/v2/account/articles/<dataset_id>/files/<file_id>", endpoint = "api_private_dataset_file_details"),
            Rule("/v2/account/articles/<dataset_id>/private_links", endpoint = "api_private_dataset_private_links"),
            Rule("/v2/account/articles/<dataset_id>/private_links/<link_id>", endpoint = "api_private_dataset_private_links_details"),
            Rule("/v2/account/articles/<dataset_id>/reserve_doi", endpoint = "api_private_dataset_reserve_doi"),

            ## Public collections
            ## ----------------------------------------------------------------
            Rule("/v2/collections",                           endpoint = "api_collections"),
            Rule("/v2/collections/search",                    endpoint = "api_collections_search"),
            Rule("/v2/collections/<collection_id>",           endpoint = "api_collection_details"),
            Rule("/v2/collections/<collection_id>/versions",  endpoint = "api_collection_versions"),
            Rule("/v2/collections/<collection_id>/versions/<version>", endpoint = "api_collection_version_details"),
            Rule("/v2/collections/<collection_id>/articles",  endpoint = "api_collection_datasets"),

            ## Private collections
            ## ----------------------------------------------------------------
            Rule("/v2/account/collections",                   endpoint = "api_private_collections"),
            Rule("/v2/account/collections/search",            endpoint = "api_private_collections_search"),
            Rule("/v2/account/collections/<collection_id>",   endpoint = "api_private_collection_details"),
            Rule("/v2/account/collections/<collection_id>/authors", endpoint = "api_private_collection_authors"),
            Rule("/v2/account/collections/<collection_id>/authors/<author_id>", endpoint = "api_private_collection_author_delete"),
            Rule("/v2/account/collections/<collection_id>/categories", endpoint = "api_private_collection_categories"),
            Rule("/v2/account/collections/<collection_id>/articles", endpoint = "api_private_collection_datasets"),
            Rule("/v2/account/collections/<collection_id>/articles/<dataset_id>", endpoint = "api_private_collection_dataset_delete"),
            Rule("/v2/account/collections/<collection_id>/reserve_doi", endpoint = "api_private_collection_reserve_doi"),
            Rule("/v2/account/collections/<collection_id>/funding", endpoint = "api_private_collection_funding"),
            Rule("/v2/account/collections/<collection_id>/funding/<funding_id>", endpoint = "api_private_collection_funding_delete"),

            ## Private authors
            Rule("/v2/account/authors/search",                endpoint = "api_private_authors_search"),
            Rule("/v2/account/authors/<author_id>",           endpoint = "api_private_author_details"),

            ## Other
            ## ----------------------------------------------------------------
            Rule("/v2/account/funding/search",                endpoint = "api_private_funding_search"),
            Rule("/v2/licenses",                              endpoint = "api_licenses"),

            ## ----------------------------------------------------------------
            ## V3 API
            ## ----------------------------------------------------------------
            Rule("/v3/datasets",                              endpoint = "api_v3_datasets"),
            Rule("/v3/datasets/top/<item_type>",              endpoint = "api_v3_datasets_top"),
            Rule("/v3/datasets/<dataset_id>/submit-for-review", endpoint = "api_v3_dataset_submit"),
            Rule("/v3/datasets/<dataset_id>/publish",         endpoint = "api_v3_dataset_publish"),
            Rule("/v3/collections/<collection_id>/publish",   endpoint = "api_v3_collection_publish"),
            Rule("/v3/datasets/timeline/<item_type>",         endpoint = "api_v3_datasets_timeline"),
            Rule("/v3/datasets/<dataset_id>/upload",          endpoint = "api_v3_dataset_upload_file"),
            Rule("/v3/datasets/<dataset_id>.git/files",       endpoint = "api_v3_dataset_git_files"),
            Rule("/v3/file/<file_id>",                        endpoint = "api_v3_file"),
            Rule("/v3/datasets/<dataset_id>/references",      endpoint = "api_v3_dataset_references"),
            Rule("/v3/collections/<collection_id>/references", endpoint = "api_v3_collection_references"),
            Rule("/v3/datasets/<dataset_id>/tags",            endpoint = "api_v3_dataset_tags"),
            Rule("/v3/collections/<collection_id>/tags",      endpoint = "api_v3_collection_tags"),
            Rule("/v3/groups",                                endpoint = "api_v3_groups"),
            Rule("/v3/profile",                               endpoint = "api_v3_profile"),
            Rule("/v3/profile/categories",                    endpoint = "api_v3_profile_categories"),
            Rule("/v3/profile/quota-request",                 endpoint = "api_v3_profile_quota_request"),

            # Data model exploratory
            Rule("/v3/explore/types",                         endpoint = "api_v3_explore_types"),
            Rule("/v3/explore/properties",                    endpoint = "api_v3_explore_properties"),
            Rule("/v3/explore/property_value_types",          endpoint = "api_v3_explore_property_types"),

            # Reviewer
            Rule("/v3/datasets/<dataset_uuid>/assign-reviewer/<reviewer_uuid>", endpoint = "api_v3_datasets_assign_reviewer"),

            ## ----------------------------------------------------------------
            ## GIT HTTP API
            ## ----------------------------------------------------------------
            Rule("/v3/datasets/<git_uuid>.git/info/refs",   endpoint = "api_v3_private_dataset_git_refs"),
            Rule("/v3/datasets/<git_uuid>.git/git-upload-pack", endpoint = "api_v3_private_dataset_git_upload_or_receive_pack"),
            Rule("/v3/datasets/<git_uuid>.git/git-receive-pack", endpoint = "api_v3_private_dataset_git_upload_or_receive_pack"),

            ## ----------------------------------------------------------------
            ## SAML 2.0
            ## ----------------------------------------------------------------
            Rule("/saml/metadata",                            endpoint = "saml_metadata"),
            Rule("/saml/login",                               endpoint = "ui_login"),

            ## ----------------------------------------------------------------
            ## EXPORT
            ## ----------------------------------------------------------------
            Rule("/export/datacite/datasets/<dataset_id>",                 endpoint = "ui_export_datacite_dataset"),
            Rule("/export/datacite/datasets/<dataset_id>/<version>",       endpoint = "ui_export_datacite_dataset"),
            Rule("/export/datacite/collections/<collection_id>",           endpoint = "ui_export_datacite_collection"),
            Rule("/export/datacite/collections/<collection_id>/<version>", endpoint = "ui_export_datacite_collection"),
            Rule("/export/refworks/datasets/<dataset_id>",                 endpoint = "ui_export_refworks_dataset"),
            Rule("/export/refworks/datasets/<dataset_id>/<version>",       endpoint = "ui_export_refworks_dataset"),
            Rule("/export/bibtex/datasets/<dataset_id>",                   endpoint = "ui_export_bibtex_dataset"),
            Rule("/export/bibtex/datasets/<dataset_id>/<version>",         endpoint = "ui_export_bibtex_dataset"),
            Rule("/export/refman/datasets/<dataset_id>",                   endpoint = "ui_export_refman_dataset"),
            Rule("/export/refman/datasets/<dataset_id>/<version>",         endpoint = "ui_export_refman_dataset"),
            Rule("/export/endnote/datasets/<dataset_id>",                  endpoint = "ui_export_endnote_dataset"),
            Rule("/export/endnote/datasets/<dataset_id>/<version>",        endpoint = "ui_export_endnote_dataset"),
            Rule("/export/nlm/datasets/<dataset_id>",                      endpoint = "ui_export_nlm_dataset"),
            Rule("/export/nlm/datasets/<dataset_id>/<version>",            endpoint = "ui_export_nlm_dataset"),
            Rule("/export/dc/datasets/<dataset_id>",                       endpoint = "ui_export_dc_dataset"),
            Rule("/export/dc/datasets/<dataset_id>/<version>",             endpoint = "ui_export_dc_dataset"),
            Rule("/export/cff/datasets/<dataset_id>",                      endpoint = "ui_export_cff_dataset"),
            Rule("/export/cff/datasets/<dataset_id>/<version>",            endpoint = "ui_export_cff_dataset"),

           ])

        ## Static resources and HTML templates.
        ## --------------------------------------------------------------------

        resources_path = os.path.dirname(__file__)
        self.static_roots = {
            "/robots.txt": os.path.join(resources_path, "resources/robots.txt"),
            "/static":     os.path.join(resources_path, "resources/static")
        }
        self.jinja   = Environment(loader = FileSystemLoader(
            [
                # For internal templates.
                os.path.join(resources_path, "resources", "html_templates"),
                # For static pages.
                "/"
            ]), autoescape = True)

        self.metadata_jinja = Environment(loader = FileSystemLoader([
            os.path.join(resources_path, "resources", "metadata_templates"),
        ]), autoescape = True)

        self.wsgi    = SharedDataMiddleware(self.__respond, self.static_roots)

        ## Disable werkzeug logging.
        ## --------------------------------------------------------------------
        werkzeug_logger = logging.getLogger('werkzeug')
        werkzeug_logger.setLevel(logging.ERROR)

    ## WSGI AND WERKZEUG SETUP.
    ## ------------------------------------------------------------------------

    def add_static_root (self, uri, path):
        """Procedure to register a filesystem root for static files."""
        if uri is not None and path is not None:
            self.static_roots = { **self.static_roots, **{ uri: path } }
            self.wsgi = SharedDataMiddleware(self.__respond, self.static_roots)

            return True

        return False

    def __call__ (self, environ, start_response):
        return self.wsgi (environ, start_response)

    def __impersonator_token (self, request):
        return self.token_from_cookie (request, self.impersonator_cookie_key)

    def __impersonating_account (self, request):
        admin_token = self.token_from_cookie (request, self.impersonator_cookie_key)
        if admin_token:
            user_token = self.token_from_cookie (request)
            account = self.db.account_by_session_token (user_token)
            return account

        return None

    def __render_template (self, request, template_name, **context):
        template      = self.jinja.get_template (template_name)
        token         = self.token_from_cookie (request)
        impersonator_token = self.__impersonator_token (request)
        parameters    = {
            "base_url":        self.base_url,
            "path":            request.path,
            "in_production":   self.in_production,
            "maintenance_mode": self.maintenance_mode,
            "identity_provider": self.identity_provider,
            "orcid_client_id": self.orcid_client_id,
            "orcid_endpoint":  self.orcid_endpoint,
            "session_token":   self.token_from_request (request),
            "is_logged_in":    self.db.is_logged_in (token),
            "is_reviewing":    self.db.may_review (impersonator_token),
            "may_review":      self.db.may_review (token),
            "may_administer":  self.db.may_administer (token),
            "may_impersonate":  self.db.may_impersonate (token),
            "impersonating_account": self.__impersonating_account (request),
            "menu":            self.menu,
        }
        return self.response (template.render({ **context, **parameters }),
                              mimetype='text/html; charset=utf-8')

    def __render_email_templates (self, template_name, **context):
        """Render a plaintext and an HTML body for sending in an e-mail."""

        html_template = self.jinja.get_template (f"{template_name}.html")
        text_template = self.jinja.get_template (f"{template_name}.txt")

        parameters    = { "base_url": self.base_url }

        html_response = html_template.render({ **context, **parameters })
        text_response = text_template.render({ **context, **parameters })

        return text_response, html_response

    def __render_export_format (self, mimetype, template_name, **context):
        template      = self.metadata_jinja.get_template (template_name)
        return self.response (template.render( **context ),
                              mimetype=mimetype)

    def __dispatch_request (self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            self.log_access (request)
            if self.maintenance_mode:
                return self.ui_maintenance (request)
            endpoint, values = adapter.match() #  pylint: disable=unpacking-non-sequence
            return getattr(self, endpoint)(request, **values)
        except NotFound:
            if request.path in self.static_pages:
                page = self.static_pages[request.path]
                if "filesystem-path" in page:
                    # Handle static pages.
                    try:
                        logging.debug("Attempting to render static page.")
                        return self.__render_template(request, page["filesystem-path"])
                    except TemplateNotFound:
                        logging.error("Couldn't find template '%s'.", page["filesystem-path"])
                elif "redirect-to" in page:
                    # Handle redirect
                    logging.debug("Attempting to redirect.")
                    return redirect(location=page["redirect-to"], code=page["code"])
                else:
                    logging.debug("Static page nor redirect found in entry.")
            else:
                logging.debug ("No static page entry for '%s'.", request.path)

            return self.error_404 (request)
        except BadRequest as error:
            logging.error("Received bad request: %s", error)
            return self.error_400 (request, error.description, 400)
        except HTTPException as error:
            logging.error("Unknown error in dispatch_request: %s", error)
            return error

    def __respond (self, environ, start_response):
        request  = Request(environ)
        response = self.__dispatch_request(request)
        return response(environ, start_response)

    def __send_templated_email (self, email_addresses, subject, template_name, **context):
        """Procedure to send an email according to a template to the list of EMAIL_ADDRESSES."""

        if not self.email.is_properly_configured ():
            return False

        if not email_addresses:
            return False

        for email_address in email_addresses:
            text, html = self.__render_email_templates (f"email/{template_name}",
                                                        recipient_email=email_address,
                                                        **context)
            self.email.send_email (email_address, subject, text, html)

        logging.info ("Sent e-mail to %d address(es): %s", len(email_addresses), subject)
        return True

    def __send_email_to_reviewers (self, subject, template_name, **context):
        """Procedure to send an email to all accounts configured with 'may_review' privileges."""
        addresses = self.db.reviewer_email_addresses()
        return self.__send_templated_email (addresses, subject, template_name, **context)

    def __send_email_to_quota_reviewers (self, subject, template_name, **context):
        """Procedure to send an email to all accounts configured with 'may_review' privileges."""
        addresses = self.db.quota_reviewer_email_addresses()
        return self.__send_templated_email (addresses, subject, template_name, **context)

    def token_from_cookie (self, request, cookie_key=None):
        """Procedure to gather an access token from a HTTP cookie."""
        try:
            if cookie_key is None:
                cookie_key = self.cookie_key
            return request.cookies[cookie_key]
        except KeyError:
            return None

    ## ERROR HANDLERS
    ## ------------------------------------------------------------------------

    def error_400_list (self, request, errors):
        """Procedure to respond with HTTP 400 with a list of error messages."""
        response = None
        if self.accepts_html (request):
            response = self.__render_template (request, "400.html", message=errors)
        else:
            response = self.response (json.dumps(errors))
        response.status_code = 400
        return response

    def error_400 (self, request, message, code):
        """Procedure to respond with HTTP 400 with a single error message."""
        return self.error_400_list (request, {
            "message": message,
            "code":    code
        })

    def error_403 (self, request):
        """Procedure to respond with HTTP 403."""
        response = None
        if self.accepts_html (request):
            response = self.__render_template (request, "403.html")
        else:
            response = self.response (json.dumps({
                "message": "Not allowed."
            }))
        response.status_code = 403
        return response

    def error_404 (self, request):
        """Procedure to respond with HTTP 404."""
        response = None
        if self.accepts_html (request):
            response = self.__render_template (request, "404.html")
        else:
            response = self.response (json.dumps({
                "message": "This resource does not exist."
            }))
        response.status_code = 404
        return response

    def error_405 (self, allowed_methods):
        """Procedure to respond with HTTP 405."""
        response = self.response (f"Acceptable methods: {allowed_methods}",
                                  mimetype="text/plain")
        response.status_code = 405
        return response

    def error_415 (self, allowed_types):
        """Procedure to respond with HTTP 415."""
        response = self.response (f"Supported Content-Types: {allowed_types}",
                                  mimetype="text/plain")
        response.status_code = 415
        return response

    def error_406 (self, allowed_formats):
        """Procedure to respond with HTTP 406."""
        response = self.response (f"Acceptable formats: {allowed_formats}",
                                  mimetype="text/plain")
        response.status_code = 406
        return response

    def error_500 (self):
        """Procedure to respond with HTTP 500."""
        response = self.response ("")
        response.status_code = 500
        return response

    def error_authorization_failed (self, request):
        """Procedure to handle authorization failures."""
        if self.accepts_html (request):
            response = self.__render_template (request, "403.html")
        else:
            response = self.response (json.dumps({
                "message": "Invalid or unknown session token",
                "code":    "InvalidSessionToken"
            }))

        response.status_code = 403
        return response

    def default_error_handling (self, request, method, content_type):
        """Procedure to handle both method and content type mismatches."""
        if request.method != method:
            return self.error_405 (method)

        if not self.accepts_content_type (request, content_type, strict=False):
            return self.error_406 (content_type)

        return None

    def response (self, content, mimetype='application/json; charset=utf-8'):
        """Returns a self.response object with some tweaks."""

        output                   = Response(content, mimetype=mimetype)
        output.headers["Server"] = "4TU.ResearchData API"
        return output

    ## GENERAL HELPERS
    ## ----------------------------------------------------------------------------

    def __dataset_by_id_or_uri (self, identifier, account_uuid=None,
                                is_published=True, is_latest=False,
                                is_under_review=None, version = None):
        try:
            dataset = None
            if parses_to_int (identifier):
                dataset = self.db.datasets (dataset_id   = int(identifier),
                                            is_published = is_published,
                                            is_latest    = is_latest,
                                            is_under_review = is_under_review,
                                            version      = version,
                                            account_uuid = account_uuid,
                                            limit        = 1)[0]
            elif validator.is_valid_uuid (identifier):
                dataset = self.db.datasets (container_uuid = identifier,
                                            is_published   = is_published,
                                            is_latest      = is_latest,
                                            is_under_review = is_under_review,
                                            version        = version,
                                            account_uuid   = account_uuid,
                                            limit          = 1)[0]

            return dataset

        except IndexError:
            return None

    def __collection_by_id_or_uri (self, identifier, account_uuid=None,
                                   is_published=True, is_latest=False,
                                   version = None):
        try:
            collection = None
            if parses_to_int (identifier):
                collection = self.db.collections (collection_id = int(identifier),
                                                  is_published  = is_published,
                                                  is_latest     = is_latest,
                                                  version       = version,
                                                  account_uuid  = account_uuid,
                                                  limit         = 1)[0]
            elif validator.is_valid_uuid (identifier):
                collection = self.db.collections (container_uuid = identifier,
                                                  is_published   = is_published,
                                                  is_latest      = is_latest,
                                                  version        = version,
                                                  account_uuid   = account_uuid,
                                                  limit          = 1)[0]

            return collection

        except IndexError:
            return None

    def __files_by_id_or_uri (self, identifier=None,
                              account_uuid=None,
                              dataset_uri=None):
        try:
            file = None
            if parses_to_int (identifier):
                file = self.db.dataset_files (file_id     = int(identifier),
                                              dataset_uri = dataset_uri,
                                              account_uuid = account_uuid)
            elif (validator.is_valid_uuid (identifier) or
                  validator.is_valid_uuid (uri_to_uuid (dataset_uri))):
                file = self.db.dataset_files (file_uuid   = identifier,
                                              dataset_uri = dataset_uri,
                                              account_uuid = account_uuid)

            return file

        except IndexError:
            return None

    def __file_by_id_or_uri (self, identifier,
                             account_uuid=None,
                             dataset_uri=None):
        try:
            return self.__files_by_id_or_uri (identifier, account_uuid, dataset_uri)[0]
        except IndexError:
            return None

    def __default_dataset_api_parameters (self, request):

        record = {}
        record["order"]           = self.get_parameter (request, "order")
        record["order_direction"] = self.get_parameter (request, "order_direction")
        record["institution"]     = self.get_parameter (request, "institution")
        record["published_since"] = self.get_parameter (request, "published_since")
        record["modified_since"]  = self.get_parameter (request, "modified_since")
        record["group"]           = self.get_parameter (request, "group")
        record["resource_doi"]    = self.get_parameter (request, "resource_doi")
        record["item_type"]       = self.get_parameter (request, "item_type")
        record["doi"]             = self.get_parameter (request, "doi")
        record["handle"]          = self.get_parameter (request, "handle")
        record["search_for"]      = self.get_parameter (request, "search_for")

        offset, limit = validator.paging_to_offset_and_limit ({
                "page":      self.get_parameter (request, "page"),
                "page_size": self.get_parameter (request, "page_size"),
                "limit":     self.get_parameter (request, "limit"),
                "offset":    self.get_parameter (request, "offset")
            })

        record["offset"] = offset
        record["limit"]  = limit

        validator.string_value  (record, "order", 0, 32)
        validator.order_direction (record, "order_direction")
        validator.integer_value (record, "institution")
        validator.string_value  (record, "published_since", maximum_length=32)
        validator.string_value  (record, "modified_since",  maximum_length=32)
        validator.integer_value (record, "group")
        validator.string_value  (record, "resource_doi",    maximum_length=255)
        validator.integer_value (record, "item_type")
        validator.string_value  (record, "doi",             maximum_length=255)
        validator.string_value  (record, "handle",          maximum_length=255)
        validator.string_value  (record, "search_for",      maximum_length=1024)

        # Rewrite the group parameter to match the database's plural form.
        record["groups"]  = [record["group"]] if record["group"] is not None else None
        del record["group"]

        return record

    def __pretty_print_dates_for_item (self, item):
        date_types = (('submitted'   , 'timeline_submission'),
                      ('first online', 'timeline_first_online'),
                      ('published'   , 'published_date'),
                      ('posted'      , 'timeline_posted'),
                      ('revised'     , 'timeline_revision'))
        dates = {}
        for (label, dtype) in date_types:
            if dtype in item:
                date_value = value_or_none (item, dtype)
                if date_value:
                    date_value = date_value[:10]
                    if date_value not in dates:
                        dates[date_value] = []
                    dates[date_value].append(label)
        dates = [ (label, ', '.join(val)) for (label,val) in dates.items() ]
        return dates

    def __formatted_collection_record (self, collection):
        """Gathers a complete collection record and formats it."""
        try:
            uri = collection["uri"]
            datasets_count = self.db.collections_dataset_count (collection_uri = uri)
            fundings       = self.db.fundings (item_uri = uri, item_type="collection")
            categories     = self.db.categories (item_uri = uri)
            references     = self.db.references (item_uri = uri)
            custom_fields  = self.db.custom_fields (item_uri = uri, item_type="collection")
            tags           = self.db.tags (item_uri = uri)
            authors        = self.db.authors (item_uri = uri, item_type="collection")
            total          = formatter.format_collection_details_record (collection,
                                                                         fundings,
                                                                         categories,
                                                                         references,
                                                                         tags,
                                                                         authors,
                                                                         custom_fields,
                                                                         datasets_count)
            return total
        except IndexError:
            return None

    def __groups_for_account (self, account):
        """Gathers groups for an account record."""
        try:
            groups = None
            if "group_id" in account:
                groups = self.db.group (group_id = account["group_id"])
            else:
                # The parent_id was pre-determined by Figshare.
                groups = self.db.group (parent_id = 28585,
                                        order_direction = "asc",
                                        order = "id")

                for index, _ in enumerate(groups):
                    groups[index]["subgroups"] = self.db.group (
                        parent_id = groups[index]["id"],
                        order_direction = "asc",
                        order = "id")

            return groups
        except (KeyError, IndexError):
            return None

    def log_access_using_x_forwarded_for (self, request):
        """Log interactions using the X-Forwarded-For header."""
        try:
            logging.access ("%s requested %s.",  # pylint: disable=no-member
                            request.headers["X-Forwarded-For"],
                            request.full_path)
        except KeyError:
            logging.error("Missing X-Forwarded-For header.")

    def log_access_directly (self, request):
        """Log interactions using the 'remote_addr' property."""
        logging.access ("%s requested %s.",  # pylint: disable=no-member
                        request.remote_addr,
                        request.full_path)

    ## AUTHENTICATION HANDLERS
    ## ------------------------------------------------------------------------

    def authenticate_using_orcid (self, request):
        """Returns a record upon success, None upon failure."""

        record = { "code": self.get_parameter (request, "code") }
        try:
            url_parameters = {
                "client_id":     self.orcid_client_id,
                "client_secret": self.orcid_client_secret,
                "grant_type":    "authorization_code",
                "redirect_uri":  f"{self.base_url}/login",
                "code":          validator.string_value (record, "code", 0, 10, required=True)
            }
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            response = requests.post(f"{self.orcid_endpoint}/token",
                                     params  = url_parameters,
                                     headers = headers,
                                     timeout = 10)

            if response.status_code == 200:
                return response.json()

            logging.error("ORCID response was %d", response.status_code)
            return None

        except validator.ValidationException:
            logging.error("ORCID parameter validation error")
            return None

    def __request_to_saml_request (self, request):
        """Turns a werkzeug request into one that python3-saml understands."""

        return {
            ## Always assume HTTPS.  A proxy server may mask it.
            "https":       "on",
            ## Override the internal HTTP host because a proxy server masks the
            ## actual HTTP host used.  Fortunately, we pre-configure the
            ## expected HTTP host in the form of the "base_url".  So we strip
            ## off the protocol prefix.
            "http_host":   self.base_url.split("://")[1],
            "script_name": request.path,
            "get_data":    request.args.copy(),
            "post_data":   request.form.copy()
        }

    def __saml_auth (self, request):
        """Returns an instance of OneLogin_Saml2_Auth."""
        http_fields = self.__request_to_saml_request (request)
        return OneLogin_Saml2_Auth (http_fields, custom_base_path=self.saml_config_path)

    def authenticate_using_saml (self, request):
        """Returns a record upon success, None otherwise."""

        http_fields = self.__request_to_saml_request (request)
        saml_auth   = OneLogin_Saml2_Auth (http_fields, custom_base_path=self.saml_config_path)
        try:
            saml_auth.process_response ()
        except OneLogin_Saml2_Error as error:
            if error.code == OneLogin_Saml2_Error.SAML_RESPONSE_NOT_FOUND:
                logging.error ("Missing SAMLResponse in POST data.")
            else:
                logging.error ("SAML error %d occured.", error.code)
            return None

        errors = saml_auth.get_errors()
        if errors:
            logging.error("Errors in the SAML authentication:")
            logging.error("%s", ", ".join(errors))
            return None

        if not saml_auth.is_authenticated():
            logging.error("SAML authentication failed.")
            return None

        ## Gather SAML session information.
        session = {}
        session['samlNameId']                = saml_auth.get_nameid()
        session['samlNameIdFormat']          = saml_auth.get_nameid_format()
        session['samlNameIdNameQualifier']   = saml_auth.get_nameid_nq()
        session['samlNameIdSPNameQualifier'] = saml_auth.get_nameid_spnq()
        session['samlSessionIndex']          = saml_auth.get_session_index()

        ## Gather attributes from user.
        record               = {}
        attributes           = saml_auth.get_attributes()
        record["session"]    = session
        record["email"]      = attributes["urn:mace:dir:attribute-def:mail"][0]
        record["first_name"] = attributes["urn:mace:dir:attribute-def:givenName"][0]
        record["last_name"]  = attributes["urn:mace:dir:attribute-def:sn"][0]
        record["common_name"] = attributes["urn:mace:dir:attribute-def:cn"][0]

        if not record["email"]:
            logging.error("Didn't receive required fields in SAMLResponse.")
            return None

        return record

    def saml_metadata (self, request):
        """Communicates the service provider metadata for SAML 2.0."""

        if not self.accepts_xml (request):
            return self.error_406 ("text/xml")

        if self.identity_provider != "saml":
            return self.error_404 (request)

        saml_auth   = self.__saml_auth (request)
        settings    = saml_auth.get_settings ()
        metadata    = settings.get_sp_metadata ()
        errors      = settings.validate_metadata (metadata)
        if len(errors) == 0:
            return self.response (metadata, mimetype="text/xml")

        logging.error ("SAML SP Metadata validation failed.")
        logging.error ("Errors: %s", ", ".join(errors))
        return self.error_500 ()

    ## CONVENIENCE PROCEDURES
    ## ------------------------------------------------------------------------

    def accepts_content_type (self, request, content_type, strict=True):
        """Procedure to check whether the client accepts a content type."""
        try:
            acceptable = request.headers['Accept']
            if not acceptable:
                return False

            exact_match  = content_type in acceptable
            if strict:
                return exact_match

            global_match = "*/*" in acceptable
            return global_match or exact_match
        except KeyError:
            return False

    def accepts_html (self, request):
        """Procedure to check whether the client accepts HTML."""
        return self.accepts_content_type (request, "text/html")

    def accepts_xml (self, request):
        """Procedure to check whether the client accepts XML."""
        return (self.accepts_content_type (request, "application/xml") or
                self.accepts_content_type (request, "text/xml"))

    def accepts_json (self, request):
        """Procedure to check whether the client accepts JSON."""
        return self.accepts_content_type (request, "application/json", strict=False)

    def contains_json (self, request):
        """Procedure to check whether the client sent JSON data."""
        contains = request.headers['Content-Type']
        if not contains:
            return False

        return "application/json" in contains

    def get_parameter (self, request, parameter):
        """Procedure to get a parameter from either the content body or the URI string."""
        try:
            return request.form[parameter]
        except KeyError:
            return request.args.get(parameter)
        except AttributeError:
            return value_or_none (request, parameter)

    def token_from_request (self, request):
        """Procedure to get the access token from a HTTP request."""
        token_string = None

        ## Get the token from the "Authorization" HTTP header.
        ## If no such header is provided, we cannot authenticate.
        try:
            token_string = self.token_from_cookie (request)
            if token_string is None:
                token_string = request.environ["HTTP_AUTHORIZATION"]
        except KeyError:
            return None

        if token_string.startswith("token "):
            token_string = token_string[6:]

        return token_string

    def impersonated_account_uuid (self, request, account):
        """Procedure to get the account UUID in the case of impersonation."""
        try:
            if account["may_impersonate"]:
                ## Handle the "impersonate" URL parameter.
                impersonate = self.get_parameter (request, "impersonate")

                ## "impersonate" can also be passed in the request body.
                if impersonate is None:
                    content_type = value_or (request.headers, "Content-Type", "")
                    if "application/json" in content_type:
                        try:
                            body        = request.get_json()
                            impersonate = value_or_none (body, "impersonate")
                        except BadRequest:
                            impersonate = None

                if impersonate is not None:
                    impersonated_account = self.db.accounts (
                        id_lte=impersonate,
                        id_gte=impersonate)[0]
                    impersonate = impersonated_account["uuid"]
                    logging.access ("Account %s impersonating account %s.", #  pylint: disable=no-member
                                    account["uuid"], impersonate)
                    return impersonate

        except (KeyError, IndexError, TypeError):
            return account["uuid"]

        return account["uuid"]

    def account_uuid_from_request (self, request):
        """Procedure to the account UUID for a HTTP request."""
        uuid  = None
        token = self.token_from_request (request)

        ## Match the token to an account_uuid.  If the token does not
        ## exist, we cannot authenticate.
        try:
            account    = self.db.account_by_session_token (token)
            if account is not None:
                uuid = self.impersonated_account_uuid (request, account)
        except KeyError:
            logging.error("Attempt to authenticate with %s failed.", token)

        return uuid

    def __account_uuid_for_privilege (self, request, privilege_test):
        """
        Returns two values: the account_uuid and None on success, or
        the account_uuid and a response on failure.
        """

        error_response = None
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            error_response = self.error_authorization_failed(request)

        token = self.token_from_cookie (request)
        if not privilege_test (token):
            error_response = self.error_403 (request)

        return account_uuid, error_response

    def __depositor_account_uuid (self, request):
        return self.__account_uuid_for_privilege (request, self.db.is_depositor)

    def __reviewer_account_uuid (self, request):
        return self.__account_uuid_for_privilege (request, self.db.may_review)

    def default_list_response (self, records, format_function):
        """Procedure to respond a list of items."""
        output     = []
        try:
            output = list(map (format_function, records))
        except TypeError:
            logging.error("%s: A TypeError occurred.", format_function)

        return self.response (json.dumps(output))

    def respond_201 (self, body):
        """Procedure to respond with HTTP 201."""
        output = self.response (json.dumps(body))
        output.status_code = 201
        return output

    def respond_202 (self):
        """Procedure to respond with HTTP 202."""
        output = Response("", 202, {})
        output.headers["Server"] = "4TU.ResearchData API"
        return output

    def respond_204 (self):
        """Procedure to respond with HTTP 204."""
        output = Response("", 204, {})
        output.headers["Server"] = "4TU.ResearchData API"
        return output

    def respond_205 (self):
        """Procedure to respond with HTTP 205."""
        output = Response("", 205, {})
        output.headers["Server"] = "4TU.ResearchData API"
        return output

    ## API CALLS
    ## ------------------------------------------------------------------------

    def ui_home (self, request):
        """Implements /."""
        if self.accepts_html (request):
            return redirect ("/portal", code=301)

        return self.response (json.dumps({ "status": "OK" }))

    def ui_maintenance (self, request):
        """Implements a maintenance page."""
        if not self.maintenance_mode:
            self.error_404 (request)

        if self.accepts_html (request):
            return self.__render_template (request, "maintenance.html")

        return self.response (json.dumps({ "status": "maintenance" }))

    def ui_account_home (self, request):
        """Implements /account/home."""
        handler = self.default_error_handling (request, "GET", "text/html")
        if handler is not None:
            return handler

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is not None:
            return redirect ("/my/dashboard", code=302)

        if self.identity_provider == "saml":
            return redirect ("/login", code=302)

        if self.identity_provider == "orcid":
            return redirect ((f"{self.orcid_endpoint}/authorize?client_id="
                              f"{self.orcid_client_id}&response_type=code"
                              "&scope=/authenticate&redirect_uri="
                              f"{self.base_url}/login"), 302)

        return self.error_403 (request)

    def ui_login (self, request):
        """Implements /login."""

        account_uuid = None

        ## ORCID authentication
        ## --------------------------------------------------------------------
        if self.identity_provider == "orcid":
            orcid_record = self.authenticate_using_orcid (request)
            if orcid_record is None:
                return self.error_403 (request)

            if not self.accepts_html (request):
                return self.error_406 ("text/html")

            account_uuid = self.db.account_uuid_by_orcid (orcid_record['orcid'])
            if account_uuid is None:
                return self.error_403 (request)

            logging.access ("Account %s logged in via ORCID.", account_uuid) #  pylint: disable=no-member

        ## SAML 2.0 authentication
        ## --------------------------------------------------------------------
        elif self.identity_provider == "saml":

            ## Initiate the login procedure.
            if request.method == "GET":
                saml_auth   = self.__saml_auth (request)
                redirect_url = saml_auth.login()
                response    = redirect (redirect_url)

                return response

            ## Retrieve signed data from SURFConext via the user.
            if request.method == "POST":
                if not self.accepts_html (request):
                    return self.error_406 ("text/html")

                saml_record = self.authenticate_using_saml (request)
                if saml_record is None:
                    return self.error_403 (request)

                try:
                    if "email" not in saml_record:
                        return self.error_400 (request, "Invalid request", "MissingEmailProperty")

                    account = self.db.account_by_email (saml_record["email"])
                    account_uuid = None
                    if account:
                        account_uuid = account["uuid"]
                        logging.access ("Account %s logged in via SAML.", account_uuid) #  pylint: disable=no-member
                    else:
                        account_uuid = self.db.insert_account (
                            email      = saml_record["email"],
                            first_name = value_or_none (saml_record, "first_name"),
                            last_name  = value_or_none (saml_record, "last_name")
                        )
                        logging.access ("Account %s created via SAML.", account_uuid) #  pylint: disable=no-member

                except TypeError:
                    pass
        else:
            logging.error ("Unknown identity provider '%s'", self.identity_provider)
            return self.error_500()

        if account_uuid is not None:
            token, mfa_token, session_uuid = self.db.insert_session (account_uuid, name="Website login")
            logging.access ("Created session %s for account %s.", session_uuid, account_uuid) #  pylint: disable=no-member

            if mfa_token is None:
                return redirect ("/my/dashboard", code=302)

            ## Send e-mail
            account = self.db.account_by_uuid (account_uuid)
            self.__send_templated_email (
                [account["email"]],
                "Two-factor authentication log-in token",
                "2fa_token", token = mfa_token)

            response = redirect (f"/my/sessions/{session_uuid}/activate", code=302)
            response.set_cookie (key=self.cookie_key, value=token, secure=self.in_production)
            return response

        return self.error_500 ()

    def ui_logout (self, request):
        """Implements /logout."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        # When impersonating, find the admin's token,
        # and set it as the new session token.
        other_session_token = self.token_from_cookie (request, self.impersonator_cookie_key)
        redirect_to         = self.token_from_cookie (request, "redirect_to")
        if other_session_token:
            response = None
            if redirect_to:
                response = redirect (redirect_to, code=302)
            else:
                response = redirect ("/admin/users", code=302)

            self.db.delete_session (self.token_from_cookie (request))
            response.set_cookie (key    = self.cookie_key,
                                 value  = other_session_token,
                                 secure = self.in_production)
            response.delete_cookie (key = self.impersonator_cookie_key)
            response.delete_cookie (key = "redirect_to")
            return response

        response = redirect ("/", code=302)
        self.db.delete_session (self.token_from_cookie (request))
        response.delete_cookie (key=self.cookie_key)
        return response

    def ui_review_impersonate_to_dataset (self, request, dataset_id):
        """Implements /review/goto-dataset/<id>."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        token = self.token_from_cookie (request)
        if not self.db.may_impersonate (token):
            return self.error_403 (request)

        dataset = None
        try:
            dataset = self.db.datasets (dataset_uuid    = dataset_id,
                                        is_published    = False,
                                        is_under_review = True)[0]
        except (IndexError, TypeError):
            pass

        if dataset is None:
            return self.error_403 (request)

        # Add a secondary cookie to go back to at one point.
        response = redirect (f"/my/datasets/{dataset['container_uuid']}/edit", code=302)
        response.set_cookie (key    = self.impersonator_cookie_key,
                             value  = token,
                             secure = self.in_production)
        response.set_cookie (key    = "redirect_to",
                             value  = "/review/dashboard",
                             secure = self.in_production)

        # Create a new session for the user to be impersonated as.
        new_token, _, _ = self.db.insert_session (dataset["account_uuid"],
                                                  name="Reviewer",
                                                  is_impersonation=True)
        response.set_cookie (key    = self.cookie_key,
                             value  = new_token,
                             secure = self.in_production)
        return response

    def ui_admin_impersonate (self, request, account_uuid):
        """Implements /admin/impersonate/<id>."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        token = self.token_from_cookie (request)
        if not self.db.may_impersonate (token):
            return self.error_403 (request)

        # Add a secondary cookie to go back to at one point.
        response = redirect ("/my/dashboard", code=302)
        response.set_cookie (key    = self.impersonator_cookie_key,
                             value  = token,
                             secure = self.in_production)
        response.set_cookie (key    = "redirect_to",
                             value  = "/admin/users",
                             secure = self.in_production)

        # Create a new session for the user to be impersonated as.
        new_token, _, _ = self.db.insert_session (account_uuid,
                                                  name="Impersonation",
                                                  is_impersonation=True)
        response.set_cookie (key    = self.cookie_key,
                             value  = new_token,
                             secure = self.in_production)
        return response

    def ui_dashboard (self, request):
        """Implements /my/dashboard."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid, error_response = self.__depositor_account_uuid (request)
        if error_response is not None:
            return error_response

        account      = self.db.account_by_uuid (account_uuid)
        storage_used = self.db.account_storage_used (account_uuid)

        account_quota   = 0
        percentage_used = 0
        try:
            account_quota   = account["quota"]
            percentage_used = round(storage_used / account_quota * 100, 2)
        except (TypeError, KeyError):
            pass

        sessions     = self.db.sessions (account_uuid)
        return self.__render_template (
            request, "depositor/dashboard.html",
            storage_used = pretty_print_size (storage_used),
            quota        = pretty_print_size (account_quota),
            percentage_used = percentage_used,
            sessions     = sessions)

    def ui_my_data (self, request):
        """Implements /my/datasets."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid, error_response = self.__depositor_account_uuid (request)
        if error_response is not None:
            return error_response

        draft_datasets = self.db.datasets (account_uuid = account_uuid,
                                           limit        = 10000,
                                           is_published = False,
                                           is_under_review = False)

        for draft_dataset in draft_datasets:
            used = 0
            if not value_or (draft_dataset, "is_metadata_record", False):
                used = self.db.dataset_storage_used (draft_dataset["container_uri"])
            draft_dataset["storage_used"] = pretty_print_size (used)

        review_datasets = self.db.datasets (account_uuid    = account_uuid,
                                            limit           = 10000,
                                            is_published    = False,
                                            is_under_review = True)

        for review_dataset in review_datasets:
            used = 0
            if not value_or (review_dataset, "is_metadata_record", False):
                used = self.db.dataset_storage_used (review_dataset["container_uri"])
            review_dataset["storage_used"] = pretty_print_size (used)

        published_datasets = self.db.datasets (account_uuid = account_uuid,
                                               is_latest  = True,
                                               is_under_review = False,
                                               limit      = 10000)

        for published_dataset in published_datasets:
            used = 0
            if not value_or (published_dataset, "is_metadata_record", False):
                used = self.db.dataset_storage_used (published_dataset["container_uri"])
            published_dataset["storage_used"] = pretty_print_size (used)

        return self.__render_template (request, "depositor/my-data.html",
                                       draft_datasets     = draft_datasets,
                                       review_datasets    = review_datasets,
                                       published_datasets = published_datasets)

    def ui_collection_published (self, request, collection_id):
        """Implements /my/collections/published/<id>."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        _, error_response = self.__depositor_account_uuid (request)
        if error_response is not None:
            return error_response

        return self.__render_template (request, "depositor/published-collection.html",
                                       collection_id = collection_id)

    def ui_dataset_submitted (self, request):
        """Implements /my/datasets/submitted-for-review."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        _, error_response = self.__depositor_account_uuid (request)
        if error_response is not None:
            return error_response

        return self.__render_template (request, "depositor/submitted-for-review.html")

    def ui_new_dataset (self, request):
        """Implements /my/datasets/new."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid, error_response = self.__depositor_account_uuid (request)
        if error_response is not None:
            return error_response

        container_uuid, _ = self.db.insert_dataset(title = "Untitled item",
                                                   account_uuid = account_uuid)
        if container_uuid is not None:
            # Add oneself as author but don't bail if that doesn't work.
            try:
                account    = self.db.account_by_uuid (account_uuid)
                author_uri = URIRef(uuid_to_uri(account["author_uuid"], "author"))
                self.db.update_item_list (container_uuid, account_uuid,
                                          [author_uri], "authors")
            except (TypeError, KeyError):
                logging.warning ("No author record for account %s.", account_uuid)

            return redirect (f"/my/datasets/{container_uuid}/edit", code=302)

        return self.error_500()

    def ui_new_version_draft_dataset (self, request, dataset_id):
        """Implements /my/datasets/<id>/new-version-draft."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid, error_response = self.__depositor_account_uuid (request)
        if error_response is not None:
            return error_response

        dataset = self.__dataset_by_id_or_uri (dataset_id,
                                               is_published = True,
                                               account_uuid = account_uuid)

        if dataset is None:
            logging.error ("Unable to find dataset '%s'.", dataset_id)
            return self.error_403 (request)

        container_uuid = dataset["container_uuid"]
        draft_uuid = self.db.create_draft_from_published_dataset (container_uuid)
        if draft_uuid is None:
            logging.info("There is no draft dataset.")
            return self.error_500()

        return redirect (f"/my/datasets/{container_uuid}/edit", code=302)

    def ui_edit_dataset (self, request, dataset_id):
        """Implements /my/datasets/<id>/edit."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid, error_response = self.__depositor_account_uuid (request)
        if error_response is not None:
            return error_response

        try:
            dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                   is_published = False,
                                                   account_uuid = account_uuid)

            if dataset is None:
                return self.error_403 (request)

            categories = self.db.categories_tree ()
            account    = self.db.account_by_uuid (account_uuid)
            groups     = self.__groups_for_account (account)

            return self.__render_template (
                request,
                "depositor/edit-dataset.html",
                container_uuid = dataset["container_uuid"],
                article    = dataset,
                account    = account,
                categories = categories,
                groups     = groups)

        except IndexError:
            return self.error_403 (request)

    def ui_delete_dataset (self, request, dataset_id):
        """Implements /my/datasets/<id>/delete."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid, error_response = self.__depositor_account_uuid (request)
        if error_response is not None:
            return error_response

        try:
            dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                   account_uuid=account_uuid,
                                                   is_published=False)

            if dataset is None:
                return self.error_403 (request)

            container_uuid = dataset["container_uuid"]
            if self.db.delete_dataset_draft (container_uuid, account_uuid):
                return redirect ("/my/datasets", code=303)

            return self.error_404 (request)
        except (IndexError, KeyError):
            pass

        return self.error_500 ()

    def ui_dataset_private_links (self, request, dataset_id):
        """Implements /my/datasets/<id>/private_links."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed (request)

        if request.method == 'GET':
            dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                   account_uuid = account_uuid,
                                                   is_published = False)
            if not dataset:
                return self.error_404 (request)

            links = self.db.private_links (item_uri     = dataset["uri"],
                                           account_uuid = account_uuid)

            return self.__render_template (request,
                                           "depositor/dataset-private-links.html",
                                           dataset       = dataset,
                                           private_links = links)

        return self.error_500()

    def ui_collection_private_links (self, request, collection_id):
        """Implements /my/collections/<id>/private_links."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed (request)

        if request.method == 'GET':
            collection = self.__collection_by_id_or_uri (collection_id,
                                                         account_uuid = account_uuid,
                                                         is_published = False)
            if not collection:
                return self.error_404 (request)

            links = self.db.private_links (item_uri     = collection["uri"],
                                           account_uuid = account_uuid)

            return self.__render_template (request,
                                           "depositor/collection-private-links.html",
                                           collection    = collection,
                                           private_links = links)

        return self.error_500()

    def ui_my_collections (self, request):
        """Implements /my/collections."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid, error_response = self.__depositor_account_uuid (request)
        if error_response is not None:
            return error_response

        drafts = self.db.collections (account_uuid = account_uuid,
                                      is_published = False,
                                      limit        = 10000)

        for collection in drafts:
            count = self.db.collections_dataset_count(collection["uri"])
            collection["number_of_datasets"] = count

        published = self.db.collections (account_uuid = account_uuid,
                                         is_published = True,
                                         is_latest    = True,
                                         limit        = 10000)

        for collection in published:
            count = self.db.collections_dataset_count(collection["uri"])
            collection["number_of_datasets"] = count

        return self.__render_template (request, "depositor/my-collections.html",
                                       draft_collections     = drafts,
                                       published_collections = published)

    def ui_edit_collection (self, request, collection_id):
        """Implements /my/collections/<id>/edit."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid, error_response = self.__depositor_account_uuid (request)
        if error_response is not None:
            return error_response

        try:
            collection = self.__collection_by_id_or_uri(
                collection_id,
                account_uuid = account_uuid,
                is_published = False)

            if collection is None:
                return self.error_403 (request)

            categories = self.db.categories_tree ()
            account    = self.db.account_by_uuid (account_uuid)
            groups     = self.__groups_for_account (account)

            return self.__render_template (
                request,
                "depositor/edit-collection.html",
                collection = collection,
                account    = account,
                categories = categories,
                groups     = groups)

        except IndexError:
            return self.error_403 (request)

    def ui_new_collection (self, request):
        """Implements /my/collections/new."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid, error_response = self.__depositor_account_uuid (request)
        if error_response is not None:
            return error_response

        container_uuid, _ = self.db.insert_collection(
            title = "Untitled collection",
            account_uuid = account_uuid)

        if container_uuid is not None:
            # Add oneself as author but don't bail if that doesn't work.
            try:
                account    = self.db.account_by_uuid (account_uuid)
                author_uri = URIRef(uuid_to_uri(account["author_uuid"], "author"))
                self.db.update_item_list (container_uuid, account_uuid,
                                          [author_uri], "authors")
            except (TypeError, KeyError):
                logging.warning ("No author record for account %s.", account_uuid)

            return redirect (f"/my/collections/{container_uuid}/edit", code=302)

        return self.error_500()

    def ui_new_version_draft_collection (self, request, collection_id):
        """Implements /my/collections/<id>/new-version-draft."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid, error_response = self.__depositor_account_uuid (request)
        if error_response is not None:
            return error_response

        collection = self.__collection_by_id_or_uri (collection_id,
                                                     is_published = True,
                                                     account_uuid = account_uuid)

        if collection is None:
            logging.error ("Unable to find collection '%s'.", collection_id)
            return self.error_403 (request)

        container_uuid = collection["container_uuid"]
        draft_uuid = self.db.create_draft_from_published_collection (container_uuid)
        if draft_uuid is None:
            logging.info("There is no draft collection.")
            return self.error_500()

        return redirect (f"/my/collections/{container_uuid}/edit", code=302)

    def ui_delete_collection (self, request, collection_id):
        """Implements /my/collections/<id>/delete."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid, error_response = self.__depositor_account_uuid (request)
        if error_response is not None:
            return error_response

        try:
            collection = self.__collection_by_id_or_uri(
                collection_id,
                account_uuid   = account_uuid,
                is_published = False)

            # Either accessing another account's collection or
            # trying to remove a published collection.
            if collection is None:
                return self.error_403 (request)

            result = self.db.delete_collection_draft (
                container_uuid = collection["container_uuid"],
                account_uuid   = account_uuid)

            if result is not None:
                return redirect ("/my/collections", code=303)

        except (IndexError, KeyError):
            pass

        return self.error_500 ()

    def ui_edit_session (self, request, session_uuid):
        """Implements /my/sessions/<id>/edit."""
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':
            if self.accepts_html (request):
                session = self.db.sessions (account_uuid, session_uuid=session_uuid)[0]
                if not session["editable"]:
                    return self.error_403 (request)

                return self.__render_template (
                    request,
                    "depositor/edit-session.html",
                    session = session)

            return self.error_406 ("text/html")

        if request.method == 'PUT':
            try:
                parameters = request.get_json()
                name = validator.string_value (parameters, "name", 0, 255)
                if self.db.update_session (account_uuid, session_uuid, name):
                    return self.respond_205 ()

                return self.error_500 ()

            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

        return self.error_405 (["GET", "PUT"])

    def ui_new_session (self, request):
        """Implements /my/sessions/new."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        _, _, session_uuid = self.db.insert_session (account_uuid,
                                                     name     = "Untitled",
                                                     editable = True)
        if session_uuid is not None:
            return redirect (f"/my/sessions/{session_uuid}/edit", code=302)

        return self.error_500()

    def __remove_session_due_to_2fa_mismatch (self, session_uuid):
        """Procedure to log and delete session upon 2FA mismatch."""
        if self.db.delete_inactive_session_by_uuid (session_uuid):
            logging.access ("Removed session %s due to 2FA mismatch.", #  pylint: disable=no-member
                            session_uuid)
        else:
            logging.error ("Failed to remove session %s to protect 2FA.", session_uuid)

    def ui_activate_session (self, request, session_uuid):
        """Implements /my/sessions/<id>/activate"""

        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        if request.method == "GET":
            return self.__render_template (request, "activate_2fa_session.html",
                                           session_uuid=session_uuid)

        if request.method == "POST":
            token     = self.token_from_cookie (request)
            if not validator.is_valid_uuid (session_uuid):
                return self.error_403 (request)

            mfa_token = request.form.get("mfa-token")
            if not parses_to_int (mfa_token):
                self.__remove_session_due_to_2fa_mismatch (session_uuid)
                return self.error_403 (request)

            account   = self.db.account_by_session_token (token, mfa_token=mfa_token)
            if account is None or "uuid" not in account:
                self.__remove_session_due_to_2fa_mismatch (session_uuid)
                return self.error_authorization_failed (request)

            session = self.db.sessions (account["uuid"],
                                        session_uuid = session_uuid,
                                        mfa_token    = mfa_token)

            if session is None:
                self.__remove_session_due_to_2fa_mismatch (session_uuid)
                return self.error_403 (request)

            if self.db.update_session (account["uuid"], session_uuid, active=True):
                return redirect ("/my/dashboard", code=302)

        return self.error_405 (["GET", "POST"])

    def ui_delete_session (self, request, session_uuid):
        """Implements /my/sessions/<id>/delete."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        response   = redirect (request.referrer, code=302)
        self.db.delete_session_by_uuid (account_uuid, session_uuid)
        return response

    def ui_dataset_new_private_link (self, request, dataset_id):
        """Implements /my/datasets/<id>/private_link/new."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed (request)

        dataset  = self.__dataset_by_id_or_uri (dataset_id,
                                                account_uuid = account_uuid,
                                                is_published = False)
        if dataset is None:
            return self.error_403 (request)

        self.db.insert_private_link (dataset["uuid"], account_uuid, item_type="dataset")
        return redirect (f"/my/datasets/{dataset_id}/private_links", code=302)

    def ui_collection_new_private_link (self, request, collection_id):
        """Implements /my/collections/<id>/private_link/new."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed (request)

        collection  = self.__collection_by_id_or_uri (collection_id,
                                                account_uuid = account_uuid,
                                                is_published = False)
        if collection is None:
            return self.error_403 (request)

        self.db.insert_private_link (collection["uuid"], account_uuid, item_type="collection")
        return redirect (f"/my/collections/{collection_id}/private_links", code=302)

    def __delete_private_link (self, request, item, account_uuid, private_link_id):
        """Deletes the private link for ITEM and responds appropriately."""
        if not item:
            return self.error_403 (request)

        response = redirect (request.referrer, code=302)
        if self.db.delete_private_links (item["container_uuid"],
                                         account_uuid,
                                         private_link_id) is None:
            return self.error_500()

        return response

    def ui_dataset_delete_private_link (self, request, dataset_id, private_link_id):
        """Implements /my/datasets/<id>/private_link/<pid>/delete."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed (request)

        dataset = self.__dataset_by_id_or_uri (dataset_id,
                                               account_uuid = account_uuid,
                                               is_published = False)

        return self.__delete_private_link (request, dataset, account_uuid, private_link_id)

    def ui_collection_delete_private_link (self, request, collection_id, private_link_id):
        """Implements /my/collections/<id>/private_link/<pid>/delete."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed (request)

        collection = self.__collection_by_id_or_uri (collection_id,
                                                     account_uuid = account_uuid,
                                                     is_published = False)

        return self.__delete_private_link (request, collection, account_uuid, private_link_id)

    def ui_profile (self, request):
        """Implements /my/profile."""
        handler = self.default_error_handling (request, "GET", "text/html")
        if handler is not None:
            return handler

        account_uuid, error_response = self.__depositor_account_uuid (request)
        if error_response is not None:
            return error_response

        try:
            return self.__render_template (
                request, "depositor/profile.html",
                account = self.db.accounts (account_uuid=account_uuid)[0],
                categories = self.db.categories_tree ())
        except IndexError:
            return self.error_403 (request)

    def ui_review_dashboard (self, request):
        """Implements /review/dashboard."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid, error_response = self.__reviewer_account_uuid (request)
        if error_response is not None:
            return error_response

        unassigned = self.db.reviews (limit       = 10000,
                                      assigned_to = None,
                                      status      = "unassigned")
        assigned   = self.db.reviews (assigned_to = account_uuid,
                                      limit       = 10000,
                                      status      = "assigned")
        published  = self.db.reviews (assigned_to = account_uuid,
                                      limit       = 10,
                                      status      = "accepted",
                                      order       = "published_date",
                                      order_direction = "desc")
        return self.__render_template (request, "review/dashboard.html",
                                       assigned_reviews   = assigned,
                                       unassigned_reviews = unassigned,
                                       published_reviews  = published)

    def ui_review_overview (self, request):
        """Implements /review/overview."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        token = self.token_from_cookie (request)
        if not self.db.may_review (token):
            return self.error_403 (request)

        reviewers = self.db.reviewer_accounts ()
        reviews = self.db.reviews (limit           = 10000,
                                   order           = "request_date",
                                   order_direction = "desc")
        return self.__render_template (request, "review/overview.html",
                                       reviewers = reviewers,
                                       reviews = reviews)

    def ui_review_assign_to_me (self, request, dataset_id):
        """Implements /review/assign-to-me/<id>."""

        account_uuid, error_response = self.__reviewer_account_uuid (request)
        if error_response is not None:
            logging.error ("Account %d attempted a reviewer action.", account_uuid)
            return error_response

        dataset    = None
        try:
            dataset = self.db.datasets (dataset_uuid    = dataset_id,
                                        is_published    = False,
                                        is_under_review = True)[0]
        except (IndexError, TypeError):
            pass

        if dataset is None:
            return self.error_403 (request)

        if self.db.update_review (dataset["review_uri"],
                                  author_account_uuid = dataset["account_uuid"],
                                  assigned_to = account_uuid,
                                  status      = "assigned"):
            return redirect ("/review/dashboard", code=302)

        return self.error_500()

    def ui_review_unassign (self, request, dataset_id):
        """Implements /review/unassign/<id>."""
        account_uuid, error_response = self.__reviewer_account_uuid (request)
        if error_response is not None:
            logging.error ("Account %d attempted a reviewer action.", account_uuid)
            return error_response

        dataset = None
        try:
            dataset = self.db.datasets (dataset_uuid    = dataset_id,
                                        is_published    = False,
                                        is_under_review = True)[0]
        except (IndexError, TypeError):
            pass

        if dataset is None:
            return self.error_403 (request)

        if self.db.update_review (dataset["review_uri"],
                                  author_account_uuid = dataset["account_uuid"],
                                  assigned_to = None,
                                  status      = "unassigned"):
            return redirect ("/review/dashboard", code=302)

        return self.error_500()

    def ui_review_published (self, request, dataset_id):
        """Implements /review/published/<id>."""
        account_uuid, error_response = self.__reviewer_account_uuid (request)
        if error_response is not None:
            logging.error ("Account %d attempted a reviewer action.", account_uuid)
            return error_response

        dataset = self.__dataset_by_id_or_uri (dataset_id,
                                               is_published = True,
                                               is_latest    = True)

        if dataset is None:
            return self.error_403 (request)

        return self.__render_template (request, "review/published.html",
                                       container_uuid=dataset["container_uuid"])

    def ui_admin_dashboard (self, request):
        """Implements /admin/dashboard."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        token = self.token_from_cookie (request)
        if not self.db.may_administer (token):
            return self.error_403 (request)

        return self.__render_template (request, "admin/dashboard.html")

    def ui_admin_users (self, request):
        """Implements /admin/users."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        token = self.token_from_cookie (request)
        if not self.db.may_administer (token):
            return self.error_403 (request)

        accounts = self.db.accounts()
        return self.__render_template (request, "admin/users.html",
                                       accounts = accounts)

    def ui_admin_exploratory (self, request):
        """Implements /admin/exploratory."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        token = self.token_from_cookie (request)
        if not self.db.may_administer (token):
            return self.error_403 (request)

        return self.__render_template (request, "admin/exploratory.html")

    def ui_admin_maintenance (self, request):
        """Implements /admin/maintenance."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        token = self.token_from_cookie (request)
        if not self.db.may_administer (token):
            return self.error_403 (request)

        return self.__render_template (request, "admin/maintenance.html")

    def ui_admin_clear_cache (self, request):
        """Implements /admin/maintenance/clear-cache."""
        token = self.token_from_cookie (request)
        if self.db.may_administer (token):
            logging.info("Invalidating caches.")
            self.db.cache.invalidate_all ()
            return self.respond_204 ()

        return self.error_403 (request)

    def ui_admin_clear_sessions (self, request):
        """Implements /admin/maintenance/clear-sessions."""
        token = self.token_from_cookie (request)
        if self.db.may_administer (token):
            logging.info("Invalidating sessions.")
            self.db.delete_all_sessions ()
            return redirect ("/", code=302)

        return self.error_403 (request)

    def ui_portal (self, request):
        """Implements /portal."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        summary_data = self.db.repository_statistics()
        try:
            for key in summary_data:
                summary_data[key] = "{:,}".format(int(summary_data[key]))
        except ValueError:
            summary_data = { "datasets": 0, "authors": 0, "collections": 0, "files": 0, "bytes": 0 }

        rgb_shift = ((244,32), (145,145), (32,244)) # begin and end values of r,g,b
        opa_min = 0.3                               # minimum opacity
        rgb_opa_days = (7., 21.)                    # fading times (days) for color and opacity

        today = date.today()
        latest = []
        try:
            records           = self.db.latest_datasets_portal(30)
            latest_pub_date   = records[0]['published_date'][:10]
            fading_delay_days = (today - date(*[int(x) for x in latest_pub_date.split('-')])).days
            for rec in records:
                pub_date = rec['published_date'][:10]
                days = (today - date(*[int(x) for x in pub_date.split('-')])).days
                ago  = ('today','yesterday')[days] if days < 2 else f'{days} days ago'
                days = days - fading_delay_days
                horizontal, vertical = [min(1., days/d) for d in rgb_opa_days]
                rgba = ([round(i[0] + horizontal*(i[1]-i[0])) for i in rgb_shift] +
                        [round(1 - vertical*(1-opa_min), 3)])
                str_rgba = ','.join([str(c) for c in rgba])
                url = f'/datasets/{rec["container_uuid"]}'
                latest.append((url, rec['title'], pub_date, ago, str_rgba))
        except (IndexError, KeyError):
            pass

        return self.__render_template (request, "portal.html",
                                       summary_data=summary_data,
                                       latest = latest)

    def ui_categories (self, request, category_id):
        """Implements /categories/<id>."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        offset    = None
        limit     = None
        page_size = self.get_parameter (request, "page_size")
        page      = self.get_parameter (request, "page")
        if page_size is None:
            page_size = 100
        if page is None:
            page = 1

        try:
            offset, limit = validator.paging_to_offset_and_limit ({
                "page":      page,
                "page_size": page_size,
            })
        except validator.ValidationException:
            pass

        category      = self.db.category_by_id (category_id)
        subcategories = self.db.subcategories_for_category (category["uuid"])
        datasets      = self.db.datasets (categories = [category["id"]],
                                          limit      = limit,
                                          offset     = offset)
        collections   = self.db.collections (categories=[category["id"]], limit=100)

        return self.__render_template (request, "categories.html",
                                       articles=datasets,
                                       collections=collections,
                                       category=category,
                                       subcategories=subcategories)

    def ui_private_dataset (self, request, private_link_id):
        """Implements /private_datasets/<id>."""
        handler = self.default_error_handling (request, "GET", "text/html")
        if handler is not None:
            return handler

        try:
            dataset = self.db.datasets (private_link_id_string = private_link_id,
                                        is_published           = False)[0]
            return self.ui_dataset (request, dataset["container_uuid"],
                                    dataset=dataset, private_view=True)
        except IndexError:
            pass

        return self.error_404 (request)

    def ui_private_collection (self, request, private_link_id):
        """Implements /private_collections/<id>."""
        handler = self.default_error_handling (request, "GET", "text/html")
        if handler is not None:
            return handler

        try:
            collection = self.db.collections (private_link_id_string = private_link_id,
                                              is_published           = False)[0]
            return self.ui_collection (request, collection["container_uuid"],
                                       container=collection, private_view=True)
        except IndexError:
            pass

        return self.error_404 (request)

    def ui_compat_dataset (self, request, slug, dataset_id, version=None):
        """Implements backward-compatibility landing page URLs for datasets."""
        return self.ui_dataset (request, dataset_id, version)

    def ui_dataset (self, request, dataset_id, version=None, dataset=None, private_view=False):
        """Implements /datasets/<id>."""

        handler = self.default_error_handling (request, "GET", "text/html")
        if handler is not None:
            return handler

        if dataset is None:
            if version is not None:
                dataset = self.__dataset_by_id_or_uri (dataset_id, is_published=True, version=version)
            else:
                dataset = self.__dataset_by_id_or_uri (dataset_id, is_published=True, is_latest=True)

            if dataset is None:
                return self.error_404 (request)

        my_collections = []
        my_email = None
        my_name  = None
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid:
            my_collections = self.db.collections_by_account (account_uuid = account_uuid)
            # Name and email may be needed to request access to data with restricted access.
            if value_or_none(dataset, 'is_confidential'):
                try:
                    my_account = self.db.accounts (account_uuid = account_uuid)[0]
                    my_email = my_account['email']
                    first_name = value_or(my_account, 'first_name', '')
                    last_name  = value_or(my_account, 'last_name' , '')
                    my_name = f'{first_name} {last_name}'.strip()
                except IndexError:
                    logging.warning ("No email found for account %s.", account_uuid)

        versions      = self.db.dataset_versions (container_uri=dataset["container_uri"])
        if not versions:
            versions = [{"version": 1}]
        versions      = [v for v in versions if v["version"]]
        current_version = version if version else versions[0]['version']
        id_version    = f"{dataset_id}/{version}" if version else f"{dataset_id}"

        authors       = self.db.authors(item_uri=dataset["uri"], limit=None)
        files         = self.db.dataset_files(dataset_uri=dataset["uri"], limit=None)
        tags          = self.db.tags(item_uri=dataset["uri"], limit=None)
        categories    = self.db.categories(item_uri=dataset["uri"], limit=None)
        references    = self.db.references(item_uri=dataset["uri"], limit=None)
        derived_from  = self.db.derived_from(item_uri=dataset["uri"], limit=None)
        fundings      = self.db.fundings(item_uri=dataset["uri"], limit=None)
        collections   = self.db.collections_from_dataset(dataset["container_uuid"])
        statistics    = {'downloads': value_or(dataset, 'total_downloads', 0),
                         'views'    : value_or(dataset, 'total_views'    , 0),
                         'shares'   : value_or(dataset, 'total_shares'   , 0),
                         'cites'    : value_or(dataset, 'total_cites'    , 0)}
        statistics    = {key:val for (key,val) in statistics.items() if val > 0}
        member = value_or (group_to_member, value_or_none (dataset, "group_id"), 'other')
        member_url_name = member_url_names[member]
        tags = { t['tag'] for t in tags }
        dataset["timeline_first_online"] = value_or_none (dataset, "timeline_first_online")
        dates = self.__pretty_print_dates_for_item (dataset)

        posted_date = value_or_none (dataset, "timeline_posted")
        if posted_date is not None:
            posted_date = posted_date[:4]
        else:
            posted_date = "unpublished"

        citation = make_citation(authors, posted_date, dataset['title'],
                                 value_or (dataset, 'version', 0),
                                 value_or (dataset, 'defined_type_name', 'undefined'),
                                 value_or (dataset, 'doi', 'unavailable'))

        lat = self_or_value_or_none(dataset, 'latitude')
        lon = self_or_value_or_none(dataset, 'longitude')
        lat_valid, lon_valid = decimal_coords(lat, lon)
        coordinates = {'lat': lat, 'lon': lon, 'lat_valid': lat_valid, 'lon_valid': lon_valid}

        odap_files = [(f, is_opendap_url(value_or_none(f, "download_url"))) for f in files]
        opendap = [value_or_none(f, "download_url") for (f, odap) in odap_files if odap]
        files_services = [(f, f['is_link_only']) for (f, odap) in odap_files if not odap]
        services = [value_or_none(f, "download_url") for (f, link) in files_services if link]
        files = [f for (f, link) in files_services if not link]
        if 'data_link' in dataset:
            url = dataset['data_link']
            if url.split('/')[2]=='opendap.4tu.nl':
                opendap.append(url)
                del dataset['data_link']
        contributors = self.parse_contributors(value_or(dataset, 'contributors', ''))

        git_repository_url = None
        if "defined_type_name" in dataset and dataset["defined_type_name"] == "software":
            try:
                git_directory  = f"{self.db.storage}/{dataset['git_uuid']}.git"
                if os.path.exists (git_directory):
                    git_repository_url = f"{self.base_url}/v3/datasets/{dataset['git_uuid']}.git"
            except KeyError:
                pass

        return self.__render_template (request, "dataset.html",
                                       item=dataset,
                                       version=version,
                                       versions=versions,
                                       citation=citation,
                                       container_doi=value_or_none(dataset, "container_doi"),
                                       my_collections = my_collections,
                                       authors=authors,
                                       contributors = contributors,
                                       files=files,
                                       services=services,
                                       tags=tags,
                                       categories=categories,
                                       fundings=fundings,
                                       references=references,
                                       derived_from=derived_from,
                                       collections=collections,
                                       dates=dates,
                                       coordinates=coordinates,
                                       member=member,
                                       member_url_name=member_url_name,
                                       id_version = id_version,
                                       opendap=opendap,
                                       statistics=statistics,
                                       git_repository_url=git_repository_url,
                                       private_view=private_view,
                                       my_email=my_email,
                                       my_name=my_name)

    def ui_data_access_request (self, request):
        """Implements /data_access_request."""

        handler = self.default_error_handling (request, "POST", "application/json")
        if handler is not None:
            return handler

        try:
            parameters = request.get_json()
            email      = validator.string_value (parameters, "email", required=True)
            name       = validator.string_value (parameters, "name", required=True)
            dataset_id = validator.string_value (parameters, "dataset_id", required=True)
            version    = validator.string_value (parameters, "version", required=True)
            reason     = validator.string_value (parameters, "reason", 0, 10000, required=True)

            dataset = self.db.datasets (container_uuid=dataset_id, version=version)[0]

            if not value_or_none(dataset, 'is_confidential'):
                logging.warning("Not allowed. Dataset %s is not confidential", dataset_id)
                return self.error_403 (request)

            doi = dataset['doi']
            title = dataset['title']
            contact_info = self.db.contact_info_from_container(dataset_id)
            addresses = self.db.reviewer_email_addresses()

            # When in pre-production state, don't send e-mails to depositors.
            owner_email = None
            if contact_info and self.in_production and not self.in_preproduction:
                owner_email = contact_info['email']
                addresses.append(owner_email)

            self.__send_templated_email (
                addresses,
                f"Request from {name} for data access to {doi}",
                "data_access_request",
                requester_email = email,
                requester_name  = name,
                owner_email     = owner_email,
                doi             = doi,
                title           = title,
                reason          = reason)

            return self.respond_204 ()
        except (validator.ValidationException, KeyError):
            pass

        return self.error_500 ()

    def ui_compat_collection (self, request, slug, collection_id, version=None):
        """Implements backward-compatibility landing page URLs for collections."""
        return self.ui_collection (request, collection_id, version)

    def ui_collection (self, request, collection_id, version=None,
                       container=None, private_view=False):
        """Implements /collections/<id>."""

        handler = self.default_error_handling (request, "GET", "text/html")
        if handler is not None:
            return handler

        if container is None:
            container_uuid = self.db.container_uuid_by_id(collection_id)
            container = self.db.container (container_uuid, item_type='collection')

        if container is None:
            return self.error_404 (request)

        container_uuid = container["container_uuid"]
        container_uri  = f"container:{container_uuid}"

        versions      = self.db.collection_versions(container_uri=container_uri)
        if not versions:
            versions = [{"version":1}]
        versions      = [v for v in versions if v['version']]
        current_version = version if version else versions[0]['version']

        collection    = None
        try:
            if private_view:
                collection = self.db.collections (container_uuid = container_uuid,
                                                  is_published   = False)[0]
            else:
                collection = self.db.collections (container_uuid = container_uuid,
                                                  version        = current_version,
                                                  is_published   = True)[0]
        except IndexError:
            return self.error_403 (request)

        collection_uri = collection['uri']
        authors       = self.db.authors(item_uri=collection_uri, item_type='collection', limit=None)
        tags          = self.db.tags(item_uri=collection_uri, limit=None)
        categories    = self.db.categories(item_uri=collection_uri, limit=None)
        references    = self.db.references(item_uri=collection_uri, limit=None)
        fundings      = self.db.fundings(item_uri=collection_uri, limit=None)
        statistics    = {'downloads': value_or(container, 'total_downloads', 0),
                         'views'    : value_or(container, 'total_views'    , 0),
                         'shares'   : value_or(container, 'total_shares'   , 0),
                         'cites'    : value_or(container, 'total_cites'    , 0)}
        statistics    = {key:val for (key,val) in statistics.items() if val > 0}
        member = value_or(group_to_member, value_or_none (collection, "group_id"), 'other')
        member_url_name = member_url_names[member]
        tags = { t['tag'] for t in tags }
        collection['timeline_first_online'] = value_or_none (container, 'first_online_date')
        dates = self.__pretty_print_dates_for_item (collection)

        posted_date = value_or_none (collection, "timeline_posted")
        if posted_date is not None:
            posted_date = posted_date[:4]
        else:
            posted_date = "unpublished"

        citation = make_citation(authors, posted_date, collection['title'],
                                 value_or (collection, 'version', 0),
                                 'collection',
                                 value_or (collection, 'doi', 'unavailable'))

        lat = self_or_value_or_none(collection, 'latitude')
        lon = self_or_value_or_none(collection, 'longitude')
        lat_valid, lon_valid = decimal_coords(lat, lon)
        coordinates = {'lat': lat, 'lon': lon, 'lat_valid': lat_valid, 'lon_valid': lon_valid}

        contributors = self.parse_contributors(value_or(collection, 'contributors', ''))
        datasets     = self.db.collection_datasets(collection_uri)

        return self.__render_template (request, "collection.html",
                                       item=collection,
                                       version=version,
                                       versions=versions,
                                       citation=citation,
                                       container_doi=value_or_none(container, 'doi'),
                                       authors=authors,
                                       contributors = contributors,
                                       tags=tags,
                                       categories=categories,
                                       fundings=fundings,
                                       references=references,
                                       dates=dates,
                                       coordinates=coordinates,
                                       member=member,
                                       member_url_name=member_url_name,
                                       datasets=datasets,
                                       statistics=statistics,
                                       private_view=private_view)

    def ui_author (self, request, author_id):
        """Implements /authors/<id>."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        author_uri = f'author:{author_id}'
        try:
            profile = self.db.author_profile (author_uri)[0]
            public_items = self.db.author_public_items(author_uri)
            datasets    = [pi for pi in public_items if pi['is_dataset']]
            collections = [pi for pi in public_items if not pi['is_dataset']]
            collaborators = self.db.author_collaborators(author_uri)
            member = value_or(group_to_member, value_or_none(profile, 'group_id'), 'other')
            member_url_name = member_url_names[member]
            categories = None
            if 'categories' in profile:
                account_uuid = profile['account'].split(':', 1)[1]
                categories = self.db.account_categories (account_uuid)
            statistics = { metric: sum(value_or (dataset, metric, 0) for dataset in datasets)
                           for metric in ('downloads', 'views', 'shares', 'cites') }
            statistics = { key:val for (key,val) in statistics.items() if val > 0 }
            return self.__render_template (request, "author.html",
                                           profile=profile,
                                           datasets=datasets,
                                           collections=collections,
                                           collaborators=collaborators,
                                           member=member,
                                           member_url_name=member_url_name,
                                           categories=categories,
                                           statistics=statistics)
        except IndexError:
            return self.error_404 (request)

    def ui_institution (self, request, institution_name):
        """Implements /institutions/<name>."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        group_name    = institution_name.replace('_', ' ')
        group         = self.db.group_by_name (group_name)
        sub_groups    = self.db.group_by_name (group_name, startswith=True)
        sub_group_ids = [item['group_id'] for item in sub_groups]
        datasets      = self.db.datasets (groups=sub_group_ids,
                                          is_published=True,
                                          limit=100)

        return self.__render_template (request, "institutions.html",
                                       articles=datasets,
                                       group=group,
                                       sub_groups=sub_groups)

    def ui_category (self, request):
        """Implements /category."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        categories    = self.db.root_categories ()
        for category in categories:
            category_id = category["id"]
            category["articles"] = self.db.datasets (categories=[category_id],
                                                     limit=5)

        return self.__render_template (request, "category.html",
                                       categories=categories)

    def ui_opendap_to_doi(self, request):
        """
        Establish back-links from opendap by matching http referrer with triple store
        and list datasets in repository, or redirect if there is exactly one.
        """
        if self.accepts_html (request):
            referrer = request.referrer
            catalog = ""
            dois = []
            if referrer is None:
                referrer = ""
            else:
                catalog = referrer.split('.nl/thredds/', 1)[-1].split('?')[0]
                if catalog.startswith('catalog/data2/IDRA'):
                    # IDRA is available at two places. Use the one in the triple store.
                    catalog = catalog.replace('catalog/data2/IDRA', 'catalog/IDRA')
            catalog_parts = catalog.split('/')
            # start with this catalog and go broader until something found
            for end_index in range(len(catalog_parts[:-1]), 0, -1):
                catalog_end = '/'.join(catalog_parts[:end_index] + [catalog_parts[-1]])
                dois = self.db.opendap_to_doi(endswith=catalog_end)
                if dois:
                    break
            if not dois:
                # search narrower catalogs (either opendap.4tu.nl or opendap.tudelft.nl)
                catalog_start = [f"https://opendap.4tu.nl/thredds/{ '/'.join(catalog_parts[:-1]) }/",
                                 f"https://opendap.tudelft.nl/thredds/{ '/'.join(catalog_parts[:-1]) }/"]
                dois = self.db.opendap_to_doi(startswith=catalog_start)
            if len(dois) == 1:
                return redirect(f"https://doi.org/{ dois[0]['doi'] }")

            dois.sort(key=lambda x: x["title"])

            return self.__render_template (request, "opendap_to_doi.html",
                                           dois=dois,
                                           referrer=referrer)

        return self.error_406 ("text/html")

    def ui_download_all_files (self, request, dataset_id, version):
        """Implements /ndownloader/items/<id>/versions/<version>"""
        try:
            ## Check whether a public dataset can be found.
            dataset  = self.__dataset_by_id_or_uri (dataset_id, version=version)

            ## When downloading a file from a dataset that isn't published,
            ## we need to authorize it first.
            if dataset is None and version == "draft":
                account_uuid = self.account_uuid_from_request (request)
                if account_uuid is not None:
                    dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                           account_uuid = account_uuid,
                                                           is_published = False)

            ## Check again whether a private dataset has been found.
            if dataset is None:
                logging.error("Download-all for %s failed: Dataset not found.", dataset_id)
                return self.error_404 (request)

            metadata = self.__files_by_id_or_uri (dataset_uri = dataset["uri"])
            file_paths = []
            for file_info in metadata:
                filesystem_location = f"{self.db.secondary_storage}/{file_info['id']}/{file_info['name']}"

                ## Data stored before Djehuty went into production requires a few tweaks.
                ## Only apply these quirks when enabled.
                if self.db.secondary_storage_quirks:
                    transformed_name = file_info['name'].replace(" ", "").replace("-", "")
                    filesystem_location = f"{self.db.secondary_storage}/{file_info['id']}/{transformed_name}"

                if "filesystem_location" in file_info:
                    filesystem_location = file_info["filesystem_location"]
                file_paths.append ({
                    "fs": filesystem_location,
                    "n":  file_info["name"]
                })

            if not file_paths:
                logging.error("Download-all for %s failed: No files associated with this dataset.",
                              dataset_id)
                return self.error_404 (request)

            zipfly_object = zipfly.ZipFly(paths = file_paths)
            writer = zipfly_object.generator()
            return self.response (writer, mimetype="application/zip")

        except (KeyError, IndexError, TypeError, FileNotFoundError) as error:
            logging.error("File download for %s failed due to: %s.", dataset_id, error)
            return self.error_404 (request)

    def ui_download_file (self, request, dataset_id, file_id):
        """Implements /file/<id>/<fid>."""
        try:
            dataset  = self.__dataset_by_id_or_uri (dataset_id)

            ## When downloading a file from a dataset that isn't published,
            ## we need to authorize it first.
            if dataset is None:
                account_uuid = self.account_uuid_from_request (request)
                if account_uuid is not None:
                    dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                           account_uuid = account_uuid,
                                                           is_published = False)

            ## Check again whether a private dataset has been found.
            if dataset is None:
                return self.error_404 (request)

            metadata  = self.__file_by_id_or_uri (file_id, dataset_uri = dataset["uri"])
            if "id" in metadata:
                file_path = f"{self.db.secondary_storage}/{metadata['id']}/{metadata['name']}"
            if "filesystem_location" in metadata:
                file_path = metadata["filesystem_location"]

            if file_path is None:
                logging.error ("File download failed due to missing metadata.")
                return self.error_500 ()

            return send_file (file_path,
                              request.environ,
                              "application/octet-stream",
                              as_attachment=True,
                              download_name=metadata["name"])

        except IndexError:
            return self.error_404 (request)
        except TypeError as error:
            logging.error("File download failed due to: %s", error)
            return self.error_404 (request)
        except FileNotFoundError:
            logging.error ("File download failed due to missing file.")

        return self.error_500 ()

    def ui_search (self, request):
        """Implements /search."""
        if self.accepts_html (request):
            search_for = self.get_parameter(request, "search")
            search_for = search_for.strip()
            operators = ("(", ")", "AND", "OR")
            has_operators = any((operator in search_for) for operator in operators)

            fields = ["title", "resource_title", "description", "citation", "format"]
            re_field = ":(" + "|".join(fields+["search_term"]) + "):"
            has_fieldsearch = re.search(re_field, search_for) is not None

            re_operator = r"(\(|\)|AND|OR)"
            search_list = re.split(re_operator, search_for)

            search_list = list(filter(None, [s.strip() for s in search_list]))

            if has_operators:
                search_list = [{"operator": element.upper()} if (element.upper() in operators) else element for element in search_list]
            elif has_fieldsearch:
                pass
            else:
                # search terms are handled separately (split on spaces) and combined with OR operators
                # terms in double quotes are seen as one
                quoted = search_for.split('"')[1::2]
                not_quoted = [item.split() for item in search_for.split('"')[0::2]]
                # flatten list
                not_quoted = sum(not_quoted, [])
                # combine quoted and non-quoted and strip leading and trailing spaces
                search_list = [item.strip() for item in quoted + not_quoted]
                # add OR operators
                index = -1
                while len(search_list) + index > 0:
                    search_list.insert(index, {"operator": "OR"})
                    index = index - 2

            display_list = search_list[:]
            for idx, search_term in enumerate(search_list):
                if isinstance(search_term, dict):
                    continue

                if re.search(re_field, search_term) is not None:
                    field_name = re.split(':', search_term)[1::2][0]
                    value = list(filter(None, [s.strip() for s in re.split(':', search_term)[0::2]]))[0]
                    if value.startswith('"') and value.endswith('"'):
                        display_list[idx] = display_list[idx].replace(value, value.strip('"'))
                        value = value.strip('"')
                    if field_name in fields:
                        search_list[idx] = {field_name: value}
                    elif field_name == "search_term":
                        search_dict = {}
                        for field_name in fields:
                            search_dict[field_name] = value
                        search_list[idx] = search_dict
                elif has_fieldsearch is False:
                    search_dict = {}
                    if search_term.startswith('"') and search_term.endswith('"'):
                        display_list[idx] = search_term.strip('"')
                        search_term = search_term.strip('"')
                    for field_name in fields:
                        search_dict[field_name] = search_term
                    search_list[idx] = search_dict

            dataset_count = self.db.datasets (search_for=search_list, is_published=True, return_count=True)
            if dataset_count == []:
                message = "Invalid query"
                datasets = []
                dataset_count = 0
            else:
                message = None
                dataset_count = dataset_count[0]["datasets"]
                datasets = self.db.datasets (search_for=search_list, is_published=True, limit=100)
            return self.__render_template (request, "search.html",
                                           search_for=search_for,
                                           articles=datasets,
                                           dataset_count=dataset_count,
                                           message=message,
                                           display_terms=display_list)
        return self.error_406 ("text/html")

    def api_authorize (self, request):
        """Implements /v2/account/applications/authorize."""
        return self.error_404 (request)

    def api_token (self, request):
        """Implements /v2/token."""
        return self.error_404 (request)

    def api_private_institution (self, request):
        """Implements /v2/account/institution."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        ## Authorization
        ## ----------------------------------------------------------------
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        ## Our API only contains data from 4TU.ResearchData.
        return self.response (json.dumps({
            "id": 898,
            "name": "4TU.ResearchData"
        }))

    def api_private_institution_accounts (self, request):
        """Implements /v2/account/institution/accounts."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        token = self.token_from_request (request)
        if not self.db.may_administer (token):
            return self.error_403 (request)

        try:
            offset, limit       = validator.paging_to_offset_and_limit (request.args)
            institution_user_id = validator.string_value (request.args, "institution_user_id", 0, 4096)
            is_active           = validator.integer_value (request.args, "is_active", 0, 1)
            email               = validator.string_value (request.args, "email", 0, 4096)
            id_lte              = validator.integer_value (request.args, "id_lte", 0, pow(2, 63))
            id_gte              = validator.integer_value (request.args, "id_gte", 0, pow(2, 63))
        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

        accounts = self.db.accounts (limit=limit,   offset=offset,
                                     email=email,   is_active=is_active,
                                     id_lte=id_lte, id_gte=id_gte,
                                     institution_user_id=institution_user_id)

        return self.default_list_response (accounts, formatter.format_account_record)

    def api_private_institution_account (self, request, account_uuid):
        """Implements /v2/account/institution/users/<id>."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        ## Authorization
        ## ----------------------------------------------------------------
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        account   = self.db.account_by_uuid (account_uuid)
        formatted = formatter.format_account_record(account)

        return self.response (json.dumps (formatted))

    def api_datasets (self, request):
        """Implements /v2/articles."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        try:
            record  = self.__default_dataset_api_parameters (request)
            records = self.db.datasets (**record, is_latest = 1)
            return self.default_list_response (records, formatter.format_dataset_record)

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    def api_datasets_search (self, request):
        """Implements /v2/articles/search."""
        handler = self.default_error_handling (request, "POST", "application/json")
        if handler is not None:
            return handler

        try:
            record  = self.__default_dataset_api_parameters (request.get_json())
            records = self.db.datasets (**record)
            return self.default_list_response (records, formatter.format_dataset_record)
        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    def api_licenses (self, request):
        """Implements /v2/licenses."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        records = self.db.licenses()
        return self.default_list_response (records, formatter.format_license_record)

    def api_dataset_details (self, request, dataset_id):
        """Implements /v2/articles/<id>."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        try:
            dataset         = self.__dataset_by_id_or_uri (dataset_id, account_uuid=None, is_latest=True)
            dataset_uri     = dataset["uri"]
            authors         = self.db.authors(item_uri=dataset_uri, item_type="dataset")
            files           = self.db.dataset_files(dataset_uri=dataset_uri)
            custom_fields   = self.db.custom_fields(item_uri=dataset_uri, item_type="dataset")
            tags            = self.db.tags(item_uri=dataset_uri)
            categories      = self.db.categories(item_uri=dataset_uri)
            references      = self.db.references(item_uri=dataset_uri)
            funding_list    = self.db.fundings(item_uri=dataset_uri, item_type="dataset")
            total         = formatter.format_dataset_details_record (dataset,
                                                                     authors,
                                                                     files,
                                                                     custom_fields,
                                                                     tags,
                                                                     categories,
                                                                     funding_list,
                                                                     references)
            # ugly fix for custom field Derived From
            custom = total['custom_fields']
            custom = [c for c in custom if c['name'] != 'Derived From']
            custom.append( {"name": "Derived From",
                            "value": self.db.derived_from(item_uri=dataset_uri)} )
            total['custom_fields'] = custom
            return self.response (json.dumps(total))
        except (IndexError, TypeError):
            response = self.response (json.dumps({
                "message": "This dataset cannot be found."
            }))
            response.status_code = 404
            return response

    def api_dataset_versions (self, request, dataset_id):
        """Implements /v2/articles/<id>/versions."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        container = self.__dataset_by_id_or_uri (dataset_id, is_published=True)
        if container is None:
            return self.error_404 (request)

        versions  = self.db.dataset_versions (container_uri=container["container_uri"])
        return self.default_list_response (versions, formatter.format_version_record)

    def api_dataset_version_details (self, request, dataset_id, version):
        """Implements /v2/articles/<id>/versions/<version>."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        try:
            dataset       = self.__dataset_by_id_or_uri (dataset_id,
                                                         is_published = True,
                                                         version = version)

            dataset_uri   = dataset["uri"]
            authors       = self.db.authors(item_uri=dataset_uri, item_type="dataset")
            files         = self.db.dataset_files(dataset_uri=dataset_uri)
            custom_fields = self.db.custom_fields(item_uri=dataset_uri, item_type="dataset")
            tags          = self.db.tags(item_uri=dataset_uri)
            categories    = self.db.categories(item_uri=dataset_uri)
            references    = self.db.references(item_uri=dataset_uri)
            fundings      = self.db.fundings(item_uri=dataset_uri, item_type="dataset")
            total         = formatter.format_dataset_details_record (dataset,
                                                                     authors,
                                                                     files,
                                                                     custom_fields,
                                                                     tags,
                                                                     categories,
                                                                     fundings,
                                                                     references)
            return self.response (json.dumps(total))
        except IndexError:
            response = self.response (json.dumps({
                "message": "This dataset cannot be found."
            }))
            response.status_code = 404
            return response

    def api_dataset_version_embargo (self, request, dataset_id, version):
        """Implements /v2/articles/<id>/versions/<version>/embargo."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        try:
            dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                   version      = version,
                                                   is_published = True)
            total   = formatter.format_dataset_embargo_record (dataset)
            return self.response (json.dumps(total))
        except IndexError:
            response = self.response (json.dumps({
                "message": "This dataset cannot be found."
            }))
            response.status_code = 404
            return response

    def api_dataset_version_confidentiality (self, request, dataset_id, version):
        """Implements /v2/articles/<id>/versions/<version>/confidentiality."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        try:
            dataset       = self.__dataset_by_id_or_uri (dataset_id,
                                                         version = version,
                                                         is_published = True)
            total           = formatter.format_dataset_confidentiality_record (dataset)
            return self.response (json.dumps(total))
        except IndexError:
            response = self.response (json.dumps({
                "message": "This dataset cannot be found."
            }))
            response.status_code = 404
            return response

    def api_dataset_version_update_thumb (self, request, dataset_id, version):
        """Implements /v2/articles/<id>/versions/<version>/update_thumb."""
        if request.method != 'PUT':
            return self.error_405 ("PUT")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        parameters = request.get_json()
        file_id    = value_or_none (parameters, "file_id")
        if not self.db.dataset_update_thumb (dataset_id, version, account_uuid, file_id):
            return self.respond_205()

        return self.error_500()

    def api_dataset_files (self, request, dataset_id):
        """Implements /v2/articles/<id>/files."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        dataset = self.__dataset_by_id_or_uri (dataset_id, is_published=True)
        files   = self.db.dataset_files (dataset_uri=dataset["uri"])

        return self.default_list_response (files, formatter.format_file_for_dataset_record)

    def api_dataset_file_details (self, request, dataset_id, file_id):
        """Implements /v2/articles/<id>/files/<fid>."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        try:
            dataset = self.__dataset_by_id_or_uri (dataset_id, is_published=True)
            files   = self.__file_by_id_or_uri (file_id,
                                                dataset_uri = dataset["uri"])

            results = formatter.format_file_for_dataset_record (files)
            return self.response (json.dumps(results))
        except IndexError:
            response = self.response (json.dumps({
                "message": "This file cannot be found."
            }))
            response.status_code = 404
            return response

    def api_private_datasets (self, request):
        """Implements /v2/account/articles."""
        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':
            try:
                offset, limit = validator.paging_to_offset_and_limit ({
                    "page":      self.get_parameter (request, "page"),
                    "page_size": self.get_parameter (request, "page_size"),
                    "limit":     self.get_parameter (request, "limit"),
                    "offset":    self.get_parameter (request, "offset")
                })

                records = self.db.datasets (limit=limit,
                                            offset=offset,
                                            is_published = False,
                                            account_uuid=account_uuid)

                return self.default_list_response (records, formatter.format_dataset_record)

            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

        if request.method == 'POST':
            record = request.get_json()
            try:
                tags = validator.array_value (record, "tags", False)
                if not tags:
                    tags = validator.array_value (record, "keywords", False)

                license_id  = validator.integer_value (record, "license", 0, pow(2, 63), False)
                license_url = self.db.license_url_by_id (license_id)
                timeline   = validator.object_value (record, "timeline", False)
                container_uuid, _ = self.db.insert_dataset (
                    title          = validator.string_value  (record, "title",          3, 1000,                   True),
                    account_uuid     = account_uuid,
                    description    = validator.string_value  (record, "description",    0, 10000,                  False),
                    tags           = tags,
                    references     = validator.array_value   (record, "references",                                False),
                    categories     = validator.array_value   (record, "categories",                                False),
                    authors        = validator.array_value   (record, "authors",                                   False),
                    defined_type_name = validator.options_value (record, "defined_type", validator.dataset_types,  False),
                    funding        = validator.string_value  (record, "funding",        0, 255,                    False),
                    funding_list   = validator.array_value   (record, "funding_list",                              False),
                    license_url    = license_url,
                    language       = validator.string_value  (record, "language",       0, 8,                      False),
                    doi            = validator.string_value  (record, "doi",            0, 255,                    False),
                    handle         = validator.string_value  (record, "handle",         0, 255,                    False),
                    resource_doi   = validator.string_value  (record, "resource_doi",   0, 255,                    False),
                    resource_title = validator.string_value  (record, "resource_title", 0, 255,                    False),
                    group_id       = validator.integer_value (record, "group_id",       0, pow(2, 63),             False),
                    publisher      = validator.string_value  (record, "publisher",      0, 255,                    False),
                    custom_fields  = validator.object_value  (record, "custom_fields",                             False),
                    # Unpack the 'timeline' object.
                    first_online          = validator.string_value (timeline, "firstOnline",                       False),
                    publisher_publication = validator.string_value (timeline, "publisherPublication",              False),
                    submission            = validator.string_value (timeline, "submission",                        False),
                    posted                = validator.string_value (timeline, "posted",                            False),
                    revision              = validator.string_value (timeline, "revision",                          False)
                )

                return self.response(json.dumps({
                    "location": f"{self.base_url}/v2/account/articles/{container_uuid}",
                    "warnings": []
                }))
            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

        return self.error_405 (["GET", "POST"])

    def api_private_dataset_details (self, request, dataset_id):
        """Implements /v2/account/articles/<id>."""
        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':
            try:
                dataset     = self.__dataset_by_id_or_uri (dataset_id,
                                                           account_uuid=account_uuid,
                                                           is_published=False)

                if not dataset:
                    return self.response ("[]")

                dataset_uri     = dataset["uri"]
                authors         = self.db.authors(item_uri=dataset_uri, item_type="dataset")
                files           = self.db.dataset_files(dataset_uri=dataset_uri, account_uuid=account_uuid)
                custom_fields   = self.db.custom_fields(item_uri=dataset_uri, item_type="dataset")
                tags            = self.db.tags(item_uri=dataset_uri)
                categories      = self.db.categories(item_uri=dataset_uri)
                references      = self.db.references(item_uri=dataset_uri)
                funding_list    = self.db.fundings(item_uri=dataset_uri, item_type="dataset")
                total           = formatter.format_dataset_details_record (dataset,
                                                                           authors,
                                                                           files,
                                                                           custom_fields,
                                                                           tags,
                                                                           categories,
                                                                           funding_list,
                                                                           references,
                                                                           is_private=True)
                # ugly fix for custom field Derived From
                custom = total['custom_fields']
                custom = [c for c in custom if c['name'] != 'Derived From']
                custom.append( {"name": "Derived From",
                                "value": self.db.derived_from(item_uri=dataset_uri)} )
                total['custom_fields'] = custom
                return self.response (json.dumps(total))
            except (IndexError, KeyError):
                response = self.response (json.dumps({
                    "message": "This dataset cannot be found."
                }))
                response.status_code = 404
                return response

        if request.method == 'PUT':
            record = request.get_json()
            try:
                defined_type_name = validator.string_value (record, "defined_type", 0, 512)
                ## These magic numbers are pre-determined by Figshare.
                defined_type = 0
                if defined_type_name == "software":
                    defined_type = 9
                elif defined_type_name == "dataset":
                    defined_type = 3

                dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                       account_uuid = account_uuid,
                                                       is_published = False)

                is_embargoed = validator.boolean_value (record, "is_embargoed", when_none=False)
                embargo_options = validator.array_value (record, "embargo_options")
                embargo_option  = value_or_none (embargo_options, 0)
                is_restricted   = value_or (embargo_option, "id", 0) == 1000
                is_closed       = value_or (embargo_option, "id", 0) == 1001
                is_temporary_embargo = is_embargoed and not is_restricted and not is_closed
                license_id  = validator.integer_value (record, "license_id", 0, pow(2, 63))
                license_url = self.db.license_url_by_id (license_id)

                result = self.db.update_dataset (dataset["container_uuid"],
                    account_uuid,
                    title           = validator.string_value  (record, "title",          3, 1000),
                    description     = validator.string_value  (record, "description",    0, 10000),
                    resource_doi    = validator.string_value  (record, "resource_doi",   0, 255),
                    resource_title  = validator.string_value  (record, "resource_title", 0, 255),
                    license_url     = license_url,
                    group_id        = validator.integer_value (record, "group_id",       0, pow(2, 63)),
                    time_coverage   = validator.string_value  (record, "time_coverage",  0, 512),
                    publisher       = validator.string_value  (record, "publisher",      0, 10000),
                    language        = validator.string_value  (record, "language",       0, 8),
                    contributors    = validator.string_value  (record, "contributors",   0, 10000),
                    license_remarks = validator.string_value  (record, "license_remarks",0, 10000),
                    geolocation     = validator.string_value  (record, "geolocation",    0, 255),
                    longitude       = validator.string_value  (record, "longitude",      0, 64),
                    latitude        = validator.string_value  (record, "latitude",       0, 64),
                    mimetype        = validator.string_value  (record, "format",         0, 255),
                    data_link       = validator.string_value  (record, "data_link",      0, 255),
                    derived_from    = validator.string_value  (record, "derived_from",   0, 255),
                    same_as         = validator.string_value  (record, "same_as",        0, 255),
                    organizations   = validator.string_value  (record, "organizations",  0, 512),
                    is_embargoed    = is_embargoed,
                    is_metadata_record = validator.boolean_value (record, "is_metadata_record", when_none=False),
                    metadata_reason = validator.string_value  (record, "metadata_reason",  0, 512),
                    embargo_until_date = validator.date_value (record, "embargo_until_date",
                                                               is_temporary_embargo),
                    embargo_type    = validator.options_value (record, "embargo_type", validator.embargo_types),
                    embargo_title   = validator.string_value  (record, "embargo_title", 0, 1000),
                    embargo_reason  = validator.string_value  (record, "embargo_reason", 0, 10000),
                    eula            = validator.string_value  (record, "eula", 0, 10000),
                    embargo_allow_access_requests = is_restricted or is_temporary_embargo,
                    defined_type_name = defined_type_name,
                    defined_type    = defined_type,
                    agreed_to_deposit_agreement = validator.boolean_value (record, "agreed_to_deposit_agreement", False, False),
                    agreed_to_publish = validator.boolean_value (record, "agreed_to_publish", False, False),
                    categories      = validator.array_value   (record, "categories"),
                )
                if not result:
                    return self.error_500()

                return self.respond_205()

            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)
            except (IndexError, KeyError):
                pass

            return self.error_500 ()

        if request.method == 'DELETE':
            try:
                dataset     = self.__dataset_by_id_or_uri (dataset_id,
                                                           account_uuid=account_uuid,
                                                           is_published=False)

                container_uuid = dataset["container_uuid"]
                if self.db.delete_dataset_draft (container_uuid, account_uuid):
                    return self.respond_204()
            except (IndexError, KeyError):
                pass

            return self.error_500 ()

        return self.error_405 (["GET", "PUT", "DELETE"])

    def api_private_dataset_authors (self, request, dataset_id):
        """Implements /v2/account/articles/<id>/authors."""

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':
            try:
                dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                       account_uuid=account_uuid,
                                                       is_published=False)

                authors = self.db.authors (item_uri   = dataset["uri"],
                                           account_uuid = account_uuid,
                                           is_published = False,
                                           item_type  = "dataset",
                                           limit      = 10000)

                return self.default_list_response (authors, formatter.format_author_record)
            except (IndexError, KeyError, TypeError):
                pass

            return self.error_500 ()

        if request.method in ['POST', 'PUT']:
            ## The 'parameters' will be a dictionary containing a key "authors",
            ## which can contain multiple dictionaries of author records.
            parameters = request.get_json()

            try:
                new_authors = []
                records     = parameters["authors"]
                for record in records:
                    # The following fields are allowed:
                    # id, name, first_name, last_name, email, orcid_id, job_title.
                    #
                    # We assume values for is_active and is_public.
                    author_uuid  = validator.string_value (record, "uuid", 0, 36, False)
                    if author_uuid is None:
                        author_uuid = self.db.insert_author (
                            full_name  = validator.string_value  (record, "name",       0, 255,        False),
                            first_name = validator.string_value  (record, "first_name", 0, 255,        False),
                            last_name  = validator.string_value  (record, "last_name",  0, 255,        False),
                            email      = validator.string_value  (record, "email",      0, 255,        False),
                            orcid_id   = validator.string_value  (record, "orcid_id",   0, 255,        False),
                            job_title  = validator.string_value  (record, "job_title",  0, 255,        False),
                            is_active  = False,
                            is_public  = True,
                            created_by = account_uuid)
                        if author_uuid is None:
                            logging.error("Adding a single author failed.")
                            return self.error_500()
                    new_authors.append(URIRef(uuid_to_uri (author_uuid, "author")))

                dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                       account_uuid=account_uuid,
                                                       is_published=False)

                # The PUT method overwrites the existing authors, so we can
                # keep an empty starting list. For POST we must retrieve the
                # existing authors to preserve them.
                existing_authors = []
                if request.method == 'POST':
                    existing_authors = self.db.authors (
                        item_uri     = dataset["uri"],
                        account_uuid   = account_uuid,
                        item_type    = "dataset",
                        is_published = False,
                        limit        = 10000)

                    existing_authors = list(map (lambda item: URIRef(uuid_to_uri(item["uuid"], "author")),
                                                 existing_authors))

                authors = existing_authors + new_authors
                if not self.db.update_item_list (dataset["container_uuid"],
                                                 account_uuid,
                                                 authors,
                                                 "authors"):
                    logging.error("Adding a single author failed.")
                    return self.error_500()

                return self.respond_205()

            except KeyError:
                return self.error_400 (request, "Expected an 'authors' field.", "NoAuthorsField")
            except IndexError:
                return self.error_500 ()
            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

        return self.error_405 ("GET")

    def api_private_dataset_author_delete (self, request, dataset_id, author_id):
        """Implements /v2/account/articles/<id>/authors/<a_id>."""
        if request.method != 'DELETE':
            return self.error_405 ("DELETE")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        try:
            dataset   = self.__dataset_by_id_or_uri (dataset_id,
                                                     account_uuid = account_uuid,
                                                     is_published = False)

            if dataset is None:
                return self.error_403 (request)

            authors = self.db.authors (item_uri     = dataset["uri"],
                                       account_uuid = account_uuid,
                                       is_published = False,
                                       item_type    = "dataset",
                                       limit        = 10000)

            if parses_to_int (author_id):
                authors.remove (next (filter (lambda item: item['id'] == author_id, authors)))
            else:
                authors.remove (next (filter (lambda item: item['uuid'] == author_id, authors)))

            authors = list(map (lambda item: URIRef(uuid_to_uri(item["uuid"], "author")), authors))
            if self.db.update_item_list (dataset["container_uuid"],
                                         account_uuid,
                                         authors,
                                         "authors"):
                return self.respond_204()

            return self.error_500()
        except (IndexError, KeyError):
            return self.error_500 ()

    def __api_private_item_funding (self, request, item_id, item_type,
                                    item_by_id_procedure):
        """Implements handling funding for both datasets and collections."""

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        accepted_methods = ["GET", "POST", "PUT"]
        if request.method not in accepted_methods:
            return self.error_405 (accepted_methods)

        if request.method == 'GET':
            try:
                item = item_by_id_procedure (item_id,
                                             account_uuid=account_uuid,
                                             is_published=False)

                if item is None:
                    return self.error_403 (request)

                funding = self.db.fundings (item_uri     = item["uri"],
                                            account_uuid = account_uuid,
                                            is_published = False,
                                            item_type    = item_type,
                                            limit        = 10000)

                return self.default_list_response (funding, formatter.format_funding_record)
            except (IndexError, KeyError, TypeError):
                pass

            return self.error_500 ()

        if request.method in ['POST', 'PUT']:
            ## The 'parameters' will be a dictionary containing a key "funders",
            ## which can contain multiple dictionaries of funding records.
            parameters = request.get_json()

            try:
                item = item_by_id_procedure (item_id,
                                             account_uuid=account_uuid,
                                             is_published=False)

                if item is None:
                    return self.error_403 (request)

                new_fundings = []
                records     = parameters["funders"]
                for record in records:
                    funder_uuid = validator.string_value (record, "uuid", 0, 36, False)

                    if funder_uuid is None:
                        funder_uuid = self.db.insert_funding (
                            title       = validator.string_value (record, "title", 0, 255, False),
                            grant_code  = validator.string_value (record, "grant_code", 0, 32, False),
                            funder_name = validator.string_value (record, "funder_name", 0, 255, False),
                            url         = validator.string_value (record, "url", 0, 512, False),
                            account_uuid = account_uuid)
                        if funder_uuid is None:
                            logging.error("Adding a single funder failed.")
                            return self.error_500()
                    new_fundings.append(URIRef(uuid_to_uri (funder_uuid, "funding")))

                # The PUT method overwrites the existing funding list, so we can
                # keep an empty starting list. For POST we must retrieve the
                # existing authors to preserve them.
                existing_fundings = []
                if request.method == 'POST':
                    existing_fundings = self.db.fundings (
                        item_uri     = item["uri"],
                        account_uuid = account_uuid,
                        item_type    = item_type,
                        is_published = False,
                        limit        = 10000)

                    existing_fundings = list(map (lambda item: URIRef(uuid_to_uri(item["uuid"],"funding")),
                                                 existing_fundings))

                fundings = existing_fundings + new_fundings
                if not self.db.update_item_list (item["container_uuid"],
                                                 account_uuid,
                                                 fundings,
                                                 "funding_list"):
                    logging.error("Adding a single funder failed.")
                    return self.error_500()

                return self.respond_205()

            except KeyError:
                return self.error_400 (request, "Expected a 'funders' field.", "NoFundersField")
            except IndexError:
                return self.error_500 ()
            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

        return self.error_500 ()

    def api_private_dataset_funding (self, request, dataset_id):
        """Implements /v2/account/articles/<id>/funding."""
        return self.__api_private_item_funding (request, dataset_id, "dataset",
                                                self.__dataset_by_id_or_uri)

    def api_private_collection_funding (self, request, collection_id):
        """Implements /v2/account/collections/<id>/funding."""
        return self.__api_private_item_funding (request, collection_id, "collection",
                                                self.__collection_by_id_or_uri)

    def __api_private_item_funding_delete (self, request, item_id, item_type,
                                           item_by_id_procedure, funding_id):
        """Implements removing funding for both datasets and collections."""

        if request.method != 'DELETE':
            return self.error_405 ("DELETE")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        try:
            item   = item_by_id_procedure (item_id,
                                           account_uuid = account_uuid,
                                           is_published = False)

            if item is None:
                return self.error_403 (request)

            fundings = self.db.fundings (item_uri     = item["uri"],
                                         account_uuid = account_uuid,
                                         is_published = False,
                                         item_type    = item_type,
                                         limit        = 10000)

            fundings.remove (next (filter (lambda item: item['uuid'] == funding_id, fundings)))

            fundings = list(map (lambda item: URIRef(uuid_to_uri(item["uuid"], "funding")), fundings))
            if self.db.update_item_list (item["container_uuid"],
                                         account_uuid,
                                         fundings,
                                         "funding_list"):
                return self.respond_204()

            return self.error_500()
        except (IndexError, KeyError):
            return self.error_500 ()

    def api_private_dataset_funding_delete (self, request, dataset_id, funding_id):
        """Implements /v2/account/articles/<id>/funding/<fid>."""
        return self.__api_private_item_funding_delete (request, dataset_id, "dataset",
                                                       self.__dataset_by_id_or_uri,
                                                       funding_id)

    def api_private_collection_funding_delete (self, request, collection_id, funding_id):
        """Implements /v2/account/collections/<id>/funding/<fid>."""
        return self.__api_private_item_funding_delete (request, collection_id, "collection",
                                                       self.__collection_by_id_or_uri,
                                                       funding_id)

    def api_private_collection_author_delete (self, request, collection_id, author_id):
        """Implements /v2/account/collections/<id>/authors/<a_id>."""
        if request.method != 'DELETE':
            return self.error_405 ("DELETE")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        try:
            collection = self.__collection_by_id_or_uri (collection_id,
                                                         account_uuid = account_uuid,
                                                         is_published = False)

            if collection is None:
                return self.error_403 (request)

            authors    = self.db.authors (item_uri     = collection["uri"],
                                          account_uuid = account_uuid,
                                          is_published = False,
                                          item_type    = "collection",
                                          limit        = 10000)

            if parses_to_int (author_id):
                authors.remove (next (filter (lambda item: item['id'] == author_id, authors)))
            else:
                authors.remove (next (filter (lambda item: item['uuid'] == author_id, authors)))

            authors = list(map(lambda item: URIRef(uuid_to_uri(item["uuid"], "author")),
                                authors))

            if self.db.update_item_list (uri_to_uuid (collection["container_uri"]),
                                         account_uuid,
                                         authors,
                                         "authors"):
                return self.respond_204()

            return self.error_500()
        except (IndexError, KeyError):
            return self.error_500 ()

    def api_private_collection_dataset_delete (self, request, collection_id, dataset_id):
        """Implements /v2/account/collections/<id>/articles/<dataset_id>."""
        if request.method != 'DELETE':
            return self.error_405 ("DELETE")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        try:
            collection = self.__collection_by_id_or_uri (collection_id, account_uuid=account_uuid, is_published=False)
            dataset    = self.__dataset_by_id_or_uri (dataset_id)
            if collection is None or dataset is None:
                return self.error_404 (request)

            datasets = self.db.datasets(collection_uri=collection["uri"], is_latest=True)
            datasets.remove (next
                             (filter
                              (lambda item: item["container_uuid"] == dataset["container_uuid"],
                               datasets)))

            datasets = list(map(lambda item: URIRef(uuid_to_uri(item["container_uuid"], "container")),
                                datasets))

            if self.db.update_item_list (collection["container_uuid"],
                                         account_uuid,
                                         datasets,
                                         "datasets"):
                self.db.cache.invalidate_by_prefix ("datasets")
                return self.respond_204()
        except (IndexError, KeyError):
            return self.error_500 ()

        return self.error_403 (request)

    def api_private_dataset_categories (self, request, dataset_id):
        """Implements /v2/account/articles/<id>/categories."""
        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':
            try:
                dataset       = self.__dataset_by_id_or_uri (dataset_id,
                                                             account_uuid=account_uuid,
                                                             is_published=False)

                categories    = self.db.categories (item_uri   = dataset["uri"],
                                                    account_uuid = account_uuid,
                                                    is_published = False)

                return self.default_list_response (categories, formatter.format_category_record)

            except (IndexError, KeyError):
                pass

            return self.error_500 ()

        if request.method in ('PUT', 'POST'):
            try:
                parameters = request.get_json()
                categories = parameters["categories"]
                if categories is None:
                    return self.error_400 (request,
                                           "Missing 'categories' parameter.",
                                           "MissingRequiredField")

                dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                       account_uuid = account_uuid,
                                                       is_published = False)

                # First, validate all values passed by the user.
                # This way, we can be as certain as we can be that performing
                # a PUT will not end in having no categories associated with
                # a dataset.
                for index, _ in enumerate(categories):
                    categories[index] = validator.string_value (categories, index, 0, 36)

                ## Append when using POST, otherwise overwrite.
                if request.method == 'POST':
                    existing_categories = self.db.categories (item_uri     = dataset["uri"],
                                                              account_uuid = account_uuid,
                                                              is_published = False,
                                                              limit        = 10000)

                    existing_categories = list(map(lambda category: category["uuid"], existing_categories))

                    # Merge and remove duplicates
                    categories = list(dict.fromkeys(existing_categories + categories))

                categories = uris_from_records (categories, "category")
                if self.db.update_item_list (dataset["container_uuid"],
                                             account_uuid,
                                             categories,
                                             "categories"):
                    return self.respond_205()

                return self.error_500()

            except IndexError:
                return self.error_500 ()
            except KeyError:
                return self.error_400 (request, "Expected an array for 'categories'.", "NoCategoriesField")
            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

        return self.error_405 (["GET", "POST", "PUT"])

    def api_private_delete_dataset_category (self, request, dataset_id, category_id):
        """Implements /v2/account/articles/<id>/categories/<cid>."""
        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        if self.db.delete_dataset_categories (dataset_id, account_uuid, category_id):
            return self.respond_204()

        return self.error_500()

    def api_private_dataset_embargo (self, request, dataset_id):
        """Implements /v2/account/articles/<id>/embargo."""
        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':
            dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                   account_uuid = account_uuid,
                                                   is_published = False)
            if not dataset:
                return self.response ("[]")

            return self.response (json.dumps (formatter.format_dataset_embargo_record (dataset)))

        if request.method == 'DELETE':
            try:
                dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                       account_uuid = account_uuid,
                                                       is_published = False)

                if self.db.delete_dataset_embargo (dataset_uri = dataset["uri"],
                                                   account_uuid = account_uuid):
                    return self.respond_204()
            except (IndexError, KeyError):
                pass

            return self.error_500 ()

        return self.error_405 (["GET", "DELETE"])

    def api_private_dataset_files (self, request, dataset_id):
        """Implements /v2/account/articles/<id>/files."""
        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':
            try:
                dataset       = self.__dataset_by_id_or_uri (dataset_id,
                                                             account_uuid=account_uuid,
                                                             is_published=False)
                if dataset is None:
                    return self.error_403 (request)

                files = self.db.dataset_files (
                    dataset_uri = dataset["uri"],
                    account_uuid = account_uuid,
                    limit      = validator.integer_value (request.args, "limit"))

                return self.default_list_response (files, formatter.format_file_for_dataset_record)

            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)
            except (IndexError, KeyError):
                pass

            return self.error_500 ()

        if request.method == 'POST':
            parameters = request.get_json()
            try:
                link = validator.string_value (parameters, "link", 0, 1000, False)
                dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                       account_uuid=account_uuid,
                                                       is_published=False)

                if dataset is None:
                    return self.error_403 (request)

                if link is not None:
                    file_id = self.db.insert_file (
                        dataset_uri        = dataset["uri"],
                        account_uuid       = account_uuid,
                        is_link_only       = True,
                        download_url       = link)

                    if file_id is None:
                        return self.error_500()

                    return self.respond_201({
                        "location": f"{self.base_url}/v2/account/articles/{dataset_id}/files/{file_id}"
                    })

                file_id = self.db.insert_file (
                    dataset_uri   = dataset["uri"],
                    account_uuid  = account_uuid,
                    is_link_only  = False,
                    upload_token  = self.token_from_request (request),
                    supplied_md5  = validator.string_value  (parameters, "md5",  32, 32),
                    name          = validator.string_value  (parameters, "name", 0,  255,        True),
                    size          = validator.integer_value (parameters, "size", 0,  pow(2, 63), True))

                if file_id is None:
                    return self.error_500()

                return self.respond_201({
                    "location": f"{self.base_url}/v2/account/articles/{dataset_id}/files/{file_id}"
                })

            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)
            except (IndexError, KeyError):
                pass

            return self.error_500 ()

        return self.error_405 (["GET", "POST"])

    def api_private_dataset_file_details (self, request, dataset_id, file_id):
        """Implements /v2/account/articles/<id>/files/<fid>."""
        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':
            try:
                dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                       account_uuid = account_uuid,
                                                       is_published = False)

                files   = self.__file_by_id_or_uri (file_id,
                                                    account_uuid = account_uuid,
                                                    dataset_uri = dataset["uri"])

                return self.default_list_response (files, formatter.format_file_details_record)
            except (IndexError, KeyError):
                pass

            return self.error_500 ()

        if request.method == 'POST':
            return self.error_500()

        if request.method == 'DELETE':
            try:
                dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                       account_uuid=account_uuid,
                                                       is_published=False)

                if dataset is None:
                    return self.error_403 (request)

                if self.using_uwsgi:
                    uwsgi.lock()
                else:
                    self.file_list_lock.acquire(timeout=60000)

                files = self.db.dataset_files (dataset_uri  = dataset["uri"],
                                               limit        = None,
                                               account_uuid = account_uuid)
                files.remove (next (filter (lambda item: item["uuid"] == file_id, files)))
                files = list(map (lambda item: URIRef(uuid_to_uri(item["uuid"], "file")),
                                           files))

                if self.db.update_item_list (dataset["container_uuid"],
                                             account_uuid,
                                             files,
                                             "files"):
                    if self.using_uwsgi:
                        uwsgi.unlock()
                    else:
                        self.file_list_lock.release()

                    return self.respond_204()

            except (IndexError, KeyError, StopIteration):
                pass

            if self.using_uwsgi:
                uwsgi.unlock()
            else:
                self.file_list_lock.release()

            return self.error_500()

        return self.error_405 (["GET", "POST", "DELETE"])

    def api_private_dataset_private_links (self, request, dataset_id):
        """Implements /v2/account/articles/<id>/private_links."""
        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':

            dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                   account_uuid = account_uuid,
                                                   is_published = False)

            if dataset is None:
                return self.error_404 (request)

            links = self.db.private_links (item_uri   = dataset["uri"],
                                           account_uuid = account_uuid)

            return self.default_list_response (links, formatter.format_private_links_record)

        if request.method == 'POST':
            parameters = request.get_json()
            try:
                dataset      = self.__dataset_by_id_or_uri (dataset_id,
                                                            is_published = False,
                                                            account_uuid = account_uuid)
                if dataset is None:
                    return self.error_404 (request)

                id_string = secrets.token_urlsafe()
                link_uri  = self.db.insert_private_link (
                    dataset["uuid"],
                    account_uuid,
                    item_type    = "dataset",
                    expires_date = validator.string_value (parameters, "expires_date", 0, 255, False),
                    read_only    = validator.boolean_value (parameters, "read_only", False),
                    id_string    = id_string,
                    is_active    = True)

                if link_uri is None:
                    logging.error ("Creating a private link failed for %s",
                                   dataset["uuid"])
                    return self.error_500()

                links    = self.db.private_links (item_uri   = dataset["uri"],
                                                  account_uuid = account_uuid)
                links    = list(map (lambda item: URIRef(item["uri"]), links))
                links    = links + [ URIRef(link_uri) ]

                if not self.db.update_item_list (dataset["container_uuid"],
                                                 account_uuid,
                                                 links,
                                                 "private_links"):
                    logging.error("Updating private links failed for %s.",
                                  dataset["container_uuid"])

                    return self.error_500()

                return self.response(json.dumps({
                    "location": f"{self.base_url}/articles/{id_string}"
                }))

            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

        return self.error_500 ()

    def api_private_dataset_private_links_details (self, request, dataset_id, link_id):
        """Implements /v2/account/articles/<id>/private_links/<link_id>."""
        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        dataset = self.__dataset_by_id_or_uri (dataset_id,
                                               account_uuid = account_uuid,
                                               is_published = False)

        if dataset is None:
            return self.error_404 (request)

        if request.method == 'GET':
            links = self.db.private_links (
                        item_uri   = dataset["uri"],
                        id_string  = link_id,
                        account_uuid = account_uuid)

            return self.default_list_response (links, formatter.format_private_links_record)

        if request.method == 'PUT':
            parameters = request.get_json()
            try:
                result = self.db.update_private_link (
                    dataset["uri"],
                    account_uuid,
                    link_id,
                    expires_date = validator.string_value (parameters, "expires_date", 0, 255, False),
                    is_active    = validator.boolean_value (parameters, "is_active", False))

                if result is None:
                    return self.error_500()

                return self.response(json.dumps({
                    "location": f"{self.base_url}/private_datasets/{link_id}"
                }))

            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

        if request.method == 'DELETE':
            result = self.db.delete_private_links (dataset["container_uuid"],
                                                   account_uuid,
                                                   link_id)

            if result is None:
                return self.error_500()

            return self.respond_204()

        return self.error_500 ()

    def __datacite_reserve_doi (self, doi=None):
        """
        Reserve a DOI at DataCite and return its API response on success or
        None on failure.
        """

        headers = {
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/vnd.api+json"
        }
        attributes = { "doi": doi } if doi else { "prefix": self.datacite_prefix }
        json_data = { "data": { "type": "dois", "attributes": attributes } }

        try:
            response = requests.post(f"{self.datacite_url}/dois",
                                     headers = headers,
                                     auth    = (self.datacite_id,
                                                self.datacite_password),
                                     timeout = 10,
                                     json    = json_data)
            data = None
            if response.status_code == 201:
                data = response.json()
            else:
                logging.error("DataCite responded with %s", response.status_code)
            return data
        except requests.exceptions.ConnectionError:
            logging.error("Failed to reserve a DOI due to a connection error.")

        return None

    def api_private_collection_reserve_doi (self, request, collection_id):
        """Implements /v2/account/collections/<id>/reserve_doi."""

        handler = self.default_error_handling (request, "POST", "application/json")
        if handler is not None:
            return handler

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        collection = self.__collection_by_id_or_uri (collection_id,
                                                     is_published = False,
                                                     account_uuid = account_uuid)
        if collection is None:
            return self.error_403 (request)

        data = self.__datacite_reserve_doi ()
        if data is None:
            return self.error_500 ()

        reserved_doi = data["data"]["id"]
        if self.db.update_collection (collection["container_uuid"],
                                      account_uuid,
                                      doi = reserved_doi):
            return self.response (json.dumps({ "doi": reserved_doi }))

        logging.error("Updating the collection %s for reserving DOI %s failed.",
                      collection_id, reserved_doi)

        return self.error_500 ()

    def __reserve_and_save_dataset_doi (self, account_uuid, dataset):
        """Returns the reserved DOI on success or False otherwise."""

        if dataset is None or account_uuid is None:
            return False

        data = self.__datacite_reserve_doi ()
        if data is None:
            return False

        reserved_doi = data["data"]["id"]
        if self.db.update_dataset (
                dataset["container_uuid"],
                account_uuid,
                doi                         = reserved_doi,
                agreed_to_deposit_agreement = value_or (dataset, "agreed_to_deposit_agreement", False),
                agreed_to_publish           = value_or (dataset, "agreed_to_publish", False),
                is_metadata_record          = value_or (dataset, "is_metadata_record", False)):
            return reserved_doi

        logging.error("Updating the dataset %s for reserving DOI %s failed.",
                      dataset["container_uuid"], reserved_doi)

        return False

    def api_private_dataset_reserve_doi (self, request, dataset_id):
        """Implements /v2/account/articles/<id>/reserve_doi."""
        handler = self.default_error_handling (request, "POST", "application/json")
        if handler is not None:
            return handler

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        dataset = self.__dataset_by_id_or_uri (dataset_id,
                                               is_published = False,
                                               account_uuid = account_uuid)

        if dataset is None:
            return self.error_403 (request)

        reserved_doi = self.__reserve_and_save_dataset_doi (account_uuid, dataset)
        if reserved_doi:
            return self.response (json.dumps({ "doi": reserved_doi }))

        return self.error_500()

    def public_item_register_doi (self, request, item_id, version=None, item_type="dataset"):
        """Procedure to register a new doi, to be called AFTER publication of the item."""

        handler = self.default_error_handling (request, "POST", "application/json")
        if handler is not None:
            return handler

        doi, xml = self.format_datacite_for_registration(item_id, version, item_type)
        encoded_bytes = base64.b64encode(xml.encode("utf-8"))
        encoded_str = str(encoded_bytes, "utf-8")
        url = landing_page_url(item_id, version, item_type)

        try:
            headers = {
                "Accept": "application/vnd.api+json",
                "Content-Type": "application/vnd.api+json"
            }
            json_data = {
                "data": {
                    "id": doi,
                    "type": "dois",
                    "attributes": {
                        "event": "publish",
                        "doi": doi,
                        "url": url,
                        "xml": encoded_str
                    }
                }
            }
            response = requests.post(f"{self.datacite_url}/dois",
                                     headers = headers,
                                     auth    = (self.datacite_id,
                                                self.datacite_password),
                                     timeout = 10,
                                     json    = json_data)

            if response.status_code == 201:
                pass #do something here?
            else:
                logging.error("DataCite responded with %s", response.status_code)
        except requests.exceptions.ConnectionError:
            logging.error("Failed to register a DOI due to a connection error.")

        return self.error_500()

    def __update_item_doi (self, item_id, version=None, item_type="dataset"):
        """Procedure to modify metadata of an existing doi."""

        doi, xml = self.format_datacite_for_registration (item_id, version, item_type)
        encoded_bytes = base64.b64encode(xml)
        headers = {
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/vnd.api+json"
        }
        json_data = {
            "data": {
                "id": doi,
                "type": "dois",
                "attributes": {"xml": str(encoded_bytes, "utf-8")}
            }
        }

        try:
            response = requests.put(f"{self.datacite_url}/dois/{doi}",
                                    headers = headers,
                                    auth    = (self.datacite_id,
                                               self.datacite_password),
                                    timeout = 10,
                                    json    = json_data)

            if response.status_code == 201:
                return True

            logging.error("DataCite responded with %s", response.status_code)
        except requests.exceptions.ConnectionError:
            logging.error("Failed to update a DOI due to a connection error.")

        return False

    def api_private_datasets_search (self, request):
        """Implements /v2/account/articles/search."""
        handler = self.default_error_handling (request, "POST", "application/json")
        if handler is not None:
            return handler

        ## Authorization
        ## ----------------------------------------------------------------
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        try:
            if not self.contains_json (request):
                return self.error_415 ("application/json")

            parameters = request.get_json()
            offset, limit = validator.paging_to_offset_and_limit (parameters)
            group = validator.integer_value (parameters, "group")
            records = self.db.datasets(
                resource_doi    = validator.string_value (parameters, "resource_doi", 0, 512),
                # "resource_id" here is not a typo for "dataset_id".
                dataset_id      = validator.integer_value (parameters, "resource_id"),
                item_type       = validator.integer_value (parameters, "item_type"),
                doi             = validator.string_value (parameters, "doi", 0, 255),
                handle          = validator.string_value (parameters, "handle", 0, 255),
                order           = validator.string_value (parameters, "order", 0, 255),
                search_for      = validator.string_value (parameters, "search_for", 0, 512),
                limit           = limit,
                offset          = offset,
                order_direction = validator.order_direction (parameters, "order_direction"),
                institution     = validator.integer_value (parameters, "institution"),
                published_since = validator.string_value (parameters, "published_since", 0, 255),
                modified_since  = validator.string_value (parameters, "modified_since", 0, 255),
                groups          = [group] if group is not None else None,
                exclude_ids     = validator.string_value (parameters, "exclude", 0, 255),
                account_uuid    = account_uuid,
                is_published    = False
            )

            return self.default_list_response (records, formatter.format_dataset_record)

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    ## ------------------------------------------------------------------------
    ## COLLECTIONS
    ## ------------------------------------------------------------------------

    def api_collections (self, request):
        """Implements /v2/collections."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        ## Parameters
        ## ----------------------------------------------------------------
        order           = self.get_parameter (request, "order")
        order_direction = self.get_parameter (request, "order_direction")
        institution     = self.get_parameter (request, "institution")
        published_since = self.get_parameter (request, "published_since")
        modified_since  = self.get_parameter (request, "modified_since")
        group           = self.get_parameter (request, "group")
        resource_doi    = self.get_parameter (request, "resource_doi")
        doi             = self.get_parameter (request, "doi")
        handle          = self.get_parameter (request, "handle")

        try:
            offset, limit = validator.paging_to_offset_and_limit ({
                "page":      self.get_parameter (request, "page"),
                "page_size": self.get_parameter (request, "page_size"),
                "limit":     self.get_parameter (request, "limit"),
                "offset":    self.get_parameter (request, "offset")
            })

            validator.order_direction ({"order_direction": order_direction}, "order_direction")
            validator.institution (institution)
            validator.group (group)

            records = self.db.collections (limit=limit,
                                           offset=offset,
                                           order=order,
                                           order_direction=order_direction,
                                           institution=institution,
                                           published_since=published_since,
                                           modified_since=modified_since,
                                           group=group,
                                           resource_doi=resource_doi,
                                           doi=doi,
                                           handle=handle)

            return self.default_list_response (records, formatter.format_collection_record)

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    def api_collections_search (self, request):
        """Implements /v2/collections/search."""
        handler = self.default_error_handling (request, "POST", "application/json")
        if handler is not None:
            return handler

        parameters = request.get_json()
        records    = self.db.collections(
            limit           = value_or_none (parameters, "limit"),
            offset          = value_or_none (parameters, "offset"),
            order           = value_or_none (parameters, "order"),
            order_direction = value_or_none (parameters, "order_direction"),
            institution     = value_or_none (parameters, "institution"),
            published_since = value_or_none (parameters, "published_since"),
            modified_since  = value_or_none (parameters, "modified_since"),
            group           = value_or_none (parameters, "group"),
            resource_doi    = value_or_none (parameters, "resource_doi"),
            doi             = value_or_none (parameters, "doi"),
            handle          = value_or_none (parameters, "handle"),
            search_for      = value_or_none (parameters, "search_for")
        )

        return self.default_list_response (records, formatter.format_collection_record)

    def api_collection_details (self, request, collection_id):
        """Implements /v2/collections/<id>."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        collection     = self.__collection_by_id_or_uri (collection_id,
                                                         is_published=True,
                                                         is_latest=True)

        if collection is None:
            return self.error_404 (request)

        total = self.__formatted_collection_record (collection)
        return self.response (json.dumps(total))

    def api_collection_versions (self, request, collection_id):
        """Implements /v2/collections/<id>/versions."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        versions = []
        if parses_to_int (collection_id):
            versions = self.db.collection_versions (collection_id=collection_id)
        elif isinstance (collection_id, str):
            uri      = uuid_to_uri (collection_id, "container")
            versions = self.db.collection_versions (container_uri = uri)

        return self.default_list_response (versions, formatter.format_version_record)

    def api_collection_version_details (self, request, collection_id, version):
        """Implements /v2/collections/<id>/versions/<version>."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        collection     = self.__collection_by_id_or_uri (collection_id, version=version)
        if collection is None:
            return self.error_404 (request)

        total = self.__formatted_collection_record (collection)
        return self.response (json.dumps(total))

    def api_private_collections (self, request):
        """Implements /v2/collections/<id>/versions/<version>."""
        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':
            ## Parameters
            ## ----------------------------------------------------------------
            offset, limit = validator.paging_to_offset_and_limit ({
                "page":      self.get_parameter (request, "page"),
                "page_size": self.get_parameter (request, "page_size"),
                "limit":     self.get_parameter (request, "limit"),
                "offset":    self.get_parameter (request, "offset")
            })
            order           = self.get_parameter (request, "order")
            order_direction = self.get_parameter (request, "order_direction")

            ## These parameters aren't in the Figshare spec.
            institution     = self.get_parameter (request, "institution")
            published_since = self.get_parameter (request, "published_since")
            modified_since  = self.get_parameter (request, "modified_since")
            group           = self.get_parameter (request, "group")
            resource_doi    = self.get_parameter (request, "resource_doi")
            doi             = self.get_parameter (request, "doi")
            handle          = self.get_parameter (request, "handle")

            records = self.db.collections (limit=limit,
                                           offset=offset,
                                           order=order,
                                           order_direction=order_direction,
                                           institution=institution,
                                           published_since=published_since,
                                           modified_since=modified_since,
                                           group=group,
                                           resource_doi=resource_doi,
                                           doi=doi,
                                           handle=handle,
                                           account_uuid=account_uuid)

            return self.default_list_response (records, formatter.format_collection_record)

        if request.method == 'POST':
            record = request.get_json()

            try:
                tags = validator.array_value (record, "tags", False)
                if not tags:
                    tags = validator.array_value (record, "keywords", False)
                timeline   = validator.object_value (record, "timeline", False)
                collection_id, _ = self.db.insert_collection (
                    title                   = validator.string_value  (record, "title",            3, 1000,       True),
                    account_uuid            = account_uuid,
                    funding                 = validator.string_value  (record, "funding",          0, 255,        False),
                    funding_list            = validator.array_value   (record, "funding_list",                    False),
                    description             = validator.string_value  (record, "description",      0, 10000,      False),
                    datasets                = validator.array_value   (record, "articles",                        False),
                    authors                 = validator.array_value   (record, "authors",                         False),
                    categories              = validator.array_value   (record, "categories",                      False),
                    categories_by_source_id = validator.array_value   (record, "categories_by_source_id",         False),
                    tags                    = validator.array_value   (record, "tags",                            False),
                    references              = validator.array_value   (record, "references",                      False),
                    custom_fields           = validator.object_value  (record, "custom_fields",                   False),
                    custom_fields_list      = validator.object_value  (record, "custom_fields_list",              False),
                    doi                     = validator.string_value  (record, "doi",              0, 255,        False),
                    handle                  = validator.string_value  (record, "handle",           0, 255,        False),
                    url                     = validator.string_value  (record, "url",              0, 512,        False),
                    resource_id             = validator.string_value  (record, "resource_id",      0, 255,        False),
                    resource_doi            = validator.string_value  (record, "resource_doi",     0, 255,        False),
                    resource_link           = validator.string_value  (record, "resource_link",    0, 255,        False),
                    resource_title          = validator.string_value  (record, "resource_title",   0, 255,        False),
                    resource_version        = validator.integer_value (record, "resource_version", 0, pow(2, 63), False),
                    group_id                = validator.integer_value (record, "group_id",         0, pow(2, 63), False),
                    # Unpack the 'timeline' object.
                    first_online            = validator.string_value (timeline, "firstOnline",                    False),
                    publisher_publication   = validator.string_value (timeline, "publisherPublication",           False),
                    submission              = validator.string_value (timeline, "submission",                     False),
                    posted                  = validator.string_value (timeline, "posted",                         False),
                    revision                = validator.string_value (timeline, "revision",                       False))

                if collection_id is None:
                    return self.error_500 ()

                return self.response(json.dumps({
                    "location": f"{self.base_url}/v2/account/collections/{collection_id}",
                    "warnings": []
                }))
            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

        return self.error_405 (["GET", "POST"])


    def api_private_collection_details (self, request, collection_id):
        """Implements /v2/account/collections/<id>."""
        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':
            try:
                collection    = self.__collection_by_id_or_uri (collection_id,
                                                                account_uuid = account_uuid,
                                                                is_published = False)
                if collection is None:
                    return self.error_403 (request)

                total = self.__formatted_collection_record (collection)
                return self.response (json.dumps(total))

            except IndexError:
                response = self.response (json.dumps({
                    "message": "This collection cannot be found."
                }))
                response.status_code = 404
                return response

        if request.method == 'PUT':
            record = request.get_json()
            try:
                collection     = self.__collection_by_id_or_uri (collection_id,
                                                                 account_uuid = account_uuid,
                                                                 is_published = False)
                container_uuid = collection["container_uuid"]
                result = self.db.update_collection (container_uuid, account_uuid,
                    title           = validator.string_value  (record, "title",          3, 1000),
                    description     = validator.string_value  (record, "description",    0, 10000),
                    resource_doi    = validator.string_value  (record, "resource_doi",   0, 255),
                    resource_title  = validator.string_value  (record, "resource_title", 0, 255),
                    group_id        = validator.integer_value (record, "group_id",       0, pow(2, 63)),
                    time_coverage   = validator.string_value  (record, "time_coverage",  0, 512),
                    publisher       = validator.string_value  (record, "publisher",      0, 10000),
                    language        = validator.string_value  (record, "language",       0, 10000),
                    contributors    = validator.string_value  (record, "contributors",   0, 10000),
                    geolocation     = validator.string_value  (record, "geolocation",    0, 255),
                    longitude       = validator.string_value  (record, "longitude",      0, 64),
                    latitude        = validator.string_value  (record, "latitude",       0, 64),
                    organizations   = validator.string_value  (record, "organizations",  0, 512),
                    categories      = validator.array_value   (record, "categories"),
                )
                if result is None:
                    return self.error_500()

                return self.respond_205()

            except (IndexError, KeyError):
                pass
            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

            return self.error_500 ()

        if request.method == 'DELETE':
            try:
                collection = self.__collection_by_id_or_uri(
                    collection_id,
                    account_uuid = account_uuid,
                    is_published = False)

                if collection is None:
                    return self.error_404 (request)

                if self.db.delete_collection_draft (
                        container_uuid = collection["container_uuid"],
                        account_uuid   = account_uuid):
                    return self.respond_204()
            except (IndexError, KeyError):
                pass

        return self.error_500 ()

    def api_private_collections_search (self, request):
        """Implements /v2/account/collections/search."""
        handler = self.default_error_handling (request, "POST", "application/json")
        if handler is not None:
            return handler

        ## Authorization
        ## ----------------------------------------------------------------
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        parameters = request.get_json()
        records = self.db.collections(
            resource_doi    = value_or_none (parameters, "resource_doi"),
            resource_id     = value_or_none (parameters, "resource_id"),
            doi             = value_or_none (parameters, "doi"),
            handle          = value_or_none (parameters, "handle"),
            order           = value_or_none (parameters, "order"),
            search_for      = value_or_none (parameters, "search_for"),
            #page            = value_or_none (parameters, "page"),
            #page_size       = value_or_none (parameters, "page_size"),
            limit           = value_or_none (parameters, "limit"),
            offset          = value_or_none (parameters, "offset"),
            order_direction = value_or_none (parameters, "order_direction"),
            institution     = value_or_none (parameters, "institution"),
            published_since = value_or_none (parameters, "published_since"),
            modified_since  = value_or_none (parameters, "modified_since"),
            group           = value_or_none (parameters, "group"),
            account_uuid    = account_uuid
        )

        return self.default_list_response (records, formatter.format_dataset_record)

    def api_private_collection_authors (self, request, collection_id):
        """Implements /v2/account/collections/<id>/authors."""

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':
            try:
                collection = self.__collection_by_id_or_uri (collection_id,
                                                             account_uuid = account_uuid,
                                                             is_published = False)

                authors    = self.db.authors (item_uri     = collection["uri"],
                                              is_published = False,
                                              account_uuid = account_uuid,
                                              item_type    = "collection",
                                              limit        = 10000)

                return self.default_list_response (authors, formatter.format_author_record)
            except (IndexError, KeyError):
                pass

            return self.error_500 ()

        if request.method in ['POST', 'PUT']:
            ## The 'parameters' will be a dictionary containing a key "authors",
            ## which can contain multiple dictionaries of author records.
            parameters = request.get_json()

            try:
                new_authors = []
                records     = parameters["authors"]
                for record in records:
                    # The following fields are allowed:
                    # id, name, first_name, last_name, email, orcid_id, job_title.
                    #
                    # We assume values for is_active and is_public.
                    author_uuid  = validator.string_value (record, "uuid", 0, 36, False)
                    if author_uuid is None:
                        author_uuid = self.db.insert_author (
                            full_name  = validator.string_value  (record, "name",       0, 255,        False),
                            first_name = validator.string_value  (record, "first_name", 0, 255,        False),
                            last_name  = validator.string_value  (record, "last_name",  0, 255,        False),
                            email      = validator.string_value  (record, "email",      0, 255,        False),
                            orcid_id   = validator.string_value  (record, "orcid_id",   0, 255,        False),
                            job_title  = validator.string_value  (record, "job_title",  0, 255,        False),
                            is_active  = False,
                            is_public  = True,
                            created_by = account_uuid)
                        if author_uuid is None:
                            logging.error("Adding a single author failed.")
                            return self.error_500()
                    new_authors.append(URIRef(uuid_to_uri (author_uuid, "author")))

                collection = self.__collection_by_id_or_uri (collection_id,
                                                             account_uuid = account_uuid,
                                                             is_published = False)

                # The PUT method overwrites the existing authors, so we can
                # keep an empty starting list. For POST we must retrieve the
                # existing authors to preserve them.
                existing_authors = []
                if request.method == 'POST':
                    existing_authors = self.db.authors (
                        item_uri     = collection["uri"],
                        account_uuid = account_uuid,
                        item_type    = "collection",
                        is_published = False,
                        limit        = 10000)

                    existing_authors = list(map (lambda item: URIRef(uuid_to_uri(item["uuid"], "author")),
                                                 existing_authors))

                authors = existing_authors + new_authors
                if not self.db.update_item_list (uri_to_uuid (collection["container_uri"]),
                                                 account_uuid,
                                                 authors,
                                                 "authors"):
                    logging.error("Adding a single author failed.")
                    return self.error_500()

                return self.respond_205()

            except IndexError:
                return self.error_500 ()
            except KeyError:
                return self.error_400 (request, "Expected an 'authors' field.", "NoAuthorsField")
            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

        return self.error_405 ("GET")

    def api_private_collection_categories (self, request, collection_id):
        """Implements /v2/account/collections/<id>/categories."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        ## Authorization
        ## ----------------------------------------------------------------
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        try:
            collection = self.__collection_by_id_or_uri (collection_id,
                                                         account_uuid=account_uuid)

            if collection is None:
                return self.error_404 (request)

            categories = self.db.categories(item_uri   = collection["uri"],
                                            account_uuid = account_uuid)

            return self.default_list_response (categories, formatter.format_category_record)
        except (IndexError, KeyError):
            pass

        return self.error_500 ()

    def api_private_collection_datasets (self, request, collection_id):
        """Implements /v2/account/collections/<id>/articles."""
        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':
            try:
                collection = self.__collection_by_id_or_uri (collection_id,
                                                             is_published = False,
                                                             account_uuid = account_uuid)

                if collection is None:
                    return self.error_404 (request)

                datasets   = self.db.datasets (collection_uri = collection["uri"])

                return self.default_list_response (datasets, formatter.format_dataset_record)
            except (IndexError, KeyError):
                pass

            return self.error_500 ()

        if request.method in ('PUT', 'POST'):
            try:
                parameters = request.get_json()
                collection = self.__collection_by_id_or_uri (collection_id, is_published=False, account_uuid=account_uuid)

                if collection is None:
                    return self.error_404 (request)

                existing_datasets = self.db.datasets(collection_uri=collection["uri"])
                if existing_datasets:
                    existing_datasets = list(map(lambda item: item["container_uuid"],
                                                 existing_datasets))
                new_datasets = parameters["articles"]
                datasets   = existing_datasets + new_datasets

                # First, validate all values passed by the user.
                # This way, we can be as certain as we can be that performing
                # a PUT will not end in having no datasets associated with
                # a dataset.
                for index, _ in enumerate(datasets):
                    if parses_to_int (datasets[index]):
                        dataset = validator.integer_value (datasets, index)
                    else:
                        dataset = validator.string_value (datasets, index, 36, 36)

                    dataset = self.__dataset_by_id_or_uri (dataset,
                                                           is_latest    = True,
                                                           is_published = True)
                    if dataset is None:
                        return self.error_500 ()

                    datasets[index] = URIRef(dataset["container_uri"])

                if self.db.update_item_list (collection["container_uuid"],
                                             account_uuid,
                                             datasets,
                                             "datasets"):
                    self.db.cache.invalidate_by_prefix ("datasets")
                    return self.respond_205()

            except (IndexError, TypeError):
                return self.error_500 ()
            except KeyError:
                return self.error_400 (request, "Expected an array for 'articles'.", "NoArticlesField")
            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

            return self.error_500()

        return self.error_405 (["GET", "POST", "PUT"])

    def api_collection_datasets (self, request, collection_id):
        """Implements /v2/collections/<id>/articles."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        try:
            collection = self.__collection_by_id_or_uri (collection_id)
            if collection is None:
                return self.error_404 (request)

            datasets   = self.db.datasets (collection_uri = collection["uri"])
            return self.default_list_response (datasets, formatter.format_dataset_record)
        except (IndexError, KeyError):
            pass

        return self.error_500 ()

    def api_private_authors_search (self, request):
        """Implements /v2/account/authors/search."""
        handler = self.default_error_handling (request, "POST", "application/json")
        if handler is not None:
            return handler

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        try:
            parameters = request.get_json()
            records = self.db.authors(
                search_for = validator.string_value (parameters, "search", 0, 255, True)
            )

            return self.default_list_response (records, formatter.format_author_details_record)

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    def api_private_author_details (self, request, author_id):
        """Implements /v2/account/authors/<id>."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        token = self.token_from_request (request)
        if not self.db.may_administer (token):
            return self.error_403 (request)

        try:
            if parses_to_int (author_id):
                author = self.db.authors(author_id=int(author_id))[0]

            return self.response (json.dumps (formatter.format_author_details_record (author)))
        except IndexError:
            pass

        return self.error_403 (request)

    def api_private_funding_search (self, request):
        """Implements /v2/account/funding/search."""
        handler = self.default_error_handling (request, "POST", "application/json")
        if handler is not None:
            return handler

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        try:
            parameters = request.get_json()
            records = self.db.fundings(
                search_for = validator.string_value (parameters, "search", 0, 255, True)
            )

            return self.default_list_response (records, formatter.format_funding_record)

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    ## ------------------------------------------------------------------------
    ## V3 API
    ## ------------------------------------------------------------------------

    def api_v3_datasets (self, request):
        """Implements /v3/datasets."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        record = {}
        record["limit"]           = self.get_parameter (request, "limit")
        record["offset"]          = self.get_parameter (request, "offset")
        record["order"]           = self.get_parameter (request, "order")
        record["order_direction"] = self.get_parameter (request, "order_direction")
        record["institution"]     = self.get_parameter (request, "institution")
        record["published_since"] = self.get_parameter (request, "published_since")
        record["modified_since"]  = self.get_parameter (request, "modified_since")
        record["group"]           = self.get_parameter (request, "group")
        record["group_ids"]       = self.get_parameter (request, "group_ids")
        record["resource_doi"]    = self.get_parameter (request, "resource_doi")
        record["item_type"]       = self.get_parameter (request, "item_type")
        record["doi"]             = self.get_parameter (request, "doi")
        record["handle"]          = self.get_parameter (request, "handle")
        record["return_count"]    = self.get_parameter (request, "return_count")
        record["categories"]      = self.get_parameter (request, "categories")

        try:
            validator.integer_value (record, "limit")
            validator.integer_value (record, "offset")
            validator.string_value  (record, "order",           maximum_length=32)
            validator.order_direction (record, "order_direction")
            validator.integer_value (record, "institution")
            validator.string_value  (record, "published_since", maximum_length=32)
            validator.string_value  (record, "modified_since",  maximum_length=32)
            validator.integer_value (record, "group")
            validator.string_value  (record, "resource_doi",    maximum_length=255)
            validator.integer_value (record, "item_type")
            validator.string_value  (record, "doi",             maximum_length=255)
            validator.string_value  (record, "handle",          maximum_length=255)
            validator.boolean_value (record, "return_count")

            if record["categories"] is not None:
                record["categories"] = record["categories"].split(",")
                validator.array_value   (record, "categories")
                for index, _ in enumerate(record["categories"]):
                    record["categories"][index] = validator.integer_value (record["categories"], index)

            if record["group_ids"] is not None:
                record["group_ids"] = record["group_ids"].split(",")
                validator.array_value   (record, "group_ids")
                for index, _ in enumerate(record["group_ids"]):
                    record["group_ids"][index] = validator.integer_value (record["group_ids"], index)

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

        records = self.db.datasets (limit           = record["limit"],
                                    offset          = record["offset"],
                                    order           = record["order"],
                                    order_direction = record["order_direction"],
                                    institution     = record["institution"],
                                    published_since = record["published_since"],
                                    modified_since  = record["modified_since"],
                                    #group           = record["group"],
                                    groups          = record["group_ids"],
                                    resource_doi    = record["resource_doi"],
                                    item_type       = record["item_type"],
                                    doi             = record["doi"],
                                    handle          = record["handle"],
                                    categories      = record["categories"],
                                    return_count    = record["return_count"])
        if record["return_count"]:
            return self.response (json.dumps(records[0]))

        return self.default_list_response (records, formatter.format_dataset_record)

    def __api_v3_datasets_parameters (self, request, item_type):
        record = {}
        record["dataset_id"]      = self.get_parameter (request, "id")
        record["limit"]           = self.get_parameter (request, "limit")
        record["offset"]          = self.get_parameter (request, "offset")
        record["order"]           = self.get_parameter (request, "order")
        record["order_direction"] = self.get_parameter (request, "order_direction")
        record["group_ids"]       = self.get_parameter(request, "group_ids")
        record["categories"]      = self.get_parameter (request, "categories")
        record["item_type"]       = item_type

        validator.integer_value (record, "dataset_id")
        validator.integer_value (record, "limit")
        validator.integer_value (record, "offset")
        validator.string_value  (record, "order", maximum_length=32)
        validator.order_direction (record, "order_direction")
        validator.string_value  (record, "item_type", maximum_length=32)

        if item_type not in {"downloads", "views", "shares", "cites"}:
            raise validator.InvalidValue(
                field_name = "item_type",
                message = ("The last URL parameter must be one of "
                           "'downloads', 'views', 'shares' or 'cites'."),
                code    = "InvalidURLParameterValue")

        if record["categories"] is not None:
            categories = record["categories"]
            if categories == "":
                categories = None
            else:
                categories = categories.split(",")
                record["categories"] = categories
                validator.array_value   (record, "categories")
                for index, _ in enumerate(categories):
                    category_id = validator.integer_value (categories, index)
                    categories[index] = category_id
                record["categories"] = categories

        if record["group_ids"] is not None:
            record["group_ids"] = record["group_ids"].split(",")
            validator.array_value(record, "group_ids")
            for index, _ in enumerate(record["group_ids"]):
                record["group_ids"][index] = validator.integer_value(record["group_ids"], index)

        return record

    def api_v3_datasets_top (self, request, item_type):
        """Implements /v3/datasets/top/<type>."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        record = {}
        try:
            record = self.__api_v3_datasets_parameters (request, item_type)
        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

        offset, limit = validator.paging_to_offset_and_limit ({
                "page":      self.get_parameter (request, "page"),
                "page_size": self.get_parameter (request, "page_size"),
                "limit":     self.get_parameter (request, "limit"),
                "offset":    self.get_parameter (request, "offset")
            })

        if ("group_ids" in record
            and record["group_ids"] is not None
            and record["group_ids"] != ""):
            record["group_ids"] = record["group_ids"]
            validator.array_value (record, "group_ids")
            for index, _ in enumerate(record["group_ids"]):
                record["group_ids"][index] = validator.integer_value (record["group_ids"], index)

        records = self.db.dataset_statistics (
            limit           = limit,
            offset          = offset,
            order           = validator.string_value (request.args, "order", 0, 255),
            order_direction = validator.order_direction (request.args, "order_direction"),
            group_ids       = record["group_ids"],
            category_ids    = record["categories"],
            item_type       = item_type)

        return self.response (json.dumps(records))

    def api_v3_datasets_timeline (self, request, item_type):
        """Implements /v3/datasets/timeline/<type>."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        record = {}
        try:
            record = self.__api_v3_datasets_parameters (request, item_type)

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

        records = self.db.dataset_statistics_timeline (
            dataset_id      = record["dataset_id"],
            limit           = record["limit"],
            offset          = record["offset"],
            order           = record["order"],
            order_direction = record["order_direction"],
            category_ids    = record["categories"],
            item_type       = item_type)

        return self.response (json.dumps(records))

    def api_v3_dataset_git_files (self, request, dataset_id):
        """Implements /v3/datasets/<id>.git/files."""
        if request.method != "GET":
            return self.error_405 ("GET")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        dataset = self.__dataset_by_id_or_uri (dataset_id,
                                               account_uuid = account_uuid,
                                               is_published = False)

        if dataset is None:
            return self.error_404 (request)

        git_directory  = f"{self.db.storage}/{dataset['git_uuid']}.git"
        if not os.path.exists (git_directory):
            return self.response ("[]")

        git_repository = pygit2.Repository(git_directory)
        branches       = list(git_repository.branches.local)
        files          = []
        if branches:
            branch_name = branches[0]
            if "master" in branches:
                branch_name = "master"
            elif "main" in branches:
                branch_name = "main"

            files = git_repository.revparse_single(branch_name).tree
            files = [e.name for e in files]

        return self.response (json.dumps(files))

    def api_v3_dataset_publish (self, request, dataset_id):
        """Implements /v3/datasets/<id>/publish."""
        handler = self.default_error_handling (request, "POST", "application/json")
        if handler is not None:
            return handler

        token = self.token_from_cookie (request, self.impersonator_cookie_key)
        if not self.db.may_review (token):
            return self.error_403 (request)

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed (request)

        dataset = self.__dataset_by_id_or_uri (dataset_id,
                                               account_uuid = account_uuid,
                                               is_published = False)

        if dataset is None:
            return self.error_403 (request)

        container_uuid = dataset["container_uuid"]
        if "doi" not in dataset:
            reserved_doi = self.__reserve_and_save_dataset_doi (account_uuid, dataset)
            if not reserved_doi:
                logging.error ("Reserving a DOI for %s failed.", container_uuid)
                return self.error_500()

            if not self.__update_item_doi (container_uuid, item_type="dataset"):
                logging.error ("Updating the DOI for publication of %s failed.",
                               container_uuid)
                return self.error_500()

        if self.db.publish_dataset (container_uuid, account_uuid):
            subject = f"Dataset published: {container_uuid}"
            self.__send_email_to_reviewers (subject, "published_dataset_notification",
                                            dataset=dataset)
            return self.respond_201 ({
                "location": f"{self.base_url}/review/published/{dataset_id}"
            })

        return self.error_500 ()

    def api_v3_collection_publish (self, request, collection_id):
        """Implements /v3/collections/<id>/publish."""
        handler = self.default_error_handling (request, "POST", "application/json")
        if handler is not None:
            return handler

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed (request)

        collection = self.__collection_by_id_or_uri (collection_id,
                                                     account_uuid = account_uuid,
                                                     is_published = False)

        if collection is None:
            return self.error_403 (request)

        ## Do strict metadata validation.
        errors = []

        validator.string_value  (collection, "title",          3, 1000,  True, errors)
        validator.string_value  (collection, "description",    0, 10000, True, errors)
        validator.integer_value (collection, "group_id",       0, pow(2, 63), True, errors)
        validator.string_value  (collection, "time_coverage",  0, 512,   False, errors)
        validator.string_value  (collection, "publisher",      0, 10000, True, errors)
        validator.string_value  (collection, "language",       0, 10,    True, errors)

        authors = self.db.authors (item_uri  = collection["uri"],
                                   item_type = "collection")
        if not authors:
            errors.append({
                "field_name": "authors",
                "message": "The collection must have at least one author."})

        tags = self.db.tags (item_uri     = collection["uri"],
                             account_uuid = account_uuid)
        if not tags:
            errors.append({
                "field_name": "tag",
                "message": "The collection must have at least one keyword."})


        categories = self.db.categories (item_uri = collection["uri"],
                                         account_uuid = account_uuid,
                                         is_published = False)

        if not categories:
            errors.append({
                "field_name": "categories",
                "message": "Please specify at least one category."})

        ## resource_doi and resource_title are not required, but if one of
        ## the two is provided, the other must be provided as well.
        resource_doi =   validator.string_value  (collection, "resource_doi",   0, 255,   False, errors)
        resource_title = validator.string_value  (collection, "resource_title", 0, 255,   False, errors)

        if resource_doi is not None:
            validator.string_value  (collection, "resource_title", 0, 255,   True, errors)
        if resource_title is not None:
            validator.string_value  (collection, "resource_doi",   0, 255,   True, errors)

        if errors:
            return self.error_400_list (request, errors)

        ## Only continue publishing when validation went fine.
        if self.db.publish_collection (collection["container_uuid"], account_uuid):
            return self.respond_201 ({
                "location": f"{self.base_url}/published/{collection_id}"
            })

        return self.error_500 ()

    def api_v3_dataset_submit (self, request, dataset_id):
        """Implements /v3/datasets/<id>/submit-for-review."""
        handler = self.default_error_handling (request, "PUT", "application/json")
        if handler is not None:
            return handler

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        dataset = self.__dataset_by_id_or_uri (dataset_id,
                                               account_uuid = account_uuid,
                                               is_published = False)

        if dataset is None:
            return self.error_404 (request)

        record = request.get_json()
        try:
            dataset_type = validator.string_value (record, "dataset_type", 0, 512)
            ## These magic numbers are pre-determined by Figshare.
            defined_type = 0
            if dataset_type == "software":
                defined_type = 9
            elif dataset_type == "dataset":
                defined_type = 3

            errors          = []
            is_embargoed    = validator.boolean_value (record, "is_embargoed", when_none=False)
            embargo_options = validator.array_value (record, "embargo_options")
            embargo_option  = value_or_none (embargo_options, 0)
            is_restricted   = value_or (embargo_option, "id", 0) == 1000
            is_closed       = value_or (embargo_option, "id", 0) == 1001
            is_temporary_embargo = is_embargoed and not is_restricted and not is_closed
            agreed_to_deposit_agreement = validator.boolean_value (record, "agreed_to_deposit_agreement", True, False, errors)
            agreed_to_publish = validator.boolean_value (record, "agreed_to_publish", True, False, errors)

            if not agreed_to_deposit_agreement:
                errors.append({
                    "field_name": "agreed_to_deposit_agreement",
                    "message": "The dataset cannot be published without agreeing to the Deposit Agreement."
                })

            if not agreed_to_publish:
                errors.append({
                    "field_name": "agreed_to_publish",
                    "message": "The dataset cannot be published without giving the reviewer permission to do so."
                })

            authors = self.db.authors (item_uri  = dataset["uri"],
                                       item_type = "dataset")
            if not authors:
                errors.append({
                    "field_name": "authors",
                    "message": "The dataset must have at least one author."})

            tags = self.db.tags (item_uri     = dataset["uri"],
                                 account_uuid = account_uuid)
            if not tags:
                errors.append({
                    "field_name": "tag",
                    "message": "The dataset must have at least one keyword."})


            categories = self.db.categories (item_uri = dataset["uri"],
                                             account_uuid = account_uuid,
                                             is_published = False)

            if not categories:
                errors.append({
                    "field_name": "categories",
                    "message": "Please specify at least one category."})

            ## resource_doi and resource_title are not required, but if one of
            ## the two is provided, the other must be provided as well.
            resource_doi =   validator.string_value  (record, "resource_doi",   0, 255,   False, errors)
            resource_title = validator.string_value  (record, "resource_title", 0, 255,   False, errors)

            if resource_doi is not None:
                validator.string_value  (record, "resource_title", 0, 255,   True, errors)
            if resource_title is not None:
                validator.string_value  (record, "resource_doi",   0, 255,   True, errors)

            license_id = validator.integer_value (record, "license_id", 0, pow(2, 63), True, errors)
            license_url = self.db.license_url_by_id (license_id)
            parameters = {
                "container_uuid":     dataset["container_uuid"],
                "account_uuid":       account_uuid,
                "title":              validator.string_value  (record, "title",          3, 1000,  True, errors),
                "description":        validator.string_value  (record, "description",    0, 10000, True, errors),
                "resource_doi":       resource_doi,
                "resource_title":     resource_title,
                "license_url":        license_url,
                "group_id":           validator.integer_value (record, "group_id",       0, pow(2, 63), True, errors),
                "time_coverage":      validator.string_value  (record, "time_coverage",  0, 512,   False, errors),
                "publisher":          validator.string_value  (record, "publisher",      0, 10000, True, errors),
                "language":           validator.string_value  (record, "language",       0, 10,    True, errors),
                "contributors":       validator.string_value  (record, "contributors",   0, 10000, False, errors),
                "license_remarks":    validator.string_value  (record, "license_remarks",0, 10000, False, errors),
                "geolocation":        validator.string_value  (record, "geolocation",    0, 255,   False, errors),
                "longitude":          validator.string_value  (record, "longitude",      0, 64,    False, errors),
                "latitude":           validator.string_value  (record, "latitude",       0, 64,    False, errors),
                "mimetype":           validator.string_value  (record, "format",         0, 255,   False, errors),
                "data_link":          validator.string_value  (record, "data_link",      0, 255,   False, errors),
                "derived_from":       validator.string_value  (record, "derived_from",   0, 255,   False, errors),
                "same_as":            validator.string_value  (record, "same_as",        0, 255,   False, errors),
                "organizations":      validator.string_value  (record, "organizations",  0, 512,   False, errors),
                "is_embargoed":       is_embargoed,
                "is_metadata_record": validator.boolean_value (record, "is_metadata_record", when_none=False),
                "metadata_reason":    validator.string_value  (record, "metadata_reason",  0, 512),
                "embargo_until_date": validator.date_value    (record, "embargo_until_date", is_temporary_embargo, errors),
                "embargo_type":       validator.options_value (record, "embargo_type", validator.embargo_types, is_temporary_embargo, errors),
                "embargo_title":      validator.string_value  (record, "embargo_title", 0, 1000, is_embargoed, errors),
                "embargo_reason":     validator.string_value  (record, "embargo_reason", 0, 10000, is_embargoed, errors),
                "eula":               validator.string_value  (record, "eula", 0, 10000, is_restricted, errors),
                "embargo_allow_access_requests": is_restricted or is_temporary_embargo,
                "defined_type_name":  dataset_type,
                "defined_type":       defined_type,
                "agreed_to_deposit_agreement": agreed_to_deposit_agreement,
                "agreed_to_publish":  agreed_to_publish,
                "categories":         validator.array_value   (record, "categories", True, errors)
            }

            if errors:
                return self.error_400_list (request, errors)

            result = self.db.update_dataset (**parameters)
            if not result:
                return self.error_500()

            if self.db.insert_review (dataset["uri"]) is not None:
                subject = f"Request for review: {dataset['container_uuid']}"
                self.__send_email_to_reviewers (subject, "submitted_for_review_notification",
                                                dataset=dataset)
                return self.respond_204 ()

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)
        except (IndexError, KeyError):
            pass

        return self.error_500 ()

    def api_v3_dataset_upload_file (self, request, dataset_id):
        """Implements /v3/datasets/<id>/upload."""
        handler = self.default_error_handling (request, "POST", "application/json")
        if handler is not None:
            return handler

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        try:
            dataset   = self.__dataset_by_id_or_uri (dataset_id,
                                                     account_uuid=account_uuid,
                                                     is_published=False)
            if dataset is None:
                return self.error_403 (request)

            file_data = request.files['file']
            if self.using_uwsgi:
                uwsgi.lock()
            else:
                self.file_list_lock.acquire(timeout=60000)

            file_uuid = self.db.insert_file (
                name          = file_data.filename,
                size          = file_data.content_length,
                is_link_only  = 0,
                upload_url    = f"/article/{dataset_id}/upload",
                upload_token  = self.token_from_request (request),
                dataset_uri   = dataset["uri"],
                account_uuid  = account_uuid)
            if self.using_uwsgi:
                uwsgi.unlock()
            else:
                self.file_list_lock.release()

            output_filename = f"{self.db.storage}/{dataset_id}_{file_uuid}"

            file_data.save (output_filename)
            file_data.close()
            if os.name != 'nt':
                os.chmod (output_filename, 0o400)

            file_size = 0
            file_size = os.path.getsize (output_filename)

            computed_md5 = None
            md5 = hashlib.new ("md5", usedforsecurity=False)
            with open(output_filename, "rb") as stream:
                for chunk in iter(lambda: stream.read(4096), b""):
                    md5.update(chunk)
                    computed_md5 = md5.hexdigest()

            download_url = f"{self.base_url}/file/{dataset_id}/{file_uuid}"
            self.db.update_file (account_uuid, file_uuid,
                                 computed_md5 = computed_md5,
                                 download_url = download_url,
                                 filesystem_location = output_filename,
                                 file_size    = file_size)

            return self.response (json.dumps({ "location": f"{self.base_url}/v3/file/{file_uuid}" }))

        except OSError:
            logging.error ("Writing %s to disk failed.", output_filename)
            return self.error_500 ()
        except (IndexError, KeyError):
            pass

        return self.error_500 ()

    def api_v3_file (self, request, file_id):
        """Implements /v3/file/<id>."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        metadata = self.__file_by_id_or_uri (file_id, account_uuid = account_uuid)
        if metadata is None:
            return self.error_404 (request)

        try:
            return self.response (json.dumps (formatter.format_file_details_record (metadata)))
        except KeyError:
            return self.error_500()

    def __api_v3_item_references (self, request, item):
        """Implements getting/setting references for datasets and collections."""

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        if request.method not in ['GET', 'POST', 'DELETE']:
            return self.error_405 (["GET", "POST", "DELETE"])

        try:
            references     = self.db.references (item_uri     = item["uri"],
                                                 account_uuid = account_uuid)

            if request.method == 'GET':
                return self.default_list_response (references, formatter.format_reference_record)

            references     = list(map(lambda reference: reference["url"], references))

            if request.method == 'DELETE':
                url_encoded = validator.string_value (request.args, "url", 0, 1024, True)
                url         = requests.utils.unquote(url_encoded)
                references.remove (next (filter (lambda item: item == url, references)))
                if not self.db.update_item_list (item["container_uuid"],
                                                 account_uuid,
                                                 references,
                                                 "references"):
                    logging.error("Deleting a reference failed.")
                    return self.error_500()

                return self.respond_204()

            ## For POST and PUT requests, the 'parameters' will be a dictionary
            ## containing a key "references", which can contain multiple
            ## dictionaries of reference records.
            parameters     = request.get_json()
            records        = parameters["references"]
            new_references = []
            for record in records:
                new_references.append(validator.string_value (record, "url", 0, 1024, True))

            if request.method == 'POST':
                references = references + new_references

            if not self.db.update_item_list (item["container_uuid"],
                                             account_uuid,
                                             references,
                                             "references"):
                logging.error("Updating references failed.")
                return self.error_500()

            return self.respond_205()

        except IndexError:
            return self.error_500 ()
        except KeyError as error:
            logging.error ("KeyError: %s", error)
            return self.error_400 (request, "Expected a 'references' field.", "NoReferencesField")
        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    def api_v3_dataset_references (self, request, dataset_id):
        """Implements /v3/datasets/<id>/references."""

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        dataset = self.__dataset_by_id_or_uri (dataset_id,
                                               account_uuid=account_uuid,
                                               is_published=False)

        return self.__api_v3_item_references (request, dataset)

    def api_v3_collection_references (self, request, collection_id):
        """Implements /v3/datasets/<id>/references."""

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        collection = self.__collection_by_id_or_uri (collection_id,
                                                     account_uuid=account_uuid,
                                                     is_published=False)

        return self.__api_v3_item_references (request, collection)

    def __api_v3_item_tags (self, request, item_id, item_by_id_procedure):
        """Implements handling tags for both datasets and collections."""
        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        if request.method not in ['GET', 'POST', 'DELETE']:
            return self.error_405 (["GET", "POST", "DELETE"])

        try:
            item  = item_by_id_procedure (item_id,
                                          account_uuid=account_uuid,
                                          is_published=False)

            tags = self.db.tags (
                item_uri        = item["uri"],
                account_uuid    = account_uuid,
                limit           = validator.integer_value (request.args, "limit"),
                order           = validator.integer_value (request.args, "order"),
                order_direction = validator.order_direction (request.args, "order_direction"))

            if request.method == 'GET':
                return self.default_list_response (tags, formatter.format_tag_record)

            tags     = list(map(lambda tag: tag["tag"], tags))

            if request.method == 'DELETE':
                tag_encoded = validator.string_value (request.args, "tag", 0, 1024, True)
                tag         = requests.utils.unquote(tag_encoded)
                tags.remove (next (filter (lambda item: item == tag, tags)))
                if not self.db.update_item_list (item["container_uuid"],
                                                 account_uuid,
                                                 tags,
                                                 "tags"):
                    logging.error("Deleting a tag failed.")
                    return self.error_500()

                return self.respond_204()

            ## For POST and PUT requests, the 'parameters' will be a dictionary
            ## containing a key "references", which can contain multiple
            ## dictionaries of reference records.
            parameters     = request.get_json()
            tags           = parameters["tags"]
            new_tags = []
            for index, _ in enumerate(tags):
                new_tags.append(validator.string_value (tags, index, 0, 512, True))

            if request.method == 'POST':
                existing_tags = self.db.tags (item_uri   = item["uri"],
                                              account_uuid = account_uuid,
                                              limit      = 10000)

                # Drop the index field.
                existing_tags = list (map (lambda item: item["tag"], existing_tags))

                # Remove duplicates.
                tags = deduplicate_list(existing_tags + new_tags)

            if not self.db.update_item_list (item["container_uuid"],
                                             account_uuid,
                                             tags,
                                             "tags"):
                logging.error("Updating tags failed.")
                return self.error_500()

            return self.respond_205()

        except IndexError:
            return self.error_500 ()
        except KeyError as error:
            logging.error ("KeyError: %s", error)
            return self.error_400 (request, "Expected a 'tags' field.", "NoTagsField")
        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    def api_v3_collection_tags (self, request, collection_id):
        """Implements /v3/collections/<id>/tags."""
        return self.__api_v3_item_tags (request, collection_id, self.__collection_by_id_or_uri)

    def api_v3_dataset_tags (self, request, dataset_id):
        """Implements /v3/datasets/<id>/tags."""
        return self.__api_v3_item_tags (request, dataset_id, self.__dataset_by_id_or_uri)

    def api_v3_groups (self, request):
        """Implements /v3/groups."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        try:
            records = self.db.group (
                group_id        = validator.integer_value (request.args, "id"),
                parent_id       = validator.integer_value (request.args, "parent_id"),
                name            = validator.string_value  (request.args, "name", 0, 255),
                association     = validator.string_value  (request.args, "association", 0, 255),
                limit           = validator.integer_value (request.args, "limit"),
                offset          = validator.integer_value (request.args, "offset"),
                order           = validator.integer_value (request.args, "order"),
                order_direction = validator.order_direction (request.args, "order_direction"))

            return self.default_list_response (records, formatter.format_group_record)

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    def __git_create_repository (self, git_uuid):
        git_directory = f"{self.db.storage}/{git_uuid}.git"
        if not os.path.exists (git_directory):
            initial_repository = pygit2.init_repository (git_directory, True)
            if initial_repository:
                try:
                    with open (f"{git_directory}/config", "a",
                               encoding = "utf-8") as config:
                        config.write ("\n[http]\n  receivepack = true\n")
                except FileNotFoundError:
                    logging.error ("%s/.git/config does not exist.", git_directory)
                    return False
                except OSError:
                    logging.error ("Could not open %s/.git/config", git_directory)
                    return False
            else:
                return False

        return True

    def __parse_git_http_response (self, input_bytes):
        """Procedure to parse HTTP responses sent from the Git http-backend."""

        ## Only consider the HTTP headers
        headers, _, body = input_bytes.partition(b"\r\n\r\n")
        lines        = headers.decode().split("\r\n")
        output       = {}

        for line in lines:
            key, _, value = line.partition(":")
            output[key.strip()] = value.strip()

        return output, body

    def __git_passthrough (self, request):
        """Procedure to proxy Git interaction to Git's http-backend."""

        ## The wrapping in 'str' is deliberate: It copies the opaque content_type value.
        content_type = str(request.content_type)
        git_protocol = value_or (request.headers, "Git-Protocol", "version 2")

        rpc_env = {
            ## Include the regular run-time environment (PATH variable etc).
            **os.environ,

            ## Git's http-backend by default doesn't allow exposing a
            ## repository unless the file "git-daemon-export-ok" exists
            ## in the .git directory of the repository.  The following
            ## environment variable overrides this behavior.
            "GIT_HTTP_EXPORT_ALL": "1",

            ## Passthrough some HTTP information.
            "GIT_PROTOCOL":        git_protocol,
            "CONTENT_TYPE":        content_type,
            "REQUEST_METHOD":      request.method,
            "QUERY_STRING":        request.query_string,

            ## Rewrite as if the request matches the filesystem layout.
            ## It assumes the first twelve characters are: "/v3/datasets".
            "PATH_TRANSLATED":     f"{self.db.storage}{request.path[12:]}",
        }

        try:
            rpc_command   = subprocess.run(['git', 'http-backend'],
                                           stdout = subprocess.PIPE,
                                           input  = bytes(request.stream.read()),
                                           env    = rpc_env,
                                           check  = True)

            headers, body = self.__parse_git_http_response (rpc_command.stdout)
            output        = self.response (body, mimetype=None)

            ## Override response headers to use the ones Git's http-backend.
            for key, value in headers.items():
                output.headers[key] = value

            return output

        except subprocess.CalledProcessError as error:
            logging.error ("Proxying to Git failed with exit code %d", error.returncode)
            logging.error ("The command was:\n---\n%s\n---", error.cmd)
            return self.error_500()

    def api_v3_private_dataset_git_refs (self, request, git_uuid):
        """Implements /v3/datasets/<id>.git/<suffix>."""

        service = validator.string_value (request.args, "service", 0, 16)
        self.__git_create_repository (git_uuid)

        ## Used for clone and pull.
        if service == "git-upload-pack":
            return self.api_v3_private_dataset_git_upload_or_receive_pack (request, git_uuid)

        ## Used for push.
        if service == "git-receive-pack":
            return self.api_v3_private_dataset_git_upload_or_receive_pack (request, git_uuid)

        logging.error ("Unsupported Git service command: %s", service)
        return self.error_500 ()

    def api_v3_private_dataset_git_upload_or_receive_pack (self, request, git_uuid):
        """Implements /v3/datasets/<id>.git/git-[upload|receive]-pack."""

        dataset = None
        try:
            if validator.is_valid_uuid (git_uuid):
                dataset = self.db.datasets (git_uuid = git_uuid,
                                            is_published = False)[0]
        except IndexError:
            return self.error_403 (request)

        if dataset is not None:
            return self.__git_passthrough (request)

        return self.error_403 (request)

    def api_v3_profile (self, request):
        """Implements /v3/profile."""

        handler = self.default_error_handling (request, "PUT", "application/json")
        if handler is not None:
            return handler

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        try:
            record = request.get_json()
            categories = validator.array_value (record, "categories")
            if categories is not None:
                for index, _ in enumerate(categories):
                    categories[index] = validator.string_value (categories, index, 36, 36)

            if self.db.update_account (account_uuid,
                    active                = validator.integer_value (record, "active", 0, 1),
                    job_title             = validator.string_value  (record, "job_title", 0, 255),
                    email                 = validator.string_value  (record, "email", 0, 255),
                    first_name            = validator.string_value  (record, "first_name", 0, 255),
                    last_name             = validator.string_value  (record, "last_name", 0, 255),
                    location              = validator.string_value  (record, "location", 0, 255),
                    twitter               = validator.string_value  (record, "twitter", 0, 255),
                    linkedin              = validator.string_value  (record, "linkedin", 0, 255),
                    website               = validator.string_value  (record, "website", 0, 255),
                    biography             = validator.string_value  (record, "biography", 0, 32768),
                    institution_user_id   = validator.integer_value (record, "institution_user_id"),
                    institution_id        = validator.integer_value (record, "institution_id"),
                    pending_quota_request = validator.integer_value (record, "pending_quota_request"),
                    maximum_file_size     = validator.integer_value (record, "maximum_file_size"),
                    modified_date         = validator.string_value  (record, "modified_date", 0, 32),
                    categories            = categories):
                return self.respond_204 ()

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

        return self.error_500 ()

    def api_v3_profile_categories (self, request):
        """Implements /v3/profile/categories."""

        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        categories = self.db.account_categories (account_uuid)
        return self.default_list_response (categories, formatter.format_category_record)

    def api_v3_profile_quota_request (self, request):
        """Implements /v3/profile/quota-request."""

        handler = self.default_error_handling (request, "POST", "application/json")
        if handler is not None:
            return handler

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        try:
            parameters = request.get_json()
            new_quota  = validator.integer_value (parameters, "new-quota", required=True)
            reason     = validator.string_value (parameters, "reason", 0, 10000, required=True)
            account    = self.db.account_by_uuid (account_uuid)
            self.__send_email_to_quota_reviewers (
                f"Quota request for {account_uuid}",
                "quota_request",
                email     = account['email'],
                new_quota = new_quota,
                reason    = reason)

            return self.respond_204 ()
        except (validator.ValidationException, KeyError):
            pass

        return self.error_500 ()

    def api_v3_explore_types (self, request):
        """Implements /v3/explore/types."""

        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        token = self.token_from_cookie (request)
        if not self.db.may_administer (token):
            return self.error_403 (request)

        types = self.db.types ()
        types = list(map (lambda item: item["type"], types))
        return self.response (json.dumps(types))

    def api_v3_explore_properties (self, request):
        """Implements /v3/explore/properties."""

        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        token = self.token_from_cookie (request)
        if not self.db.may_administer (token):
            return self.error_403 (request)

        try:
            parameters = {}
            parameters["uri"] = self.get_parameter (request, "uri")
            uri        = validator.string_value (parameters, "uri", 0, 255)
            uri        = requests.utils.unquote(uri)
            properties = self.db.properties_for_type (uri)
            properties = list(map (lambda item: item["predicate"], properties))

            return self.response (json.dumps(properties))

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    def api_v3_explore_property_types (self, request):
        """Implements /v3/explore/property_value_types."""

        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        token = self.token_from_cookie (request)
        if not self.db.may_administer (token):
            return self.error_403 (request)

        try:
            parameters = {}
            parameters["type"]     = self.get_parameter (request, "type")
            parameters["property"] = self.get_parameter (request, "property")

            rdf_type     = validator.string_value (parameters, "type", 0, 255)
            rdf_type     = requests.utils.unquote(rdf_type)
            rdf_property = validator.string_value (parameters, "property", 0, 255)
            rdf_property = requests.utils.unquote(rdf_property)
            types        = self.db.types_for_property (rdf_type, rdf_property)
            types        = list(map (lambda item: item["type"], types))

            return self.response (json.dumps(types))

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    def api_v3_datasets_assign_reviewer (self, request, dataset_uuid, reviewer_uuid):
        """Implements /v3/datasets/<id>/assign-reviewer/<rid>."""

        if request.method != "PUT":
            return self.error_405 ("PUT")

        account_uuid = self.account_uuid_from_request (request)
        token = self.token_from_cookie (request)
        if not self.db.may_review (token):
            logging.error ("Account %d attempted a reviewer action.", account_uuid)
            return self.error_403 (request)

        reviewer = self.db.account_by_uuid (reviewer_uuid)
        dataset  = None
        try:
            dataset = self.db.datasets (dataset_uuid    = dataset_uuid,
                                        is_published    = False,
                                        is_under_review = True)[0]
        except (IndexError, TypeError):
            pass

        if dataset is None or reviewer is None:
            return self.error_403 (request)

        if self.db.update_review (dataset["review_uri"],
                                  author_account_uuid = dataset["account_uuid"],
                                  assigned_to = reviewer["uuid"],
                                  status      = "assigned"):
            return self.respond_204 ()

        return self.error_500()

    ## ------------------------------------------------------------------------
    ## EXPORTS
    ## ------------------------------------------------------------------------

    def __metadata_export_parameters (self, item_id, version=None, item_type="dataset", from_draft=False):
        """collect patameters for various export formats"""

        container_uuid = self.db.container_uuid_by_id(item_id)
        is_dataset = item_type == "dataset"
        items_function = None
        if is_dataset:
            items_function     = self.db.datasets
        else:
            items_function     = self.db.collections
        container = self.db.container(container_uuid, item_type=item_type)
        if version:
            current_version = version
        else:
            current_version = value_or(container, 'latest_published_version_number', 0)
            if from_draft:
                current_version += 1
        if from_draft:
            try:
                item = items_function (container_uuid=container_uuid,
                                       is_published=False)[0]
                item['version'] = current_version
            except IndexError:
                logging.warning ("No draft for %s.", item_id)
                return None
            published_date = date.today().isoformat()
        else:
            item = items_function (container_uuid=container_uuid,
                                   version=current_version,
                                   is_published=True)[0]
            published_date = item['published_date'][:10]
        item_uuid = item['uuid']
        item_uri = f'{item_type}:{item_uuid}'
        lat = self_or_value_or_none(item, 'latitude')
        lon = self_or_value_or_none(item, 'longitude')
        lat_valid, lon_valid = decimal_coords(lat, lon)
        coordinates = {'lat_valid': lat_valid, 'lon_valid': lon_valid}
        doi = item['doi']
        if not version and 'doi' in container:
            doi = container['doi']
        parameters = {
            'item'          : item,
            'doi'           : doi,
            'authors'       : self.db.authors(item_uri=item_uri, item_type=item_type),
            'categories'    : self.db.categories(item_uri=item_uri, limit=None),
            'tags'          : [tag['tag'] for tag in self.db.tags(item_uri=item_uri)],
            'published_year': published_date[:4],
            'published_date': published_date,
            'organizations' : self.parse_organizations(value_or(item, 'organizations', '')),
            'contributors'  : self.parse_contributors (value_or(item, 'contributors' , '')),
            'references'    : self.db.references(item_uri=item_uri, limit=None),
            'coordinates'   : coordinates
            }
        if is_dataset:
            parameters['fundings'] = self.db.fundings(item_uri=item_uri)
        return parameters

    def ui_export_datacite_dataset (self, request, dataset_id, version=None):
        """Implements /export/datacite/datasets/<id>."""
        return self.export_datacite(dataset_id, version, item_type="dataset")

    def ui_export_datacite_collection (self, request, collection_id, version=None):
        """Implements /export/datacite/collections/<id>."""
        return self.export_datacite(collection_id, version, item_type="collection")

    def export_datacite (self, item_id, version=None, item_type="dataset"):
        """export metadata in datacite format"""
        xml_string = self.format_datacite(item_id, version, item_type=item_type)
        output = self.response (xml_string, mimetype="application/xml; charset=utf-8")
        version_string = f'_v{version}' if version else ''
        output.headers["Content-disposition"] = f"attachment; filename={item_id}{version_string}_datacite.xml"
        return output

    def format_datacite(self, item_id, version=None, item_type="dataset", indent=True):
        """render metadata in datacite format"""
        parameters = self.__metadata_export_parameters(item_id, version, item_type=item_type)
        return xml_formatter.datacite(parameters, indent=indent)

    def format_datacite_for_registration(self, item_id, version=None, item_type="dataset"):
        """return doi and un-indented datacite xml separately"""
        parameters = self.__metadata_export_parameters(item_id, version, item_type=item_type, from_draft=True)
        return parameters["doi"], xml_formatter.datacite(parameters, indent=False)

    def ui_export_refworks_dataset (self, request, dataset_id, version=None):
        """export metadata in Refworks format"""
        parameters = self.__metadata_export_parameters(dataset_id, version)
        xml_string = xml_formatter.refworks(parameters)
        output = self.response (xml_string, mimetype="application/xml; charset=utf-8")
        version_string = f'_v{version}' if version else ''
        output.headers["Content-disposition"] = f"attachment; filename={dataset_id}{version_string}_refworks.xml"
        return output

    def ui_export_nlm_dataset (self, request, dataset_id, version=None):
        """export metadata in NLM format"""
        parameters = self.__metadata_export_parameters(dataset_id, version)
        xml_string = xml_formatter.nlm(parameters)
        output = self.response (xml_string, mimetype="application/xml; charset=utf-8")
        version_string = f'_v{version}' if version else ''
        output.headers["Content-disposition"] = f"attachment; filename={dataset_id}{version_string}_nlm.xml"
        return output

    def ui_export_dc_dataset (self, request, dataset_id, version=None):
        """export metadata in Dublin Core format"""
        parameters = self.__metadata_export_parameters(dataset_id, version)
        xml_string = xml_formatter.dublincore(parameters)
        output = self.response (xml_string, mimetype="application/xml; charset=utf-8")
        version_string = f'_v{version}' if version else ''
        output.headers["Content-disposition"] = f"attachment; filename={dataset_id}{version_string}_dublincore.xml"
        return output

    def ui_export_bibtex_dataset (self, request, dataset_id, version=None):
        """export metadata in bibtex format"""
        # collect rendering parameters
        parameters = self.__metadata_export_parameters(dataset_id, version=version)
        # adjust rendering parameters
        # turn authors in one string
        parameters["authors_str"] = " and ".join([f"{author['last_name']}, {author['first_name']}" for author in
                                                 parameters["authors"]])
        # turn tags into one comma delimited string
        parameters["tags_str"] = ', '.join(parameters["tags"])

        headers = {"Content-disposition": f"attachment; filename={parameters['item']['uuid']}.bib"}
        return self.__render_export_format(template_name="bibtex.bib",
                                           mimetype="text/plain; charset=utf-8",
                                           headers=headers, **parameters)

    def ui_export_refman_dataset (self, request, dataset_id, version=None):
        """export metadata in .ris format"""
        # collect rendering parameters
        parameters = self.__metadata_export_parameters(dataset_id, version=version)
        # adjust rendering parameters: use / as date separator
        parameters['published_date'] = parameters['published_date'].replace('-', '/')

        headers = {"Content-disposition": f"attachment; filename={parameters['item']['uuid']}.ris"}
        return self.__render_export_format(template_name="refman.ris",
                                           mimetype="text/plain; charset=utf-8",
                                           headers=headers, **parameters)

    def ui_export_endnote_dataset (self, request, dataset_id, version=None):
        """export metadata in .enw format"""
        # collect rendering parameters
        parameters = self.__metadata_export_parameters(dataset_id, version=version)
        # adjust rendering parameters
        # prepare Reference Type (Tag %0)
        parameters["reference_type"] = "Generic"
        if parameters["item"]["defined_type_name"] == "software":
            parameters["reference_type"] = "Computer Program"

        headers = {"Content-disposition": f"attachment; filename={parameters['item']['uuid']}.enw"}
        return self.__render_export_format(template_name="endnote.enw",
                                           mimetype="text/plain; charset=utf-8",
                                           headers=headers, **parameters)

    def ui_export_cff_dataset (self, request, dataset_id, version=None):
        """export metadata in citation file format"""
        # collect rendering parameters
        parameters = self.__metadata_export_parameters(dataset_id, version=version)
        headers = {"Content-disposition": f"attachment; filename={parameters['item']['uuid']}_citation.cff"}
        return self.__render_export_format(template_name="citation.cff",
                                           mimetype="text/plain; charset=utf-8",
                                           headers=headers, **parameters)

    def parse_organizations (self, text):
        """Obscure procedure to split organizations by semicolon."""
        return [x for x in re.split(r'\s*[;\n]\s*', text) if x != '']

    def parse_contributors (self, text):
        """Procedure to split contributors by semicolon."""
        contributors = []
        for contributor in text.split(';\n'):
            if contributor:
                parts = contributor.split(' [orcid:', 1)
                contr_dict = {'name': parts[0]}
                if parts[1:]:
                    contr_dict['orcid'] = parts[1][:-1]
                contributors.append(contr_dict)
        return contributors
