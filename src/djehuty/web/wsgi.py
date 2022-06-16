"""This module implements the API server."""

from datetime import date
import os.path
import logging
import json
import hashlib
import subprocess
import requests
import pygit2
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
from djehuty.web import database
from djehuty.utils.convenience import pretty_print_size, decimal_coords
from djehuty.utils.convenience import value_or, value_or_none
from djehuty.utils.convenience import self_or_value_or_none, parses_to_int
from djehuty.utils.constants import group_to_member, member_url_names
from djehuty.utils.rdf import uuid_to_uri, uri_to_uuid, uris_from_records


class ApiServer:
    """This class implements the API server."""

    ## INITIALISATION
    ## ------------------------------------------------------------------------

    def __init__ (self, address="127.0.0.1", port=8080):
        self.base_url         = f"http://{address}:{port}"
        self.db               = database.SparqlInterface()
        self.cookie_key       = "djehuty_session"
        self.in_production    = False

        self.orcid_client_id     = None
        self.orcid_client_secret = None
        self.orcid_endpoint      = None

        self.defined_type_options = [
            "figure", "online resource", "preprint", "book",
            "conference contribution", "media", "dataset",
            "poster", "journal contribution", "presentation",
            "thesis", "software"
        ]

        self.static_pages = {}

        ## Routes to all API calls.
        ## --------------------------------------------------------------------

        self.url_map = Map([
            ## ----------------------------------------------------------------
            ## UI
            ## ----------------------------------------------------------------
            Rule("/",                                         endpoint = "home"),
            Rule("/login",                                    endpoint = "login"),
            Rule("/logout",                                   endpoint = "logout"),
            Rule("/my/dashboard",                             endpoint = "dashboard"),
            Rule("/my/datasets",                              endpoint = "my_data"),
            Rule("/my/datasets/<article_id>/edit",            endpoint = "edit_article"),
            Rule("/my/datasets/<article_id>/delete",          endpoint = "delete_article"),
            Rule("/my/datasets/new",                          endpoint = "new_article"),
            Rule("/my/collections",                           endpoint = "my_collections"),
            Rule("/my/collections/<collection_id>/edit",      endpoint = "edit_collection"),
            Rule("/my/collections/<collection_id>/delete",    endpoint = "delete_collection"),
            Rule("/my/collections/new",                       endpoint = "new_collection"),
            Rule("/my/sessions/<session_uuid>/edit",          endpoint = "edit_session"),
            Rule("/my/sessions/<session_uuid>/delete",        endpoint = "delete_session"),
            Rule("/my/sessions/new",                          endpoint = "new_session"),
            Rule("/my/profile",                               endpoint = "profile"),
            Rule("/admin/dashboard",                          endpoint = "admin_dashboard"),
            Rule("/admin/users",                              endpoint = "admin_users"),
            Rule("/admin/impersonate/<account_id>",           endpoint = "admin_impersonate"),
            Rule("/admin/maintenance",                        endpoint = "admin_maintenance"),
            Rule("/admin/maintenance/clear-cache",            endpoint = "admin_clear_cache"),
            Rule("/admin/maintenance/clear-sessions",         endpoint = "admin_clear_sessions"),
            Rule("/portal",                                   endpoint = "portal"),
            Rule("/categories/_/<category_id>",               endpoint = "categories"),
            Rule("/category",                                 endpoint = "category"),
            Rule("/institutions/<institution_name>",          endpoint = "institution"),
            Rule("/opendap_to_doi",                           endpoint = "opendap_to_doi"),
            Rule("/articles/_/<article_id>",                  endpoint = "article_ui"),
            Rule("/articles/_/<article_id>/<version>",        endpoint = "article_ui"),
            Rule("/file/<article_id>/<file_id>",              endpoint = "download_file"),

            ## ----------------------------------------------------------------
            ## API
            ## ----------------------------------------------------------------
            Rule("/v2/account/applications/authorize",        endpoint = "authorize"),
            Rule("/v2/token",                                 endpoint = "token"),
            Rule("/v2/collections",                           endpoint = "collections"),

            ## Private institutions
            ## ----------------------------------------------------------------
            Rule("/v2/account/institution",                   endpoint = "private_institution"),
            Rule("/v2/account/institution/users/<account_id>",endpoint = "private_institution_account"),

            ## Public articles
            ## ----------------------------------------------------------------
            Rule("/v2/articles",                              endpoint = "articles"),
            Rule("/v2/articles/search",                       endpoint = "articles_search"),
            Rule("/v2/articles/<article_id>",                 endpoint = "article_details"),
            Rule("/v2/articles/<article_id>/versions",        endpoint = "article_versions"),
            Rule("/v2/articles/<article_id>/versions/<version>", endpoint = "article_version_details"),
            Rule("/v2/articles/<article_id>/versions/<version>/embargo", endpoint = "article_version_embargo"),
            Rule("/v2/articles/<article_id>/versions/<version>/confidentiality", endpoint = "article_version_confidentiality"),
            Rule("/v2/articles/<article_id>/versions/<version>/update_thumb", endpoint = "article_version_update_thumb"),
            Rule("/v2/articles/<article_id>/files",           endpoint = "article_files"),
            Rule("/v2/articles/<article_id>/files/<file_id>", endpoint = "article_file_details"),

            ## Private articles
            ## ----------------------------------------------------------------
            Rule("/v2/account/articles",                      endpoint = "private_articles"),
            Rule("/v2/account/articles/search",               endpoint = "private_articles_search"),
            Rule("/v2/account/articles/<article_id>",         endpoint = "private_article_details"),
            Rule("/v2/account/articles/<article_id>/authors", endpoint = "private_article_authors"),
            Rule("/v2/account/articles/<article_id>/authors/<author_id>", endpoint = "private_article_author_delete"),
            Rule("/v2/account/articles/<article_id>/categories", endpoint = "private_article_categories"),
            Rule("/v2/account/articles/<article_id>/categories/<category_id>", endpoint = "private_delete_article_category"),
            Rule("/v2/account/articles/<article_id>/embargo", endpoint = "private_article_embargo"),
            Rule("/v2/account/articles/<article_id>/files",   endpoint = "private_article_files"),
            Rule("/v2/account/articles/<article_id>/files/<file_id>", endpoint = "private_article_file_details"),
            Rule("/v2/account/articles/<article_id>/private_links", endpoint = "private_article_private_links"),
            Rule("/v2/account/articles/<article_id>/private_links/<link_id>", endpoint = "private_article_private_links_details"),

            ## Public collections
            ## ----------------------------------------------------------------
            Rule("/v2/collections",                           endpoint = "collections"),
            Rule("/v2/collections/search",                    endpoint = "collections_search"),
            Rule("/v2/collections/<collection_id>",           endpoint = "collection_details"),
            Rule("/v2/collections/<collection_id>/versions",  endpoint = "collection_versions"),
            Rule("/v2/collections/<collection_id>/versions/<version>", endpoint = "collection_version_details"),
            Rule("/v2/collections/<collection_id>/articles",  endpoint = "collection_articles"),

            ## Private collections
            ## ----------------------------------------------------------------
            Rule("/v2/account/collections",                   endpoint = "private_collections"),
            Rule("/v2/account/collections/search",            endpoint = "private_collections_search"),
            Rule("/v2/account/collections/<collection_id>",   endpoint = "private_collection_details"),
            Rule("/v2/account/collections/<collection_id>/authors", endpoint = "private_collection_authors"),
            Rule("/v2/account/collections/<collection_id>/authors/<author_id>", endpoint = "private_collection_author_delete"),
            Rule("/v2/account/collections/<collection_id>/categories", endpoint = "private_collection_categories"),
            Rule("/v2/account/collections/<collection_id>/articles", endpoint = "private_collection_articles"),
            Rule("/v2/account/collections/<collection_id>/articles/<article_id>", endpoint = "private_collection_article_delete"),

            ## Private authors
            Rule("/v2/account/authors/search",                endpoint = "private_authors_search"),

            ## Other
            ## ----------------------------------------------------------------
            Rule("/v2/licenses",                              endpoint = "licenses"),

            ## ----------------------------------------------------------------
            ## V3 API
            ## ----------------------------------------------------------------
            Rule("/v3/articles",                              endpoint = "v3_articles"),
            Rule("/v3/articles/top/<item_type>",              endpoint = "v3_articles_top"),
            Rule("/v3/articles/timeline/<item_type>",         endpoint = "v3_articles_timeline"),
            Rule("/v3/articles/<article_id>/upload",          endpoint = "v3_article_upload_file"),
            Rule("/v3/articles/<article_id>.git/files",       endpoint = "v3_article_git_files"),
            Rule("/v3/file/<file_id>",                        endpoint = "v3_file"),
            Rule("/v3/articles/<article_id>/references",      endpoint = "v3_article_references"),
            Rule("/v3/groups",                                endpoint = "v3_groups"),
            Rule("/v3/profile",                               endpoint = "v3_profile"),
            Rule("/v3/profile/categories",                    endpoint = "v3_profile_categories"),

            ## ----------------------------------------------------------------
            ## GIT HTTP API
            ## ----------------------------------------------------------------
            Rule("/v3/articles/<article_id>.git/info/refs",   endpoint = "v3_private_article_git_refs"),
            Rule("/v3/articles/<article_id>.git/git-upload-pack", endpoint = "v3_private_article_git_upload_pack"),
            Rule("/v3/articles/<article_id>.git/git-receive-pack", endpoint = "v3_private_article_git_receive_pack"),
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

        self.wsgi    = SharedDataMiddleware(self.__respond, self.static_roots)

        ## Disable werkzeug logging.
        ## --------------------------------------------------------------------
        werkzeug_logger = logging.getLogger('werkzeug')
        werkzeug_logger.setLevel(logging.ERROR)

    ## WSGI AND WERKZEUG SETUP.
    ## ------------------------------------------------------------------------

    def add_static_root (self, uri, path):
        if uri is not None and path is not None:
            self.static_roots = { **self.static_roots, **{ uri: path } }
            self.wsgi = SharedDataMiddleware(self.__respond, self.static_roots)

            return True

        return False

    def __call__ (self, environ, start_response):
        return self.wsgi (environ, start_response)

    def __impersonating_account (self, request):
        other_cookie_key = f"impersonator_{self.cookie_key}"
        admin_token = self.token_from_cookie (request, other_cookie_key)
        if admin_token:
            user_token = self.token_from_cookie (request)
            account = self.db.account_by_session_token (user_token)
            return account

        return None

    def __render_template (self, request, template_name, **context):
        template      = self.jinja.get_template (template_name)
        token         = self.token_from_cookie (request)
        parameters    = {
            "base_url":        self.base_url,
            "path":            request.path,
            "orcid_client_id": self.orcid_client_id,
            "is_logged_in":    self.db.is_logged_in (token),
            "may_review":      self.db.may_review (token),
            "may_administer":  self.db.may_administer (token),
            "may_impersonate":  self.db.may_impersonate (token),
            "impersonating_account": self.__impersonating_account (request)
        }
        return self.response (template.render({ **context, **parameters }),
                              mimetype='text/html; charset=utf-8')

    def __dispatch_request (self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            return getattr(self, f"api_{endpoint}")(request, **values)
        except NotFound:
            # Handle static pages.
            try:
                logging.debug ("Attempting to render static page.")
                page = self.static_pages[request.path]
                return self.__render_template (request, page)
            except TemplateNotFound:
                logging.error ("Couldn't find template '%s'.", page)
            except KeyError:
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

    def token_from_cookie (self, request, cookie_key=None):
        try:
            if cookie_key is None:
                cookie_key = self.cookie_key
            return request.cookies[cookie_key]
        except KeyError:
            return None

    ## ERROR HANDLERS
    ## ------------------------------------------------------------------------

    def error_400 (self, request, message, code):
        response = None
        if self.accepts_html (request):
            response = self.__render_template (request, "400.html", message=message)
        else:
            response = self.response (json.dumps({
                "message": message,
                "code":    code
            }))
        response.status_code = 400
        return response

    def error_403 (self, request):
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
        response = self.response (f"Acceptable methods: {allowed_methods}",
                                  mimetype="text/plain")
        response.status_code = 405
        return response

    def error_415 (self, allowed_types):
        response = self.response (f"Supported Content-Types: {allowed_types}",
                                  mimetype="text/plain")
        response.status_code = 415
        return response

    def error_406 (self, allowed_formats):
        response = self.response (f"Acceptable formats: {allowed_formats}",
                                  mimetype="text/plain")
        response.status_code = 406
        return response

    def error_500 (self):
        response = self.response ("")
        response.status_code = 500
        return response

    def error_authorization_failed (self, request):
        if self.accepts_html (request):
            response = self.__render_template (request, "403.html")
        else:
            response = self.response (json.dumps({
                "message": "Invalid or unknown session token",
                "code":    "InvalidSessionToken"
            }))

        response.status_code = 403
        return response

    def default_error_handling (self, request, method):
        if request.method != method:
            return self.error_405 (method)

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        return None

    def response (self, content, mimetype='application/json; charset=utf-8'):
        """Returns a self.response object with some tweaks."""

        output                   = Response(content, mimetype=mimetype)
        output.headers["Server"] = "4TU.ResearchData API"
        return output

    ## GENERAL HELPERS
    ## ----------------------------------------------------------------------------

    def __dataset_by_id_or_uri (self, identifier, account_id=None,
                                is_published=True, is_latest=False,
                                version = None):
        try:
            dataset = None
            if parses_to_int (identifier):
                dataset = self.db.datasets (dataset_id   = int(identifier),
                                            is_published = is_published,
                                            is_latest    = is_latest,
                                            version      = version,
                                            account_id   = account_id)[0]
            else:
                dataset = self.db.datasets (container_uuid = identifier,
                                            is_published   = is_published,
                                            is_latest      = is_latest,
                                            version        = version,
                                            account_id     = account_id)[0]

            return dataset

        except IndexError:
            return None

    def __collection_by_id_or_uri (self, identifier, account_id=None,
                                   is_published=True, is_latest=False,
                                   version = None):
        try:
            collection = None
            if parses_to_int (identifier):
                collection = self.db.collections (collection_id = int(identifier),
                                                  is_published  = is_published,
                                                  is_latest     = is_latest,
                                                  version       = version,
                                                  account_id    = account_id,
                                                  limit         = 1)[0]
            else:
                collection = self.db.collections (container_uuid = identifier,
                                                  is_published   = is_published,
                                                  is_latest      = is_latest,
                                                  version        = version,
                                                  account_id     = account_id,
                                                  limit          = 1)[0]

            return collection

        except IndexError:
            return None

    def __file_by_id_or_uri (self, identifier,
                             account_id=None,
                             article_uri=None):
        try:
            file = None
            if parses_to_int (identifier):
                file = self.db.article_files (file_id     = int(identifier),
                                              article_uri = article_uri,
                                              account_id  = account_id)[0]
            else:
                file = self.db.article_files (file_uuid   = identifier,
                                              article_uri = article_uri,
                                              account_id  = account_id)[0]

            return file

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
        validator.order_direction (record["order_direction"])
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

    ## AUTHENTICATION HANDLERS
    ## ------------------------------------------------------------------------

    def authenticate_using_orcid (self, request):
        """Returns a record upon success, None upon failure."""

        record = { "code": self.get_parameter (request, "code") }
        try:
            validator.string_value (record, "code", 0, 10, required=True)
            url_parameters = {
                "client_id":     self.orcid_client_id,
                "client_secret": self.orcid_client_secret,
                "grant_type":    "authorization_code",
                "redirect_uri":  f"{self.base_url}/login",
                "code":          record["code"]
            }
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            response = requests.post(f"{self.orcid_endpoint}/token",
                                     params  = url_parameters,
                                     headers = headers)

            if response.status_code == 200:
                return response.json()

            logging.error("ORCID response was %d", response.status_code)
            return None

        except validator.ValidationException:
            logging.error("ORCID parameter validation error")
            return None

    ## CONVENIENCE PROCEDURES
    ## ------------------------------------------------------------------------

    def accepts_html (self, request):
        acceptable = request.headers['Accept']
        if not acceptable:
            return False

        return "text/html" in acceptable

    def accepts_json (self, request):
        acceptable = request.headers['Accept']
        if not acceptable:
            return False

        return (("application/json" in acceptable) or
                ("*/*" in acceptable))

    def contains_json (self, request):
        contains = request.headers['Content-Type']
        if not contains:
            return False

        return "application/json" in contains

    def get_parameter (self, request, parameter):
        try:
            return request.form[parameter]
        except KeyError:
            return request.args.get(parameter)
        except AttributeError:
            return value_or_none (request, parameter)

    def token_from_request (self, request):
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

    def impersonated_account_id (self, request, account):
        try:
            if account["may_impersonate"]:
                ## Handle the "impersonate" URL parameter.
                impersonate = self.get_parameter (request, "impersonate")

                ## "impersonate" can also be passed in the request body.
                if impersonate is None:
                    content_type = value_or (request.headers, "Content-Type", "")
                    if "application/json" in content_type:
                        body  = request.get_json()
                        impersonate = value_or_none (body, "impersonate")

                if impersonate is not None:
                    return int(impersonate)
        except KeyError:
            return int(account["account_id"])
        except TypeError:
            return int(account["account_id"])

        return int(account["account_id"])

    def account_id_from_request (self, request):
        account_id = None
        token = self.token_from_request (request)

        ## Match the token to an account_id.  If the token does not
        ## exist, we cannot authenticate.
        try:
            account    = self.db.account_by_session_token (token)
            if account is not None:
                account_id = self.impersonated_account_id (request, account)
        except KeyError:
            logging.error("Attempt to authenticate with %s failed.", token)

        return account_id

    def default_list_response (self, records, format_function):
        output     = []
        try:
            output = list(map (format_function, records))
        except TypeError:
            logging.error("%s: A TypeError occurred.", format_function)

        return self.response (json.dumps(output))

    def respond_201 (self, body):
        output = self.response (json.dumps(body))
        output.status_code = 201
        return output

    def respond_202 (self):
        output = Response("", 202, {})
        output.headers["Server"] = "4TU.ResearchData API"
        return output

    def respond_204 (self):
        output = Response("", 204, {})
        output.headers["Server"] = "4TU.ResearchData API"
        return output

    def respond_205 (self):
        output = Response("", 205, {})
        output.headers["Server"] = "4TU.ResearchData API"
        return output

    ## API CALLS
    ## ------------------------------------------------------------------------

    def api_home (self, request):
        if self.accepts_html (request):
            return redirect ("/portal", code=301)

        return self.response (json.dumps({ "status": "OK" }))

    def api_login (self, request):
        orcid_record = self.authenticate_using_orcid (request)
        if orcid_record is None:
            return self.error_403 (request)

        orcid_uri = f"https://orcid.org/{orcid_record['orcid']}"
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        response   = redirect ("/my/dashboard", code=302)
        account_id = self.db.account_id_by_orcid (orcid_uri)

        # XXX: We could create an account for an unknown ORCID.
        #      Here we limit the system to known ORCID users.
        if account_id is None:
            return self.error_403 (request)

        token, _ = self.db.insert_session (account_id, name="Website login")
        response.set_cookie (key=self.cookie_key, value=token,
                             secure=self.in_production)
        return response

    def api_logout (self, request):
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        # When impersonating, find the admin's token,
        # and set it as the new session token.
        other_cookie_key    = f"impersonator_{self.cookie_key}"
        other_session_token = self.token_from_cookie (request, other_cookie_key)
        if other_session_token:
            response = redirect ("/admin/users", code=302)
            self.db.delete_session (self.token_from_cookie (request))
            response.set_cookie (key    = self.cookie_key,
                                 value  = other_session_token,
                                 secure = self.in_production)
            response.delete_cookie (key = other_cookie_key)
            return response

        response = redirect ("/", code=302)
        self.db.delete_session (self.token_from_cookie (request))
        response.delete_cookie (key=self.cookie_key)
        return response

    def api_admin_impersonate (self, request, account_id):
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        token = self.token_from_cookie (request)
        if not self.db.may_impersonate (token):
            return self.error_403 (request)

        # Add a secundary cookie to go back to at one point.
        response = redirect ("/my/dashboard", code=302)
        other_cookie_key = f"impersonator_{self.cookie_key}"
        response.set_cookie (key    = other_cookie_key,
                             value  = token,
                             secure = self.in_production)

        # Create a new session for the user to be impersonated as.
        new_token, _ = self.db.insert_session (int(account_id), name="Impersonation")
        response.set_cookie (key    = self.cookie_key,
                             value  = new_token,
                             secure = self.in_production)
        return response

    def api_dashboard (self, request):
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        token = self.token_from_cookie (request)
        if not self.db.is_depositor (token):
            return self.error_404 (request)

        account_id   = self.account_id_from_request (request)
        storage_used = self.db.account_storage_used (account_id)
        sessions     = self.db.sessions (account_id)
        return self.__render_template (
            request, "depositor/dashboard.html",
            storage_used = pretty_print_size (storage_used),
            sessions     = sessions)

    def api_my_data (self, request):
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        token = self.token_from_cookie (request)
        if not self.db.is_depositor (token):
            return self.error_404 (request)

        draft_datasets = self.db.datasets (account_id   = account_id,
                                           limit        = 10000,
                                           is_published = False)

        for draft_dataset in draft_datasets:
            used = 0
            if not value_or (draft_dataset, "is_metadata_record", False):
                used = self.db.dataset_storage_used (draft_dataset["container_uri"])
            draft_dataset["storage_used"] = pretty_print_size (used)

        published_datasets = self.db.datasets (account_id = account_id,
                                               is_latest  = True,
                                               limit      = 10000)

        for published_dataset in published_datasets:
            used = 0
            if not value_or (published_dataset, "is_metadata_record", False):
                used = self.db.dataset_storage_used (published_dataset["container_uri"])
            published_dataset["storage_used"] = pretty_print_size (used)

        return self.__render_template (request, "depositor/my-data.html",
                                       draft_datasets     = draft_datasets,
                                       published_datasets = published_datasets)

    def api_new_article (self, request):
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        token = self.token_from_cookie (request)
        if not self.db.is_depositor (token):
            return self.error_404 (request)

        article_id = self.db.insert_dataset(title = "Untitled item",
                                            account_id = account_id)
        if article_id is not None:
            return redirect (f"/my/datasets/{article_id}/edit", code=302)

        return self.error_500()

    def api_edit_article (self, request, article_id):
        if self.accepts_html (request):
            account_id = self.account_id_from_request (request)
            if account_id is None:
                return self.error_authorization_failed(request)

            token = self.token_from_cookie (request)
            if self.db.is_depositor (token):
                try:
                    article = self.__dataset_by_id_or_uri (article_id,
                                                           is_published = False,
                                                           account_id   = account_id)

                    categories = self.db.categories_tree ()

                    # The parent_id was pre-determined by Figshare.
                    groups = self.db.group (parent_id = 28585,
                                            order_direction = "asc",
                                            order = "id")

                    for index, _ in enumerate(groups):
                        groups[index]["subgroups"] = self.db.group (parent_id = groups[index]["id"],
                                                                    order_direction = "asc",
                                                                    order = "id")

                    return self.__render_template (request,
                                                   "depositor/edit-article.html",
                                                   container_uuid = article["container_uuid"],
                                                   article    = article,
                                                   categories = categories,
                                                   groups     = groups)
                except IndexError:
                    return self.error_403 (request)

            return self.error_404 (request)

        return self.response (json.dumps({
            "message": "This page is meant for humans only."
        }))

    def api_delete_article (self, request, article_id):
        if self.accepts_html (request):
            account_id = self.account_id_from_request (request)
            if account_id is None:
                return self.error_authorization_failed(request)

            token = self.token_from_cookie (request)
            if self.db.is_depositor (token):
                try:
                    dataset     = self.__dataset_by_id_or_uri (article_id,
                                                               account_id=account_id,
                                                               is_published=False)

                    container_uuid = uri_to_uuid (dataset["container_uri"])
                    if self.db.delete_dataset_draft (container_uuid, account_id):
                        return redirect ("/my/datasets", code=303)

                    return self.error_404 (request)
                except IndexError:
                    pass
                except KeyError:
                    pass

                return self.error_500 ()

        return self.response (json.dumps({
            "message": "This page is meant for humans only."
        }))

    def api_my_collections (self, request):
        if self.accepts_html (request):
            account_id = self.account_id_from_request (request)
            if account_id is None:
                return self.error_authorization_failed(request)

            token = self.token_from_cookie (request)
            if self.db.is_depositor (token):
                collections = self.db.collections (account_id   = account_id,
                                                   is_published = False,
                                                   limit        = 10000)

                for collection in collections:
                    count = self.db.collections_article_count(collection["uri"])
                    collection["number_of_articles"] = count

                return self.__render_template (request, "depositor/my-collections.html",
                                               collections = collections)

            return self.error_404 (request)

        return self.response (json.dumps({
            "message": "This page is meant for humans only."
        }))

    def api_edit_collection (self, request, collection_id):
        if self.accepts_html (request):
            account_id = self.account_id_from_request (request)
            if account_id is None:
                return self.error_authorization_failed(request)

            token = self.token_from_cookie (request)
            if self.db.is_depositor (token):
                try:
                    collection = self.__collection_by_id_or_uri(
                        collection_id,
                        account_id   = account_id,
                        is_published = False)

                    categories = self.db.categories_tree ()

                    # The parent_id was pre-determined by Figshare.
                    groups = self.db.group (parent_id = 28585,
                                            order_direction = "asc",
                                            order = "id")

                    for index, _ in enumerate(groups):
                        groups[index]["subgroups"] = self.db.group (
                            parent_id = groups[index]["id"],
                            order_direction = "asc",
                            order = "id")

                    return self.__render_template (
                        request,
                        "depositor/edit-collection.html",
                        collection = collection,
                        categories = categories,
                        groups     = groups)

                except IndexError:
                    return self.error_403 (request)

            return self.error_404 (request)

        return self.response (json.dumps({
            "message": "This page is meant for humans only."
        }))

    def api_new_collection (self, request):
        if self.accepts_html (request):
            account_id = self.account_id_from_request (request)
            if account_id is None:
                return self.error_authorization_failed(request)

            token = self.token_from_cookie (request)
            if self.db.is_depositor (token):
                collection_id = self.db.insert_collection(
                    title = "Untitled collection",
                    account_id = account_id)

                if collection_id is not None:
                    return redirect (f"/my/collections/{collection_id}/edit", code=302)
                return self.error_500()

            return self.error_404 (request)

        return self.response (json.dumps({
            "message": "This page is meant for humans only."
        }))

    def api_delete_collection (self, request, collection_id):
        if self.accepts_html (request):
            account_id = self.account_id_from_request (request)
            if account_id is None:
                return self.error_authorization_failed(request)

            token = self.token_from_cookie (request)
            if self.db.is_depositor (token):

                try:
                    collection = self.__collection_by_id_or_uri(
                        collection_id,
                        account_id   = account_id,
                        is_published = False)

                    # Either accessing another account's collection or
                    # trying to remove a published collection.
                    if collection is None:
                        self.error_403 (request)

                    result = self.db.delete_collection (
                        container_uuid = collection["container_uuid"],
                        account_id     = account_id)

                    if result is not None:
                        return redirect ("/my/collections", code=303)

                except IndexError:
                    pass
                except KeyError:
                    pass

                return self.error_500 ()

            return self.error_404 (request)

        return self.response (json.dumps({
            "message": "This page is meant for humans only."
        }))

    def api_edit_session (self, request, session_uuid):

        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':
            if self.accepts_html (request):
                session = self.db.sessions (account_id, session_uuid=session_uuid)[0]
                if not session["editable"]:
                    return self.error_403 (request)

                return self.__render_template (
                    request,
                    "depositor/edit-session.html",
                    session = session)

            return self.response (json.dumps({
                "message": "This page is meant for humans only."
            }))

        if request.method == 'PUT':
            try:
                parameters = request.get_json()
                name = validator.string_value (parameters, "name", 0, 255)
                if self.db.update_session (account_id, session_uuid, name):
                    return self.respond_205 ()

                return self.error_500 ()

            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

        return self.error_405 (["GET", "PUT"])

    def api_new_session (self, request):
        if self.accepts_html (request):
            account_id = self.account_id_from_request (request)
            if account_id is None:
                return self.error_authorization_failed(request)

            _, session_uuid = self.db.insert_session (account_id,
                                                      name     = "Untitled",
                                                      editable = True)
            if session_uuid is not None:
                return redirect (f"/my/sessions/{session_uuid}/edit", code=302)

            return self.error_500()

        return self.response (json.dumps({
            "message": "This page is meant for humans only."
        }))

    def api_delete_session (self, request, session_uuid):
        if self.accepts_html (request):
            account_id = self.account_id_from_request (request)
            if account_id is None:
                return self.error_authorization_failed(request)

            response   = redirect (request.referrer, code=302)
            self.db.delete_session_by_uuid (account_id, session_uuid)
            return response

        return self.response (json.dumps({
            "message": "This page is meant for humans only."
        }))

    def api_profile (self, request):
        if not self.accepts_html (request):
            return self.response (json.dumps({
                "message": "This page is meant for humans only."
            }))

        if request.method == 'GET':
            token = self.token_from_cookie (request)
            if self.db.is_depositor (token):
                try:
                    account_id = self.account_id_from_request (request)
                    return self.__render_template (
                        request, "depositor/profile.html",
                        account = self.db.accounts (account_id=account_id)[0],
                        categories = self.db.categories_tree ())
                except IndexError:
                    return self.error_404 (request)

            return self.error_403 (request)

        return self.error_405 ("GET")

    def api_admin_dashboard (self, request):
        if self.accepts_html (request):
            token = self.token_from_cookie (request)
            if self.db.may_administer (token):
                return self.__render_template (request, "admin/dashboard.html")

            return self.error_403 (request)

        return self.response (json.dumps({
            "message": "This page is meant for humans only."
        }))

    def api_admin_users (self, request):
        if self.accepts_html (request):
            token = self.token_from_cookie (request)
            if self.db.may_administer (token):
                accounts = self.db.accounts()
                return self.__render_template (
                    request, "admin/users.html",
                    accounts = accounts)

            return self.error_403 (request)

        return self.response (json.dumps({
            "message": "This page is meant for humans only."
        }))

    def api_admin_maintenance (self, request):
        if self.accepts_html (request):
            token = self.token_from_cookie (request)
            if self.db.may_administer (token):
                return self.__render_template (request, "admin/maintenance.html")

            return self.error_403 (request)

        return self.response (json.dumps({
            "message": "This page is meant for humans only."
        }))

    def api_admin_clear_cache (self, request):
        token = self.token_from_cookie (request)
        if self.db.may_administer (token):
            logging.info("Invalidating caches.")
            self.db.cache.invalidate_all ()
            return redirect ("/admin/dashboard", code=302)

        return self.error_403 (request)

    def api_admin_clear_sessions (self, request):
        token = self.token_from_cookie (request)
        if self.db.may_administer (token):
            logging.info("Invalidating sessions.")
            self.db.delete_all_sessions ()
            return redirect ("/", code=302)

        return self.error_403 (request)

    def api_portal (self, request):
        #When Djehuty is completely in production, set fromFigshare to False.
        if self.accepts_html (request):
            summary_data = self.db.repository_statistics()

            page_size = 30
            rgb_shift = ((208,0), (104,104), (0,208)) #begin and end values of r,g,b
            opa_min = 0.3                             #minimum opacity
            rgb_opa_days = (7., 21.)                  #fading times (days) for color and opacity
            fromFigshare = False                      #from Figshare API or from SPARQL query?

            fig = self.get_parameter (request, "fig") #override fromFigshare
            if fig in ('0', 'false'):
                fromFigshare = False
            if fig in ('1', 'true'):
                fromFigshare = True

            n = self.get_parameter (request, "n")     #override page_size
            if n is not None:
                page_size = int(n)

            today = date.today()
            latest = []
            try:
                if fromFigshare:
                    base = 'https://api.figshare.com/v2/articles'
                    headers = {'Content-Type': 'application/json'}
                    data = json.dumps({'page_size': page_size, 'institution_id': 898, 'order': 'published_date', 'order_direction': 'desc'})
                    records = requests.get(base, headers=headers, data=data).json()
                else:
                    records = self.db.latest_articles_portal(page_size)
                for rec in records:
                    pub_date = rec['published_date'][:10]
                    days = (today - date(*[int(x) for x in pub_date.split('-')])).days
                    #days = (today - date.fromisoformat(pub_date)).days  #newer Python versions
                    ago = ('today','yesterday')[days] if days < 2 else f'{days} days ago'
                    x, y = [min(1., days/d) for d in rgb_opa_days]
                    rgba = [round(i[0] + x*(i[1]-i[0])) for i in rgb_shift] + [round(1 - y*(1-opa_min), 3)]
                    str_rgba = ','.join([str(c) for c in rgba])
                    url = rec['url_public_html'] if fromFigshare else f'/articles/_/{rec["article_id"]}'
                    latest.append((url, rec['title'], pub_date, ago, str_rgba))
            except:
                pass

            return self.__render_template (request, "portal.html",
                                           summary_data=summary_data,
                                           latest = latest)

        return self.response (json.dumps({
            "message": "This page is meant for humans only."
        }))

    def api_categories (self, request, category_id):
        if self.accepts_html (request):
            category      = self.db.category_by_id (category_id)
            subcategories = self.db.subcategories_for_category (category_id)
            articles      = self.db.datasets (categories=[category_id], limit=100)

            return self.__render_template (request, "categories.html",
                                           articles=articles,
                                           category=category,
                                           subcategories=subcategories)
        return self.response (json.dumps({
            "message": "This page is meant for humans only."
        }))

    def api_article_ui (self, request, article_id, version=None):
        if self.accepts_html (request):
            container     = self.db.article_container(article_id=article_id)[0]
            versions      = self.db.dataset_versions(article_id=article_id)
            versions      = [v for v in versions if v['version']] # exclude version None (still necessary?)
            current_version = version if version else versions[0]['version']
            article       = self.db.datasets (dataset_id    = article_id,
                                              version       = current_version,
                                              is_published  = True)[0]
            article_uri   = article['uri']
            authors       = self.db.authors(item_uri=article_uri)
            files         = self.db.article_files(article_uri=article_uri, limit=None)
            custom_fields = self.db.custom_fields(item_uri=article_uri)
            embargo_options = None #TODO
            tags          = self.db.tags(item_uri=article_uri)
            categories    = self.db.categories(item_uri=article_uri)
            references    = self.db.references(item_uri=article_uri)
            derived_from  = self.db.derived_from(item_uri=article_uri)
            fundings      = self.db.fundings(item_uri=article_uri)
            collections   = self.db.collections_from_article(article_id=article_id)
            statistics    = {'downloads': value_or(container, 'total_downloads', 0),
                             'views'    : value_or(container, 'total_views'    , 0),
                             'shares'   : value_or(container, 'total_shares'   , 0),
                             'cites'    : value_or(container, 'total_cites'    , 0)}
            statistics    = {key:val for (key,val) in statistics.items() if val > 0}
            member = value_or(group_to_member, article["group_id"], 'other')
            member_url_name = member_url_names[member]
            tags = set([t['tag'] for t in tags if not t['tag'].startswith('Collection: ')])
            article['timeline_first_online'] = container['first_online_date']
            date_types = ( ('submitted'   , 'timeline_submission'),
                           ('first online', 'timeline_first_online'),
                           ('published'   , 'published_date'),
                           ('posted'      , 'timeline_posted'),
                           ('revised'     , 'timeline_revision') )
            dates = {}
            for (label, dtype) in date_types:
                if dtype in article:
                    date = article[dtype]
                    if date:
                        date = date[:10]
                        if not date in dates:
                            dates[date] = []
                        dates[date].append(label)
            dates = [ (label, ', '.join(val)) for (label,val) in dates.items() ]

            id_v = f'{article_id}/{version}' if version else f'{article_id}'
            export_base = f'/datasets/{id_v}/exports/'

            lat = self_or_value_or_none(article, 'latitude')
            lon = self_or_value_or_none(article, 'longitude')
            lat_valid, lon_valid = decimal_coords(lat, lon)
            coordinates = {'lat': lat, 'lon': lon, 'lat_valid': lat_valid, 'lon_valid': lon_valid}

            odap_files = [(f, f['download_url'].split('/')[2]=='opendap.4tu.nl') for f in files]
            opendap = [f['download_url'] for (f, odap) in odap_files if odap]
            files_services = [(f, f['is_link_only']) for (f, odap) in odap_files if not odap]
            services = [f['download_url'] for (f, link) in files_services if link]
            files = [f for (f, link) in files_services if not link]
            if 'data_link' in article:
                url = article['data_link']
                if url.split('/')[2]=='opendap.4tu.nl':
                    opendap.append(url)
                    del article['data_link']

            contributors = []
            if 'contributors' in article:
                contr = article['contributors'].split(';\\n')
                contr_parts = [ c.split(' [orcid:') for c in contr ]
                contributors = contr_parts
                contributors = [ {'name': c[0], 'orcid': c[1][:-1] if c[1:] else None} for c in contr_parts]

            return self.__render_template (request, "article.html",
                                           article=article,
                                           version=version,
                                           versions=versions,
                                           authors=authors,
                                           contributors = contributors,
                                           files=files,
                                           services=services,
                                           custom_fields=custom_fields, #needed? Duplicated in article?
                                           embargo_options=embargo_options,
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
                                           export_base = export_base,
                                           opendap=opendap,
                                           statistics=statistics)
        return self.response (json.dumps({
            "message": "This page is meant for humans only."
        }))

    def api_institution (self, request, institution_name):
        if self.accepts_html (request):
            group_name    = institution_name.replace('_', ' ')
            group         = self.db.group_by_name (group_name)
            sub_groups    = self.db.group_by_name (group_name, startswith=True)
            sub_group_ids = [item['group_id'] for item in sub_groups]
            articles      = self.db.datasets (groups=sub_group_ids, is_published=True, limit=100)

            return self.__render_template (request, "institutions.html",
                                           articles=articles,
                                           group=group,
                                           sub_groups=sub_groups)
        return self.response (json.dumps({
            "message": "This page is meant for humans only."
        }))

    def api_category (self, request):
        if self.accepts_html (request):
            categories    = self.db.root_categories ()
            for category in categories:
                category_id = category["id"]
                category["articles"] = self.db.datasets (categories=[category_id], limit=5)

            return self.__render_template (request, "category.html",
                                           categories=categories)

        return self.response (json.dumps({
            "message": "This page is meant for humans only."
        }))

    def api_opendap_to_doi(self, request):
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

        return self.response (json.dumps({
            "message": "This page is meant for humans only."
        }))

    def api_download_file (self, request, article_id, file_id):
        try:
            article  = self.__dataset_by_id_or_uri (article_id)

            ## When downloading a file from an article that isn't published,
            ## we need to authorize it first.
            if article is None:
                account_id = self.account_id_from_request (request)
                if account_id is not None:
                    article = self.__dataset_by_id_or_uri (article_id,
                                                           account_id   = account_id,
                                                           is_published = False)

            ## Check again whether a private article has been found.
            if article is None:
                return self.error_404 (request)

            metadata = self.__file_by_id_or_uri (file_id,
                                                 article_uri = article["uri"])

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

    def api_authorize (self, request):
        return self.error_404 (request)

    def api_token (self, request):
        return self.error_404 (request)

    def api_private_institution (self, request):
        handler = self.default_error_handling (request, "GET")
        if handler is not None:
            return handler

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        ## Our API only contains data from 4TU.ResearchData.
        return self.response (json.dumps({
            "id": 898,
            "name": "4TU.ResearchData"
        }))

    def api_private_institution_account (self, request, account_id):
        handler = self.default_error_handling (request, "GET")
        if handler is not None:
            return handler

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        account   = self.db.account_by_id (account_id)
        formatted = formatter.format_account_record(account)

        return self.response (json.dumps (formatted))

    def api_articles (self, request):
        if request.method != 'GET':
            return self.error_405 ("GET")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Parameters
        ## ----------------------------------------------------------------
        try:
            record  = self.__default_dataset_api_parameters (request)
            records = self.db.datasets (**record, is_latest = 1)
            return self.default_list_response (records, formatter.format_article_record)

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    def api_articles_search (self, request):
        if request.method != 'POST':
            return self.error_405 ("POST")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        try:
            record  = self.__default_dataset_api_parameters (request.get_json())
            records = self.db.datasets (**record)
            return self.default_list_response (records, formatter.format_article_record)
        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    def api_licenses (self, request):
        handler = self.default_error_handling (request, "GET")
        if handler is not None:
            return handler

        records = self.db.licenses()
        return self.default_list_response (records, formatter.format_license_record)

    def api_article_details (self, request, article_id):
        if request.method != 'GET':
            return self.error_405 ("GET")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        try:
            article         = self.__dataset_by_id_or_uri (article_id, account_id=None, is_latest=True)
            article_uri     = article["uri"]
            authors         = self.db.authors(item_uri=article_uri, item_type="article")
            files           = self.db.article_files(article_uri=article_uri)
            custom_fields   = self.db.custom_fields(item_uri=article_uri, item_type="article")
            tags            = self.db.tags(item_uri=article_uri, item_type="article")
            categories      = self.db.categories(item_uri=article_uri)
            references      = self.db.references(item_uri=article_uri)
            funding_list    = self.db.fundings(item_uri=article_uri, item_type="article")
            total         = formatter.format_article_details_record (article,
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
                            "value": self.db.derived_from(item_uri=article_uri)} )
            total['custom_fields'] = custom
            return self.response (json.dumps(total))
        except IndexError:
            response = self.response (json.dumps({
                "message": "This article cannot be found."
            }))
            response.status_code = 404
            return response

    def api_article_versions (self, request, article_id):
        handler = self.default_error_handling (request, "GET")
        if handler is not None:
            return handler

        versions = []
        if parses_to_int (article_id):
            versions = self.db.dataset_versions (article_id=article_id)
        elif isinstance (article_id, str):
            uri      = uuid_to_uri (article_id, "container")
            versions = self.db.dataset_versions (container_uri = uri)

        return self.default_list_response (versions, formatter.format_version_record)

    def api_article_version_details (self, request, article_id, version):
        if request.method != 'GET':
            return self.error_405 ("GET")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        try:
            article       = self.__dataset_by_id_or_uri (article_id,
                                                         is_published = True,
                                                         version = version)

            article_uri   = article["uri"]
            authors       = self.db.authors(item_uri=article_uri, item_type="article")
            files         = self.db.article_files(article_uri=article_uri)
            custom_fields = self.db.custom_fields(item_uri=article_uri, item_type="article")
            tags          = self.db.tags(item_uri=article_uri, item_type="article")
            categories    = self.db.categories(item_uri=article_uri)
            references    = self.db.references(item_uri=article_uri)
            fundings      = self.db.fundings(item_uri=article_uri, item_type="article")
            total         = formatter.format_article_details_record (article,
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
                "message": "This article cannot be found."
            }))
            response.status_code = 404
            return response

    def api_article_version_embargo (self, request, article_id, version):
        if request.method != 'GET':
            return self.error_405 ("GET")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        try:
            article = self.__dataset_by_id_or_uri (article_id,
                                                   version      = version,
                                                   is_published = True)
            total   = formatter.format_article_embargo_record (article)
            return self.response (json.dumps(total))
        except IndexError:
            response = self.response (json.dumps({
                "message": "This article cannot be found."
            }))
            response.status_code = 404
            return response

    def api_article_version_confidentiality (self, request, article_id, version):
        if request.method != 'GET':
            return self.error_405 ("GET")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        try:
            article       = self.db.articles (article_id  = article_id,
                                              version     = version,
                                              is_editable = 0,
                                              is_public   = 1)[0]
            total           = formatter.format_article_confidentiality_record (article)
            return self.response (json.dumps(total))
        except IndexError:
            response = self.response (json.dumps({
                "message": "This article cannot be found."
            }))
            response.status_code = 404
            return response

    def api_article_version_update_thumb (self, request, article_id, version):
        if request.method != 'PUT':
            return self.error_405 ("PUT")

        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        parameters = request.get_json()
        file_id    = value_or_none (parameters, "file_id")
        if not self.db.article_update_thumb (article_id, version, account_id, file_id):
            return self.respond_205()

        return self.error_500()

    def api_article_files (self, request, article_id):
        if request.method != 'GET':
            return self.error_405 ("GET")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        article = self.__dataset_by_id_or_uri (article_id, is_published=True)
        files   = self.db.article_files (article_uri=article["uri"])

        return self.default_list_response (files, formatter.format_file_for_article_record)

    def api_article_file_details (self, request, article_id, file_id):
        if request.method != 'GET':
            return self.error_405 ("GET")
        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        try:
            article = self.__dataset_by_id_or_uri (article_id, is_published=True)
            files   = self.__file_by_id_or_uri (file_id,
                                                article_uri = article["uri"])

            results = formatter.format_file_for_article_record (files)
            return self.response (json.dumps(results))
        except IndexError:
            response = self.response (json.dumps({
                "message": "This file cannot be found."
            }))
            response.status_code = 404
            return response


    def api_private_articles (self, request):
        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
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
                                            account_id=account_id)

                return self.default_list_response (records, formatter.format_article_record)

            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

        if request.method == 'POST':
            record = request.get_json()

            try:
                timeline   = validator.object_value (record, "timeline", False)
                dataset_uuid = self.db.insert_dataset (
                    title          = validator.string_value  (record, "title",          3, 1000,                   True),
                    account_id     = account_id,
                    description    = validator.string_value  (record, "description",    0, 10000,                  False),
                    tags           = validator.array_value   (record, "tags",                                      False),
                    keywords       = validator.array_value   (record, "keywords",                                  False),
                    references     = validator.array_value   (record, "references",                                False),
                    categories     = validator.array_value   (record, "categories",                                False),
                    authors        = validator.array_value   (record, "authors",                                   False),
                    defined_type   = validator.options_value (record, "defined_type",   self.defined_type_options, False),
                    funding        = validator.string_value  (record, "funding",        0, 255,                    False),
                    funding_list   = validator.array_value   (record, "funding_list",                              False),
                    license_id     = validator.integer_value (record, "license",        0, pow(2, 63),             False),
                    doi            = validator.string_value  (record, "doi",            0, 255,                    False),
                    handle         = validator.string_value  (record, "handle",         0, 255,                    False),
                    resource_doi   = validator.string_value  (record, "resource_doi",   0, 255,                    False),
                    resource_title = validator.string_value  (record, "resource_title", 0, 255,                    False),
                    group_id       = validator.integer_value (record, "group_id",       0, pow(2, 63),             False),
                    custom_fields  = validator.object_value  (record, "custom_fields",                             False),
                    # Unpack the 'timeline' object.
                    first_online          = validator.string_value (timeline, "firstOnline",                       False),
                    publisher_publication = validator.string_value (timeline, "publisherPublication",              False),
                    publisher_acceptance  = validator.string_value (timeline, "publisherAcceptance",               False),
                    submission            = validator.string_value (timeline, "submission",                        False),
                    posted                = validator.string_value (timeline, "posted",                            False),
                    revision              = validator.string_value (timeline, "revision",                          False)
                )

                return self.response(json.dumps({
                    "location": f"{self.base_url}/v2/account/articles/{dataset_uuid}",
                    "warnings": []
                }))
            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

        return self.error_405 (["GET", "POST"])

    def api_private_article_details (self, request, article_id):

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':
            try:
                article     = self.__dataset_by_id_or_uri (article_id,
                                                           account_id=account_id,
                                                           is_published=False)

                if not article:
                    return self.response (json.dumps([]))

                article_uri     = article["uri"]
                authors         = self.db.authors(item_uri=article_uri, item_type="article")
                files           = self.db.article_files(article_uri=article_uri)
                custom_fields   = self.db.custom_fields(item_uri=article_uri, item_type="article")
                tags            = self.db.tags(item_uri=article_uri, item_type="article")
                categories      = self.db.categories(item_uri=article_uri)
                references      = self.db.references(item_uri=article_uri)
                funding_list    = self.db.fundings(item_uri=article_uri, item_type="article")
                total           = formatter.format_article_details_record (article,
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
                                "value": self.db.derived_from(item_uri=article_uri)} )
                total['custom_fields'] = custom
                return self.response (json.dumps(total))
            except IndexError:
                response = self.response (json.dumps({
                    "message": "This article cannot be found."
                }))
                response.status_code = 404
                return response

        if request.method == 'PUT':
            record = request.get_json()
            try:
                defined_type_name = validator.string_value (record, "defined_type_name", 0, 512)
                ## These magic numbers are pre-determined by Figshare.
                defined_type = 0
                if defined_type_name == "software":
                    defined_type = 9
                elif defined_type_name == "dataset":
                    defined_type = 3

                article = self.__dataset_by_id_or_uri (article_id,
                                                       account_id = account_id,
                                                       is_published = False)

                result = self.db.update_article (uri_to_uuid (article["container_uri"]),
                    account_id,
                    title           = validator.string_value  (record, "title",          3, 1000),
                    description     = validator.string_value  (record, "description",    0, 10000),
                    resource_doi    = validator.string_value  (record, "resource_doi",   0, 255),
                    resource_title  = validator.string_value  (record, "resource_title", 0, 255),
                    license_id      = validator.integer_value (record, "license_id",     0, pow(2, 63)),
                    group_id        = validator.integer_value (record, "group_id",       0, pow(2, 63)),
                    time_coverage   = validator.string_value  (record, "time_coverage",  0, 10000),
                    publisher       = validator.string_value  (record, "publisher",      0, 10000),
                    language        = validator.string_value  (record, "language",       0, 10000),
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
                    is_embargoed    = validator.boolean_value (record, "is_embargoed"),
                    embargo_until_date = validator.string_value (record, "embargo_until_date", 0, 20),
                    embargo_type    = validator.string_value (record, "embargo_type", 0, 32),
                    embargo_title   = validator.string_value (record, "embargo_title", 0, 1000),
                    embargo_reason  = validator.string_value (record, "embargo_reason", 0, 10000),
                    embargo_allow_access_requests = validator.integer_value (record, "embargo_allow_access_requests", 0, 2),
                    defined_type_name = defined_type_name,
                    defined_type    = defined_type,
                    categories      = validator.array_value   (record, "categories"),
                )
                if not result:
                    return self.error_500()

                return self.respond_205()

            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)
            except IndexError:
                pass
            except KeyError:
                pass

            return self.error_500 ()

        if request.method == 'DELETE':
            try:
                dataset     = self.__dataset_by_id_or_uri (article_id,
                                                           account_id=account_id,
                                                           is_published=False)

                container_uuid = uri_to_uuid (dataset["container_uri"])
                if self.db.delete_dataset_draft (container_uuid, account_id):
                    return self.respond_204()
            except IndexError:
                pass
            except KeyError:
                pass

            return self.error_500 ()

        return self.error_405 (["GET", "PUT", "DELETE"])

    def api_private_article_authors (self, request, article_id):
        """Implements /v2/account/articles/<id>/authors."""

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':
            try:
                article = self.__dataset_by_id_or_uri (article_id,
                                                       account_id=account_id,
                                                       is_published=False)

                authors = self.db.authors (item_uri   = article["uri"],
                                           account_id = account_id,
                                           is_published = False,
                                           item_type  = "article",
                                           limit      = 10000)

                return self.default_list_response (authors, formatter.format_author_record)
            except IndexError:
                pass
            except KeyError:
                pass
            except TypeError:
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
                            is_public  = True)
                        if author_uuid is None:
                            logging.error("Adding a single author failed.")
                            return self.error_500()
                    new_authors.append(URIRef(uuid_to_uri (author_uuid, "author")))

                article = self.__dataset_by_id_or_uri (article_id,
                                                       account_id=account_id,
                                                       is_published=False)

                # The PUT method overwrites the existing authors, so we can
                # keep an empty starting list. For POST we must retrieve the
                # existing authors to preserve them.
                existing_authors = []
                if request.method == 'POST':
                    existing_authors = self.db.authors (
                        item_uri     = article["uri"],
                        account_id   = account_id,
                        item_type    = "article",
                        is_published = False,
                        limit        = 10000)

                    existing_authors = list(map (lambda item: URIRef(uuid_to_uri(item["uuid"], "author")),
                                                 existing_authors))

                authors = existing_authors + new_authors
                if not self.db.update_item_list (uri_to_uuid (article["container_uri"]),
                                                 account_id,
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
            except Exception as error:
                logging.error("An error occurred when adding an author record:")
                logging.error("Exception: %s", error)

            return self.error_500()

        return self.error_405 ("GET")

    def api_private_article_author_delete (self, request, article_id, author_id):
        if request.method != 'DELETE':
            return self.error_405 ("DELETE")

        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        try:
            article   = self.__dataset_by_id_or_uri (article_id,
                                                     account_id   = account_id,
                                                     is_published = False)

            authors = self.db.authors (item_uri     = article["uri"],
                                       account_id   = account_id,
                                       is_published = False,
                                       item_type    = "article",
                                       limit        = 10000)

            if parses_to_int (author_id):
                authors.remove (next (filter (lambda item: item['id'] == author_id, authors)))
            else:
                authors.remove (next (filter (lambda item: item['uuid'] == author_id, authors)))

            authors = list(map (lambda item: URIRef(uuid_to_uri(item["uuid"], "author")), authors))
            if self.db.update_item_list (uri_to_uuid (article["container_uri"]),
                                         account_id,
                                         authors,
                                         "authors"):
                return self.respond_204()

            return self.error_500()
        except IndexError:
            return self.error_500 ()
        except KeyError:
            return self.error_500 ()

        return self.error_403 (request)

    def api_private_collection_author_delete (self, request, collection_id, author_id):
        if request.method != 'DELETE':
            return self.error_405 ("DELETE")

        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        try:
            collection = self.__collection_by_id_or_uri (collection_id,
                                                         account_id  = account_id,
                                                         is_published = False)

            authors    = self.db.authors (item_uri     = collection["uri"],
                                          account_id   = account_id,
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
                                         account_id,
                                         authors,
                                         "authors"):
                return self.respond_204()

            return self.error_500()
        except IndexError:
            return self.error_500 ()
        except KeyError:
            return self.error_500 ()

        return self.error_403 (request)

    def api_private_collection_article_delete (self, request, collection_id, article_id):
        if request.method != 'DELETE':
            return self.error_405 ("DELETE")

        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        try:
            collection = self.__collection_by_id_or_uri (collection_id, account_id=account_id)
            article    = self.__dataset_by_id_or_uri (article_id, account_id=account_id)
            if collection is None or article is None:
                return self.error_404 (request)

            articles = self.db.datasets(collection_uri=collection["uri"])
            articles.remove (next
                             (filter
                              (lambda item: item["uuid"] == article["uuid"],
                               articles)))

            articles = list(map(lambda item: URIRef(uuid_to_uri(item["uuid"], "article")),
                                articles))

            if self.db.update_item_list (collection["container_uuid"],
                                         account_id,
                                         articles,
                                         "articles"):
                return self.respond_204()
        except IndexError:
            return self.error_500 ()
        except KeyError:
            return self.error_500 ()

        return self.error_403 (request)

    def api_private_article_categories (self, request, article_id):

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':
            try:
                article       = self.__dataset_by_id_or_uri (article_id,
                                                             account_id=account_id,
                                                             is_published=False)

                categories    = self.db.categories (item_uri   = article["uri"],
                                                    account_id = account_id,
                                                    is_published = False)

                return self.default_list_response (categories, formatter.format_category_record)

            except IndexError:
                pass
            except KeyError:
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

                article = self.__dataset_by_id_or_uri (article_id,
                                                       account_id = account_id,
                                                       is_published = False)

                # First, validate all values passed by the user.
                # This way, we can be as certain as we can be that performing
                # a PUT will not end in having no categories associated with
                # an article.
                for index, _ in enumerate(categories):
                    categories[index] = validator.string_value (categories, index, 0, 36)

                ## Append when using POST, otherwise overwrite.
                if request.method == 'POST':
                    existing_categories = self.db.categories (item_uri     = article["uri"],
                                                              account_id   = account_id,
                                                              is_published = False,
                                                              limit        = 10000)

                    existing_categories = list(map(lambda category: category["uuid"], existing_categories))

                    # Merge and remove duplicates
                    categories = list(dict.fromkeys(existing_categories + categories))

                categories = uris_from_records (categories, "category")
                if self.db.update_item_list (article["container_uuid"],
                                             account_id,
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
            except Exception as error:
                logging.error("An error occurred when adding a category record:")
                logging.error("Exception: %s", error)

        return self.error_405 (["GET", "POST", "PUT"])

    def api_private_delete_article_category (self, request, article_id, category_id):

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        if self.db.delete_article_categories (article_id, account_id, category_id):
            return self.respond_204()

        return self.error_500()

    def api_private_article_embargo (self, request, article_id):
        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':
            article = self.__dataset_by_id_or_uri (article_id,
                                                   account_id = account_id,
                                                   is_published = False)
            if not article:
                return self.response (json.dumps([]))

            return self.response (json.dumps (formatter.format_article_embargo_record (article)))

        if request.method == 'DELETE':
            try:
                article = self.__dataset_by_id_or_uri (article_id,
                                                       account_id = account_id,
                                                       is_published = False)

                if self.db.delete_article_embargo (article_uri = article["uri"],
                                                   account_id  = account_id):
                    return self.respond_204()
            except IndexError:
                pass
            except KeyError:
                pass

            return self.error_500 ()

        return self.error_405 (["GET", "DELETE"])

    def api_private_article_files (self, request, article_id):

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':
            try:
                article       = self.__dataset_by_id_or_uri (article_id,
                                                             account_id=account_id,
                                                             is_published=False)
                files = self.db.article_files (
                    article_uri = article["uri"],
                    account_id = account_id,
                    limit      = validator.integer_value (request.args, "limit"))

                return self.default_list_response (files, formatter.format_file_for_article_record)

            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)
            except IndexError:
                pass
            except KeyError:
                pass

            return self.error_500 ()

        if request.method == 'POST':
            parameters = request.get_json()
            try:
                link = validator.string_value (parameters, "link", 0, 1000, False)
                article = self.__dataset_by_id_or_uri (article_id,
                                                       account_id=account_id,
                                                       is_published=False)

                if link is not None:
                    file_id = self.db.insert_file (
                        article_uri        = article["uri"],
                        account_id         = account_id,
                        is_link_only       = True,
                        download_url       = link)

                    if file_id is None:
                        return self.error_500()

                    return self.respond_201({
                        "location": f"{self.base_url}/v2/account/articles/{article_id}/files/{file_id}"
                    })

                file_id = self.db.insert_file (
                    article_uri   = article["uri"],
                    account_id    = account_id,
                    is_link_only  = False,
                    upload_token  = self.token_from_request (request),
                    supplied_md5  = validator.string_value  (parameters, "md5",  32, 32),
                    name          = validator.string_value  (parameters, "name", 0,  255,        True),
                    size          = validator.integer_value (parameters, "size", 0,  pow(2, 63), True))

                if file_id is None:
                    return self.error_500()

                return self.respond_201({
                    "location": f"{self.base_url}/v2/account/articles/{article_id}/files/{file_id}"
                })

            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)
            except IndexError:
                pass
            except KeyError:
                pass

            return self.error_500 ()

        return self.error_405 (["GET", "POST"])

    def api_private_article_file_details (self, request, article_id, file_id):

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':
            try:
                article = self.__dataset_by_id_or_uri (article_id,
                                                       account_id = account_id,
                                                       is_published = False)

                files   = self.__file_by_id_or_uri (file_id,
                                                    account_id  = account_id,
                                                    article_uri = article["uri"])

                return self.default_list_response (files, formatter.format_file_details_record)
            except IndexError:
                pass
            except KeyError:
                pass

            return self.error_500 ()

        if request.method == 'POST':
            return self.error_500()

        if request.method == 'DELETE':
            try:
                article = self.__dataset_by_id_or_uri (article_id,
                                                       account_id=account_id,
                                                       is_published=False)

                files = self.db.article_files (article_uri=article["uri"])
                files.remove (next (filter (lambda item: item["uuid"] == file_id, files)))
                files = list(map (lambda item: URIRef(uuid_to_uri(item["uuid"], "file")),
                                           files))

                if self.db.update_item_list (article["container_uuid"],
                                             account_id,
                                             files,
                                             "files"):
                    return self.respond_204()

            except IndexError:
                pass
            except KeyError:
                pass

            return self.error_500()

        return self.error_405 (["GET", "POST", "DELETE"])

    def api_private_article_private_links (self, request, article_id):

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':

            dataset = self.__dataset_by_id_or_uri (article_id,
                                                   account_id = account_id,
                                                   is_published = False)

            if dataset is None:
                return self.error_404 (request)

            links = self.db.private_links (item_uri   = dataset["uri"],
                                           account_id = account_id)

            return self.default_list_response (links, formatter.format_private_links_record)

        if request.method == 'POST':
            parameters = request.get_json()
            try:
                dataset      = self.__dataset_by_id_or_uri (article_id,
                                                            account_id = account_id)
                if dataset is None:
                    return self.error_404 (request)

                expires_date = validator.string_value (parameters, "expires_date", 0, 255, False)
                read_only    = validator.boolean_value (parameters, "read_only", False)
                id_string    = secrets.token_urlsafe()
                link_uri     = self.db.insert_private_link (
                                   expires_date = expires_date,
                                   read_only    = read_only,
                                   id_string    = id_string,
                                   is_active    = True)

                if link_uri is None:
                    logging.error ("Creating a private link failed for %s",
                                   dataset["uuid"])
                    return self.error_500()

                links    = self.db.private_links (item_uri   = dataset["uri"],
                                                  account_id = account_id)
                links    = list(map (lambda item: URIRef(item["uri"]), links))
                links    = links + [ URIRef(link_uri) ]

                if self.db.update_item_list (dataset["container_uuid"],
                                             account_id,
                                             links,
                                             "private_links"):
                    logging.error("Updating private links failed for %s.",
                                  dataset["uuid"])

                    return self.error_500()

                return self.response(json.dumps({
                    "location": f"{self.base_url}/articles/{id_string}"
                }))

            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

        return self.error_500 ()

    def api_private_article_private_links_details (self, request, article_id, link_id):

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        dataset = self.__dataset_by_id_or_uri (article_id,
                                               account_id = account_id,
                                               is_published = False)

        if dataset is None:
            return self.error_404 (request)

        if request.method == 'GET':
            links = self.db.private_links (
                        item_uri   = dataset["uri"],
                        id_string  = link_id,
                        account_id = account_id)

            return self.default_list_response (links, formatter.format_private_links_record)

        if request.method == 'PUT':
            parameters = request.get_json()
            try:
                expires_date = validator.string_value (parameters, "expires_date", 0, 255, False)
                is_active    = validator.boolean_value (parameters, "is_active", False)

                result = self.db.update_private_link (dataset["uri"],
                                                      account_id,
                                                      link_id,
                                                      expires_date = expires_date,
                                                      is_active    = is_active)

                if result is None:
                    return self.error_500()

                return self.response(json.dumps({
                    "location": f"{self.base_url}/articles/{link_id}"
                }))

            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

            return self.error_500 ()

        if request.method == 'DELETE':
            result = self.db.delete_private_links (dataset["uri"],
                                                   account_id,
                                                   link_id)

            if result is None:
                return self.error_500()

            return self.respond_204()

        return self.error_500 ()

    def api_private_articles_search (self, request):
        if request.method != 'POST':
            return self.error_405 ("POST")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        try:
            if not self.contains_json (request):
                return self.error_415 ("application/json")

            parameters = request.get_json()
            offset, limit = validator.paging_to_offset_and_limit (parameters)
            group = validator.integer_value (parameters, "group")
            records = self.db.datasets(
                resource_doi    = validator.string_value (parameters, "resource_doi", 0, 512),
                # "resource_id" here is not a typo for "article_id".
                dataset_id      = validator.integer_value (parameters, "resource_id"),
                item_type       = validator.integer_value (parameters, "item_type"),
                doi             = validator.string_value (parameters, "doi", 0, 255),
                handle          = validator.string_value (parameters, "handle", 0, 255),
                order           = validator.string_value (parameters, "order", 0, 255),
                search_for      = validator.string_value (parameters, "search_for", 0, 512),
                limit           = limit,
                offset          = offset,
                order_direction = validator.options_value (parameters, "order_direction", ["asc", "desc"]),
                institution     = validator.integer_value (parameters, "institution"),
                published_since = validator.string_value (parameters, "published_since", 0, 255),
                modified_since  = validator.string_value (parameters, "modified_since", 0, 255),
                groups          = [group] if group is not None else None,
                exclude_ids     = validator.string_value (parameters, "exclude", 0, 255),
                account_id      = account_id,
                is_published    = False
            )

            return self.default_list_response (records, formatter.format_article_record)

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    ## ------------------------------------------------------------------------
    ## COLLECTIONS
    ## ------------------------------------------------------------------------

    def api_collections (self, request):
        handler = self.default_error_handling (request, "GET")
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

            validator.order_direction (order_direction)
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
        handler = self.default_error_handling (request, "POST")
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
        handler = self.default_error_handling (request, "GET")
        if handler is not None:
            return handler

        collection     = self.__collection_by_id_or_uri (collection_id,
                                                         is_published=True,
                                                         is_latest=True)

        if collection is None:
            return self.error_404 (request)

        collection_uri = collection["uri"]
        articles_count = self.db.collections_article_count(collection_uri = collection_uri)
        fundings       = self.db.fundings(item_uri = collection_uri, item_type="collection")
        categories     = self.db.categories(item_uri = collection_uri)
        references     = self.db.references(item_uri = collection_uri)
        custom_fields  = self.db.custom_fields(item_uri = collection_uri, item_type="collection")
        tags           = self.db.tags(item_uri = collection_uri, item_type="collection")
        authors        = self.db.authors(item_uri = collection_uri, item_type="collection")
        total          = formatter.format_collection_details_record (collection,
                                                                     fundings,
                                                                     categories,
                                                                     references,
                                                                     tags,
                                                                     authors,
                                                                     custom_fields,
                                                                     articles_count)
        return self.response (json.dumps(total))

    def api_collection_versions (self, request, collection_id):
        handler = self.default_error_handling (request, "GET")
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
        handler = self.default_error_handling (request, "GET")
        if handler is not None:
            return handler

        collection     = self.__collection_by_id_or_uri (collection_id, version=version)
        if collection is None:
            return self.error_404 (request)

        collection_uri = collection["uri"]
        articles_count = self.db.collections_article_count(collection_uri = collection_uri)
        fundings       = self.db.fundings(item_uri = collection_uri, item_type="collection")
        categories     = self.db.categories(item_uri = collection_uri)
        references     = self.db.references(item_uri = collection_uri)
        custom_fields  = self.db.custom_fields(item_uri = collection_uri, item_type="collection")
        tags           = self.db.tags(item_uri = collection_uri, item_type="collection")
        authors        = self.db.authors(item_uri = collection_uri, item_type="collection")
        total          = formatter.format_collection_details_record (collection,
                                                                     fundings,
                                                                     categories,
                                                                     references,
                                                                     tags,
                                                                     authors,
                                                                     custom_fields,
                                                                     articles_count)

        return self.response (json.dumps(total))

    def api_private_collections (self, request):

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
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
                                           account_id=account_id)

            return self.default_list_response (records, formatter.format_collection_record)

        if request.method == 'POST':
            record = request.get_json()

            try:
                timeline   = validator.object_value (record, "timeline", False)
                collection_id = self.db.insert_collection (
                    title                   = validator.string_value  (record, "title",            3, 1000,       True),
                    account_id              = account_id,
                    funding                 = validator.string_value  (record, "funding",          0, 255,        False),
                    funding_list            = validator.array_value   (record, "funding_list",                    False),
                    description             = validator.string_value  (record, "description",      0, 10000,      False),
                    articles                = validator.array_value   (record, "articles",                        False),
                    authors                 = validator.array_value   (record, "authors",                         False),
                    categories              = validator.array_value   (record, "categories",                      False),
                    categories_by_source_id = validator.array_value   (record, "categories_by_source_id",         False),
                    tags                    = validator.array_value   (record, "tags",                            False),
                    keywords                = validator.array_value   (record, "keywords",                        False),
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
                    publisher_acceptance    = validator.string_value (timeline, "publisherAcceptance",            False),
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

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':
            try:
                collection    = self.__collection_by_id_or_uri (collection_id,
                                                                account_id = account_id,
                                                                is_published = False)

                collection_uri = collection["uri"]
                articles_count= self.db.collections_article_count(collection_uri=collection_uri)
                fundings      = self.db.fundings(item_uri=collection_uri, item_type="collection")
                categories    = self.db.categories(item_uri=collection_uri)
                references    = self.db.references(item_uri=collection_uri)
                custom_fields = self.db.custom_fields(item_uri=collection_uri, item_type="collection")
                tags          = self.db.tags(item_uri=collection_uri, item_type="collection")
                authors       = self.db.authors(item_uri=collection_uri, item_type="collection")
                total         = formatter.format_collection_details_record (collection,
                                                                            fundings,
                                                                            categories,
                                                                            references,
                                                                            tags,
                                                                            authors,
                                                                            custom_fields,
                                                                            articles_count)
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
                                                                 account_id = account_id,
                                                                 is_published = False)
                container_uuid = collection["container_uuid"]
                result = self.db.update_collection (container_uuid, account_id,
                    title           = validator.string_value  (record, "title",          3, 1000),
                    description     = validator.string_value  (record, "description",    0, 10000),
                    resource_doi    = validator.string_value  (record, "resource_doi",   0, 255),
                    resource_title  = validator.string_value  (record, "resource_title", 0, 255),
                    group_id        = validator.integer_value (record, "group_id",       0, pow(2, 63)),
                    time_coverage   = validator.string_value  (record, "time_coverage",  0, 10000),
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

            except IndexError:
                pass
            except KeyError:
                pass
            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

            return self.error_500 ()

        if request.method == 'DELETE':
            try:
                collection = self.__collection_by_id_or_uri(
                    collection_id,
                    account_id   = account_id,
                    is_published = False)

                if collection is None:
                    return self.error_404 (request)

                if self.db.delete_collection (
                        container_uuid = collection["container_uuid"],
                        account_id     = account_id):
                    return self.respond_204()
            except IndexError:
                pass
            except KeyError:
                pass

        return self.error_500 ()

    def api_private_collections_search (self, request):
        handler = self.default_error_handling (request, "POST")
        if handler is not None:
            return handler

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
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
            account_id      = account_id
        )

        return self.default_list_response (records, formatter.format_article_record)

    def api_private_collection_authors (self, request, collection_id):
        """Implements /v2/account/collections/<id>/authors."""

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':
            try:
                collection = self.__collection_by_id_or_uri (collection_id,
                                                             account_id   = account_id,
                                                             is_published = False)

                authors    = self.db.authors (item_uri     = collection["uri"],
                                              is_published = False,
                                              account_id   = account_id,
                                              item_type    = "collection",
                                              limit        = 10000)

                return self.default_list_response (authors, formatter.format_author_record)
            except IndexError:
                pass
            except KeyError:
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
                            is_public  = True)
                        if author_uuid is None:
                            logging.error("Adding a single author failed.")
                            return self.error_500()
                    new_authors.append(URIRef(uuid_to_uri (author_uuid, "author")))

                collection = self.__collection_by_id_or_uri (collection_id,
                                                             account_id   = account_id,
                                                             is_published = False)

                # The PUT method overwrites the existing authors, so we can
                # keep an empty starting list. For POST we must retrieve the
                # existing authors to preserve them.
                existing_authors = []
                if request.method == 'POST':
                    existing_authors = self.db.authors (
                        item_uri     = collection["uri"],
                        account_id   = account_id,
                        item_type    = "collection",
                        is_published = False,
                        limit        = 10000)

                    existing_authors = list(map (lambda item: URIRef(uuid_to_uri(item["uuid"], "author")),
                                                 existing_authors))

                authors = existing_authors + new_authors
                if not self.db.update_item_list (uri_to_uuid (collection["container_uri"]),
                                                 account_id,
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
            except Exception as error:
                logging.error("An error occurred when adding an author record:")
                logging.error("Exception: %s", error)

            return self.error_500()

        return self.error_405 ("GET")

    def api_private_collection_categories (self, request, collection_id):
        handler = self.default_error_handling (request, "GET")
        if handler is not None:
            return handler

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        try:
            collection = self.__collection_by_id_or_uri (collection_id,
                                                         account_id=account_id)

            if collection is None:
                return self.error_404 (request)

            categories = self.db.categories(item_uri   = collection["uri"],
                                            account_id = account_id)

            return self.default_list_response (categories, formatter.format_category_record)
        except IndexError:
            pass
        except KeyError:
            pass

        return self.error_500 ()

    def api_private_collection_articles (self, request, collection_id):
        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        if request.method == 'GET':
            try:
                collection = self.__collection_by_id_or_uri (collection_id,
                                                             is_published = False,
                                                             account_id = account_id)

                if collection is None:
                    return self.error_404 (request)

                articles   = self.db.datasets (collection_uri = collection["uri"],
                                               account_id     = account_id)

                return self.default_list_response (articles, formatter.format_article_record)
            except IndexError:
                pass
            except KeyError:
                pass

            return self.error_500 ()

        if request.method in ('PUT', 'POST'):
            try:
                parameters = request.get_json()
                articles = parameters["articles"]

                collection = self.__collection_by_id_or_uri (collection_id, account_id=account_id)
                if collection is None:
                    return self.error_404 (request)

                # First, validate all values passed by the user.
                # This way, we can be as certain as we can be that performing
                # a PUT will not end in having no articles associated with
                # an article.
                for index, _ in enumerate(articles):
                    if parses_to_int (articles[index]):
                        article = validator.integer_value (articles, index)
                    else:
                        article = validator.string_value (articles, index, 36, 36)

                    article = self.__dataset_by_id_or_uri (article)
                    articles[index] = URIRef(article["container_uri"])

                if self.db.update_item_list (collection["uuid"],
                                             account_id,
                                             articles,
                                             "articles"):
                    return self.respond_205()

                return self.error_500 ()
            except IndexError:
                return self.error_500 ()
            except KeyError:
                return self.error_400 (request, "Expected an array for 'articles'.", "NoArticlesField")
            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)
            except Exception as error:
                logging.error("An error occurred when adding articles:")
                logging.error("Exception: %s", error)

        return self.error_405 (["GET", "POST", "PUT"])

    def api_collection_articles (self, request, collection_id):
        handler = self.default_error_handling (request, "GET")
        if handler is not None:
            return handler

        try:
            collection = self.__collection_by_id_or_uri (collection_id)
            if collection is None:
                return self.error_404 (request)

            articles   = self.db.datasets (collection_uri = collection["uri"])
            return self.default_list_response (articles, formatter.format_article_record)
        except IndexError:
            pass
        except KeyError:
            pass

        return self.error_500 ()

    ## ------------------------------------------------------------------------
    ## AUTHORS
    ## ------------------------------------------------------------------------

    def api_private_authors_search (self, request):
        handler = self.default_error_handling (request, "POST")
        if handler is not None:
            return handler

        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        try:
            parameters = request.get_json()
            records = self.db.authors(
                search_for = validator.string_value (parameters, "search", 0, 255, True)
            )

            return self.default_list_response (records, formatter.format_author_details_record)

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    ## ------------------------------------------------------------------------
    ## V3 API
    ## ------------------------------------------------------------------------

    def api_v3_articles (self, request):
        handler = self.default_error_handling (request, "GET")
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
            validator.order_direction (record["order_direction"])
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

        return self.default_list_response (records, formatter.format_article_record)

    def __api_v3_articles_parameters (self, request, item_type):
        record = {}
        record["article_id"]      = self.get_parameter (request, "id")
        record["limit"]           = self.get_parameter (request, "limit")
        record["offset"]          = self.get_parameter (request, "offset")
        record["order"]           = self.get_parameter (request, "order")
        record["order_direction"] = self.get_parameter (request, "order_direction")
        record["group_ids"]       = self.get_parameter(request, "group_ids")
        record["categories"]      = self.get_parameter (request, "categories")
        record["item_type"]       = item_type

        validator.integer_value (record, "id")
        validator.integer_value (record, "limit")
        validator.integer_value (record, "offset")
        validator.string_value  (record, "order", maximum_length=32)
        validator.order_direction (record["order_direction"])
        validator.string_value  (record, "item_type", maximum_length=32)

        if item_type not in {"downloads", "views", "shares", "cites"}:
            raise validator.InvalidValue(
                message = ("The last URL parameter must be one of "
                           "'downloads', 'views', 'shares' or 'cites'."),
                code    = "InvalidURLParameterValue")

        if record["categories"] is not None:
            record["categories"] = record["categories"].split(",")
            validator.array_value   (record, "categories")
            for index, _ in enumerate(record["categories"]):
                record["categories"][index] = validator.integer_value (record["categories"], index)

        if record["group_ids"] is not None:
            record["group_ids"] = record["group_ids"].split(",")
            validator.array_value(record, "group_ids")
            for index, _ in enumerate(record["group_ids"]):
                record["group_ids"][index] = validator.integer_value(record["group_ids"], index)

        return record

    def api_v3_articles_top (self, request, item_type):
        handler = self.default_error_handling (request, "GET")
        if handler is not None:
            return handler

        record = {}
        try:
            record = self.__api_v3_articles_parameters (request, item_type)

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

        offset, limit = validator.paging_to_offset_and_limit ({
                "page":      self.get_parameter (request, "page"),
                "page_size": self.get_parameter (request, "page_size"),
                "limit":     self.get_parameter (request, "limit"),
                "offset":    self.get_parameter (request, "offset")
            })

        if "group_ids" in record and record["group_ids"] is not None:
            record["group_ids"] = record["group_ids"]
            validator.array_value (record, "group_ids")
            for index, _ in enumerate(record["group_ids"]):
                record["group_ids"][index] = validator.integer_value (record["group_ids"], index)

        if "categories" in record and record["categories"] is not None:
            validator.array_value (record, "categories")
            for index, _ in enumerate(record["categories"]):
                record["categories"][index] = validator.integer_value (record["categories"], index)
        else:
            record["categories"] = None

        records = self.db.article_statistics (
            limit           = limit,
            offset          = offset,
            order           = validator.string_value (request.args, "order", 0, 255),
            order_direction = validator.options_value (request.args, "order_direction", ["asc", "desc"]),
            group_ids       = record["group_ids"],
            category_ids    = record["categories"],
            item_type       = item_type)

        return self.response (json.dumps(records))

    def api_v3_articles_timeline (self, request, item_type):
        handler = self.default_error_handling (request, "GET")
        if handler is not None:
            return handler

        record = {}
        try:
            record = self.__api_v3_articles_parameters (request, item_type)

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

        records = self.db.article_statistics_timeline (
            article_id      = record["article_id"],
            limit           = record["limit"],
            offset          = record["offset"],
            order           = record["order"],
            order_direction = record["order_direction"],
            category_ids    = record["categories"],
            item_type       = item_type)

        return self.response (json.dumps(records))

    def api_v3_article_git_files (self, request, article_id):

        if request.method != "GET":
            return self.error_405 ("GET")

        git_directory  = f"{self.db.storage}/{article_id}.git"
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

    def api_v3_article_upload_file (self, request, article_id):
        handler = self.default_error_handling (request, "POST")
        if handler is not None:
            return handler

        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        try:
            article   = self.__dataset_by_id_or_uri (article_id,
                                                     account_id=account_id,
                                                     is_published=False)
            file_data = request.files['file']
            file_uuid = self.db.insert_file (
                name          = file_data.filename,
                size          = file_data.content_length,
                is_link_only  = 0,
                upload_url    = f"/article/{article_id}/upload",
                upload_token  = self.token_from_request (request),
                article_uri   = article["uri"],
                account_id    = account_id)

            output_filename = f"{self.db.storage}/{article_id}_{file_uuid}"

            file_data.save (output_filename)
            file_data.close()

            file_size = 0
            file_size = os.path.getsize (output_filename)

            computed_md5 = None
            md5 = hashlib.md5()
            with open(output_filename, "rb") as stream:
                for chunk in iter(lambda: stream.read(4096), b""):
                    md5.update(chunk)
                    computed_md5 = md5.hexdigest()

            download_url = f"{self.base_url}/file/{article_id}/{file_uuid}"
            self.db.update_file (account_id, file_uuid,
                                 computed_md5 = computed_md5,
                                 download_url = download_url,
                                 filesystem_location = output_filename,
                                 file_size    = file_size)

            return self.response (json.dumps({ "location": f"{self.base_url}/v3/file/{file_uuid}" }))

        except OSError:
            logging.error ("Writing %s to disk failed.", output_filename)
            return self.error_500 ()
        except IndexError:
            pass
        except KeyError:
            pass

        return self.error_500 ()

    def api_v3_file (self, request, file_id):
        handler = self.default_error_handling (request, "GET")
        if handler is not None:
            return handler

        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        metadata = self.__file_by_id_or_uri (file_id, account_id = account_id)
        if metadata is None:
            return self.error_404 (request)

        try:
            return self.response (json.dumps (formatter.format_file_details_record (metadata)))
        except KeyError:
            return self.error_500()

        return self.error_500()

    def api_v3_article_references (self, request, article_id):
        """Implements /v3/articles/<id>/references."""

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        if request.method not in ['GET', 'POST', 'DELETE']:
            return self.error_405 (["GET", "POST", "DELETE"])

        try:
            article        = self.__dataset_by_id_or_uri (article_id,
                                                          account_id=account_id,
                                                          is_published=False)

            references     = self.db.references (item_uri   = article["uri"],
                                                 account_id = account_id)

            if request.method == 'GET':
                return self.default_list_response (references, formatter.format_reference_record)

            references     = list(map(lambda reference: reference["url"], references))

            if request.method == 'DELETE':
                url_encoded = validator.string_value (request.args, "url", 0, 1024, True)
                url         = requests.utils.unquote(url_encoded)
                references.remove (next (filter (lambda item: item == url, references)))
                if not self.db.update_item_list (uri_to_uuid (article["container_uri"]),
                                                 account_id,
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
                new_references.append(validator.string_value (record, "url", 0, 512, True))

            if request.method == 'POST':
                references = references + new_references

            if not self.db.update_item_list (uri_to_uuid (article["container_uri"]),
                                             account_id,
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
        except Exception as error:
            logging.error("An error occurred when adding a reference record:")
            logging.error("Exception: %s", error)

        return self.error_500 ()

    def api_v3_groups (self, request):
        handler = self.default_error_handling (request, "GET")
        if handler is not None:
            return handler

        try:
            limit           = validator.integer_value (request.args, "limit")
            offset          = validator.integer_value (request.args, "offset")
            order           = validator.integer_value (request.args, "order")
            order_direction = validator.string_value  (request.args, "order_direction", 0, 4)
            group_id        = validator.integer_value (request.args, "id")
            parent_id       = validator.integer_value (request.args, "parent_id")
            name            = validator.string_value  (request.args, "name", 0, 255)
            association     = validator.string_value  (request.args, "association", 0, 255)

            records         = self.db.group (group_id        = group_id,
                                             parent_id       = parent_id,
                                             name            = name,
                                             association     = association,
                                             limit           = limit,
                                             offset          = offset,
                                             order           = order,
                                             order_direction = order_direction)

            return self.default_list_response (records, formatter.format_group_record)

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

        return self.error_500 ()

    def __git_create_repository (self, article_id):
        git_directory = f"{self.db.storage}/{article_id}.git"
        if not os.path.exists (git_directory):
            initial_repository = pygit2.init_repository (git_directory, False)
            if initial_repository:
                try:
                    with open (f"{git_directory}/.git/config", "a",
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
            ## It assumes the first twelve characters are: "/v3/articles".
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

    def api_v3_private_article_git_refs (self, request, article_id):
        """Implements /v3/articles/<id>.git/<suffix>."""

        service = validator.string_value (request.args, "service", 0, 255)
        self.__git_create_repository (article_id)

        ## Used for clone and pull.
        if service == "git-upload-pack":
            return self.__git_passthrough (request)

        ## Used for push.
        if service == "git-receive-pack":
            return self.__git_passthrough (request)

        logging.error ("Unsupported Git service command: %s", service)
        return self.error_500 ()

    def api_v3_private_article_git_upload_pack (self, request, article_id):
        """Implements /v3/articles/<id>.git/git-upload-pack."""
        return self.__git_passthrough (request)

    def api_v3_private_article_git_receive_pack (self, request, article_id):
        """Implements /v3/articles/<id>.git/git-receive-pack."""
        return self.__git_passthrough (request)

    def api_v3_profile (self, request):
        """Implements /v3/profile."""

        if not self.accepts_json (request):
            return self.error_406 ("application/json")

        if request.method != 'PUT':
            return self.error_405 ("PUT")

        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        try:
            record = request.get_json()
            categories = validator.array_value (record, "categories")
            if categories is not None:
                for index, _ in enumerate(categories):
                    categories[index] = validator.string_value (categories, index, 36, 36)

            if self.db.update_account (account_id,
                    active                = validator.integer_value (record, "active", 0, 1),
                    job_title             = validator.string_value  (record, "job_title", 0, 255),
                    email                 = validator.string_value  (record, "email", 0, 255),
                    first_name            = validator.string_value  (record, "first_name", 0, 255),
                    last_name             = validator.string_value  (record, "last_name", 0, 255),
                    location              = validator.string_value  (record, "location", 0, 255),
                    biography             = validator.string_value  (record, "biography", 0, 32768),
                    institution_user_id   = validator.integer_value (record, "institution_user_id"),
                    institution_id        = validator.integer_value (record, "institution_id"),
                    pending_quota_request = validator.integer_value (record, "pending_quota_request"),
                    used_quota_public     = validator.integer_value (record, "used_quota_public"),
                    used_quota_private    = validator.integer_value (record, "used_quota_private"),
                    used_quota            = validator.integer_value (record, "used_quota"),
                    maximum_file_size     = validator.integer_value (record, "maximum_file_size"),
                    quota                 = validator.integer_value (record, "quota"),
                    modified_date         = validator.string_value  (record, "modified_date", 0, 32),
                    group_id              = validator.integer_value (record, "group_id"),
                    categories            = categories):
                return self.respond_204 ()

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

        return self.error_500 ()

    def api_v3_profile_categories (self, request):
        """Implements /v3/profile/categories."""

        handler = self.default_error_handling (request, "GET")
        if handler is not None:
            return handler

        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed(request)

        categories = self.db.account_categories (account_id)
        return self.default_list_response (categories, formatter.format_category_record)
