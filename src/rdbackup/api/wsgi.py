"""This module implements the API server."""

import os.path
import logging
import json
from werkzeug.wrappers import Request, Response
from werkzeug.serving import run_simple
from werkzeug.routing import Map, Rule
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.exceptions import HTTPException, NotFound
from jinja2 import Environment, FileSystemLoader
from rdbackup.api import formatter
from rdbackup.api import database
from rdbackup.utils import convenience

class ApiServer:
    """This class implements the API server."""

    ## INITIALISATION
    ## ------------------------------------------------------------------------

    def __init__ (self):
        self.address          = "127.0.0.1"
        self.port             = 8080
        self.db               = database.SparqlInterface()

        ## This is a temporary predefined set of tokens to test the private
        ## articles functionality.
        self.tokens           = {
            "2bc2d4c4ea5e3c5f3da70e2aa697c51730d66adadc5c4503e0ff7b4541683b99": 2391394,
            "e33bfd5e4b05a342f496f53939d4ab29d835d7bbe2d925b69d40a712908ccddc": 2397553,
            "60b2a1fbae694cb7c85105aeaa57a2d04644f078db32c23732b420c68abb0efe": 1000002
        }

        ## Routes to all API calls.
        ## --------------------------------------------------------------------

        self.url_map = Map([
            Rule("/",                                         endpoint = "home"),
            Rule("/v2/account/applications/authorize",        endpoint = "authorize"),
            Rule("/v2/token",                                 endpoint = "token"),
            Rule("/v2/collections",                           endpoint = "collections"),

            ## Private institutions
            ## ----------------------------------------------------------------
            Rule("/v2/account/institution",                   endpoint = "private_institution"),

            ## Public articles
            ## ----------------------------------------------------------------
            Rule("/v2/articles",                              endpoint = "articles"),
            Rule("/v2/articles/search",                       endpoint = "articles_search"),
            Rule("/v2/articles/<article_id>",                 endpoint = "article_details"),
            Rule("/v2/articles/<article_id>/files",           endpoint = "article_files"),
            Rule("/v2/articles/<article_id>/files/<file_id>", endpoint = "article_file_details"),

            ## Private articles
            ## ----------------------------------------------------------------
            Rule("/v2/account/articles",                      endpoint = "private_articles"),
            Rule("/v2/account/articles/search",               endpoint = "private_articles_search"),
            Rule("/v2/account/articles/<article_id>",         endpoint = "private_article_details"),
            Rule("/v2/account/articles/<article_id>/authors", endpoint = "private_article_authors"),
            Rule("/v2/account/articles/<article_id>/categories", endpoint = "private_article_categories"),
            Rule("/v2/account/articles/<article_id>/files",   endpoint = "private_article_files"),
            Rule("/v2/account/articles/<article_id>/files/<file_id>", endpoint = "private_article_file_details"),

            ## Public collections
            ## ----------------------------------------------------------------
            Rule("/v2/collections",                           endpoint = "collections"),
            Rule("/v2/collections/search",                    endpoint = "collections_search"),
            Rule("/v2/collections/<collection_id>",           endpoint = "collection_details"),

            ## Private collections
            ## ----------------------------------------------------------------
            Rule("/v2/account/collections",                   endpoint = "private_collections"),
            Rule("/v2/account/collections/search",            endpoint = "private_collections_search"),
            Rule("/v2/account/collections/<collection_id>",   endpoint = "private_collection_details"),
            Rule("/v2/account/collections/<collection_id>/authors", endpoint = "private_collection_authors"),
            Rule("/v2/account/collections/<collection_id>/categories", endpoint = "private_collection_categories"),
            Rule("/v2/account/collections/<collection_id>/articles", endpoint = "private_collection_articles"),
          ])

        ## Static resources and HTML templates.
        ## --------------------------------------------------------------------

        self.jinja   = Environment(loader = FileSystemLoader(
                        os.path.join(os.path.dirname(__file__),
                                     "resources/templates")),
                                     autoescape = True)

        self.wsgi    = SharedDataMiddleware(self.respond, {
            "/static": os.path.join(os.path.dirname(__file__),
                                    "resources/static")
        })

        ## Disable werkzeug logging.
        ## --------------------------------------------------------------------
        werkzeug_logger = logging.getLogger('werkzeug')
        werkzeug_logger.setLevel(logging.ERROR)

    ## WSGI AND WERKZEUG SETUP.
    ## ------------------------------------------------------------------------

    def __call__ (self, environ, start_response):
        return self.wsgi (environ, start_response)

    def render_template (self, template_name, **context):
        template = self.jinja.get_template (template_name)
        return self.response (template.render(context),
                              mimetype='text/html; charset=utf-8')

    def dispatch_request (self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            return getattr(self, f"api_{endpoint}")(request, **values)
        except NotFound:
            return self.error_404 (request)
        except HTTPException as error:
            logging.error("Unknown error in dispatch_request: %s", error)
            return error

    def respond (self, environ, start_response):
        request  = Request(environ)
        response = self.dispatch_request(request)
        return response(environ, start_response)

    def start (self):
        run_simple (self.address,
                    self.port,
                    self,
                    use_debugger=True,
                    use_reloader=False)

    ## ERROR HANDLERS
    ## ------------------------------------------------------------------------

    def error_404 (self, request):
        response = None
        if self.accepts_html (request):
            response = self.render_template ("404.html")
        else:
            response = self.response (json.dumps({
                "message": "This call does not exist."
            }))
        response.status_code = 404
        return response

    def error_405 (self, allowed_methods):
        response = self.response (f"Acceptable methods: {allowed_methods}",
                                  mimetype="text/plain")
        response.status_code = 405
        return response

    def error_406 (self, allowed_formats):
        response = self.response (f"Acceptable formats: {allowed_formats}",
                                  mimetype="text/plain")
        response.status_code = 406
        return response

    def error_authorization_failed (self):
        return self.response (json.dumps({
            "message": "Invalid or unknown OAuth token",
            "code":    "OAuthInvalidToken"
        }))

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

    def get_parameter (self, request, parameter):
        try:
            return request.form[parameter]
        except KeyError:
            return request.args.get(parameter)


    def account_id_from_request (self, request):
        token_string = None
        account_id = None
        token = ""

        ## Get the token from the "Authorization" HTTP header.
        ## If no such header is provided, we cannot authenticate.
        try:
            token_string = request.environ["HTTP_AUTHORIZATION"]
        except KeyError:
            return account_id

        if token_string.startswith("token "):
            token = token_string[6:]

        ## Match the token to an account_id.  If the token does not
        ## exist, we cannot authenticate.
        try:
            account_id = self.tokens[token]
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

    ## API CALLS
    ## ------------------------------------------------------------------------

    def api_home (self, request):
        if self.accepts_html (request):
            return self.render_template ("home.html")

        return self.response (json.dumps({ "status": "OK" }))

    def api_authorize (self, request):
        return False

    def api_token (self, request):
        return False

    def api_private_institution (self, request):
        handler = self.default_error_handling (request, "GET")
        if handler is not None:
            return handler

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        ## Our API only contains data from 4TU.ResearchData.
        return self.response (json.dumps({
            "id": 898,
            "name": "4TU.ResearchData"
        }))

    def api_articles (self, request):
        if request.method != 'GET':
            return self.error_405 ("GET")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## TODO: Setting "limit" to "TEST" crashes the app. Do type checking
        ## and sanitization.

        ## Parameters
        ## ----------------------------------------------------------------
        page            = self.get_parameter (request, "page")
        page_size       = self.get_parameter (request, "page_size")
        limit           = self.get_parameter (request, "limit")
        offset          = self.get_parameter (request, "offset")
        order           = self.get_parameter (request, "order")
        order_direction = self.get_parameter (request, "order_direction")
        institution     = self.get_parameter (request, "institution")
        published_since = self.get_parameter (request, "published_since")
        modified_since  = self.get_parameter (request, "modified_since")
        group           = self.get_parameter (request, "group")
        resource_doi    = self.get_parameter (request, "resource_doi")
        item_type       = self.get_parameter (request, "item_type")
        doi             = self.get_parameter (request, "doi")
        handle          = self.get_parameter (request, "handle")

        records = self.db.articles(#page=page,
                                   #page_size=page_size,
                                   limit=limit,
                                   offset=offset,
                                   order=order,
                                   order_direction=order_direction,
                                   institution=institution,
                                   published_since=published_since,
                                   modified_since=modified_since,
                                   group=group,
                                   resource_doi=resource_doi,
                                   item_type=item_type,
                                   doi=doi,
                                   handle=handle)

        return self.default_list_response (records, formatter.format_article_record)

    def api_articles_search (self, request):
        if request.method != 'POST':
            return self.error_405 ("POST")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        parameters = request.get_json()
        records = self.db.articles(
            limit           = convenience.value_or_none(parameters, "limit"),
            offset          = convenience.value_or_none(parameters, "offset"),
            order           = convenience.value_or_none(parameters, "order"),
            order_direction = convenience.value_or_none(parameters, "order_direction"),
            institution     = convenience.value_or_none(parameters, "institution"),
            published_since = convenience.value_or_none(parameters, "published_since"),
            modified_since  = convenience.value_or_none(parameters, "modified_since"),
            group           = convenience.value_or_none(parameters, "group"),
            resource_doi    = convenience.value_or_none(parameters, "resource_doi"),
            item_type       = convenience.value_or_none(parameters, "item_type"),
            doi             = convenience.value_or_none(parameters, "doi"),
            handle          = convenience.value_or_none(parameters, "handle"),
            search_for      = convenience.value_or_none(parameters, "search_for")
        )

        return self.default_list_response (records, formatter.format_article_record)

    def api_article_details (self, request, article_id):
        if request.method != 'GET':
            return self.error_405 ("GET")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        try:
            article       = self.db.articles(article_id=article_id)[0]
            authors       = self.db.authors(item_id=article_id, item_type="article")
            files         = self.db.article_files(article_id=article_id)
            custom_fields = self.db.custom_fields(item_id=article_id, item_type="article")
            embargo_options = self.db.article_embargo_options(article_id=article_id)
            tags          = self.db.tags(item_id=article_id, item_type="article")
            categories    = self.db.categories(item_id=article_id, item_type="article")
            references    = self.db.references(item_id=article_id, item_type="article")
            fundings      = self.db.fundings(item_id=article_id, item_type="article")
            total         = formatter.format_article_details_record (article,
                                                                     authors,
                                                                     files,
                                                                     custom_fields,
                                                                     embargo_options,
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

    def api_article_files (self, request, article_id):
        if request.method != 'GET':
            return self.error_405 ("GET")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        files = self.db.article_files(article_id=article_id)
        return self.default_list_response (files, formatter.format_file_for_article_record)

    def api_article_file_details (self, request, article_id, file_id):
        if request.method != 'GET':
            return self.error_405 ("GET")
        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        try:
            files = self.db.article_files(file_id=file_id, article_id=article_id)[0]
            results = formatter.format_file_for_article_record(files)
            return self.response (json.dumps(results))
        except IndexError:
            response = self.response (json.dumps({
                "message": "This file cannot be found."
            }))
            response.status_code = 404
            return response


    def api_private_articles (self, request):
        if request.method != 'GET':
            return self.error_405 ("GET")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        ## TODO: Setting "limit" to "TEST" crashes the app. Do type checking
        ## and sanitization.

        ## Parameters
        ## ----------------------------------------------------------------
        page            = self.get_parameter (request, "page")
        page_size       = self.get_parameter (request, "page_size")
        limit           = self.get_parameter (request, "limit")
        offset          = self.get_parameter (request, "offset")

        records = self.db.articles(#page=page,
                                   #page_size=page_size,
                                   limit=limit,
                                   offset=offset,
                                   account_id=account_id)

        return self.default_list_response (records, formatter.format_article_record)

    def api_private_article_details (self, request, article_id):
        if request.method != 'GET':
            return self.error_405 ("GET")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        article    = self.db.articles (article_id=article_id, account_id=account_id)
        if not article:
            return self.response (json.dumps([]))

        try:
            article         = article[0]
            authors         = self.db.authors(item_id=article_id, item_type="article")
            files           = self.db.article_files(article_id=article_id)
            custom_fields   = self.db.custom_fields(item_id=article_id, item_type="article")
            embargo_options = self.db.article_embargo_options(article_id=article_id)
            tags            = self.db.tags(item_id=article_id, item_type="article")
            categories      = self.db.categories(item_id=article_id, item_type="article")
            funding         = self.db.fundings(item_id=article_id, item_type="article")
            references      = self.db.references(item_id=article_id, item_type="article")
            total           = formatter.format_article_details_record (article,
                                                                       authors,
                                                                       files,
                                                                       custom_fields,
                                                                       embargo_options,
                                                                       tags,
                                                                       categories,
                                                                       funding,
                                                                       references)

            return self.response (json.dumps(total))
        except IndexError:
            response = self.response (json.dumps({
                "message": "This article cannot be found."
            }))
            response.status_code = 404
            return response

    def api_private_article_authors (self, request, article_id):
        if request.method != 'GET':
            return self.error_405 ("GET")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        authors    = self.db.authors(item_id    = article_id,
                                     account_id = account_id,
                                     item_type  = "article")

        return self.default_list_response (authors, formatter.format_author_record)

    def api_private_article_categories (self, request, article_id):
        if request.method != 'GET':
            return self.error_405 ("GET")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        categories    = self.db.categories(item_id    = article_id,
                                           account_id = account_id,
                                           item_type  = "article")

        return self.default_list_response (categories, formatter.format_category_record)

    def api_private_article_files (self, request, article_id):
        if request.method != 'GET':
            return self.error_405 ("GET")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        files         = self.db.article_files (article_id = article_id,
                                               account_id = account_id)

        return self.default_list_response (files, formatter.format_file_for_article_record)

    def api_private_article_file_details (self, request, article_id, file_id):
        if request.method != 'GET':
            return self.error_405 ("GET")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        files         = self.db.article_files (article_id = article_id,
                                               account_id = account_id,
                                               file_id    = file_id)

        return self.default_list_response (files, formatter.format_file_details_record)

    def api_private_articles_search (self, request):
        if request.method != 'POST':
            return self.error_405 ("POST")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        parameters = request.get_json()
        records = self.db.articles(
            resource_doi    = convenience.value_or_none(parameters, "resource_doi"),
            article_id      = convenience.value_or_none(parameters, "resource_id"),
            item_type       = convenience.value_or_none(parameters, "item_type"),
            doi             = convenience.value_or_none(parameters, "doi"),
            handle          = convenience.value_or_none(parameters, "handle"),
            order           = convenience.value_or_none(parameters, "order"),
            search_for      = convenience.value_or_none(parameters, "search_for"),
            #page            = convenience.value_or_none(parameters, "page"),
            #page_size       = convenience.value_or_none(parameters, "page_size"),
            limit           = convenience.value_or_none(parameters, "limit"),
            offset          = convenience.value_or_none(parameters, "offset"),
            order_direction = convenience.value_or_none(parameters, "order_direction"),
            institution     = convenience.value_or_none(parameters, "institution"),
            published_since = convenience.value_or_none(parameters, "published_since"),
            modified_since  = convenience.value_or_none(parameters, "modified_since"),
            group           = convenience.value_or_none(parameters, "group"),
            account_id      = account_id
        )

        return self.default_list_response (records, formatter.format_article_record)

    ## ------------------------------------------------------------------------
    ## COLLECTIONS
    ## ------------------------------------------------------------------------

    def api_collections (self, request):
        handler = self.default_error_handling (request, "GET")
        if handler is not None:
            return handler

        ## TODO: Setting "limit" to "TEST" crashes the app. Do type checking
        ## and sanitization.

        ## Parameters
        ## ----------------------------------------------------------------
        page            = self.get_parameter (request, "page")
        page_size       = self.get_parameter (request, "page_size")
        limit           = self.get_parameter (request, "limit")
        offset          = self.get_parameter (request, "offset")
        order           = self.get_parameter (request, "order")
        order_direction = self.get_parameter (request, "order_direction")
        institution     = self.get_parameter (request, "institution")
        published_since = self.get_parameter (request, "published_since")
        modified_since  = self.get_parameter (request, "modified_since")
        group           = self.get_parameter (request, "group")
        resource_doi    = self.get_parameter (request, "resource_doi")
        doi             = self.get_parameter (request, "doi")
        handle          = self.get_parameter (request, "handle")

        records = self.db.collections (#page=page,
                                       #page_size=page_size,
                                       limit=limit,
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

    def api_collections_search (self, request):
        handler = self.default_error_handling (request, "POST")
        if handler is not None:
            return handler

        parameters = request.get_json()
        records    = self.db.collections(
            limit           = convenience.value_or_none(parameters, "limit"),
            offset          = convenience.value_or_none(parameters, "offset"),
            order           = convenience.value_or_none(parameters, "order"),
            order_direction = convenience.value_or_none(parameters, "order_direction"),
            institution     = convenience.value_or_none(parameters, "institution"),
            published_since = convenience.value_or_none(parameters, "published_since"),
            modified_since  = convenience.value_or_none(parameters, "modified_since"),
            group           = convenience.value_or_none(parameters, "group"),
            resource_doi    = convenience.value_or_none(parameters, "resource_doi"),
            doi             = convenience.value_or_none(parameters, "doi"),
            handle          = convenience.value_or_none(parameters, "handle"),
            search_for      = convenience.value_or_none(parameters, "search_for")
        )

        return self.default_list_response (records, formatter.format_collection_record)

    def api_collection_details (self, request, collection_id):
        handler = self.default_error_handling (request, "GET")
        if handler is not None:
            return handler

        try:
            collection    = self.db.collections(collection_id=collection_id, limit=1)[0]
            fundings      = self.db.fundings(item_id=collection_id, item_type="collection")
            categories    = self.db.categories(item_id=collection_id, item_type="collection")
            references    = self.db.references(item_id=collection_id, item_type="collection")
            custom_fields = self.db.custom_fields(item_id=collection_id, item_type="collection")
            tags          = self.db.tags(item_id=collection_id, item_type="collection")
            authors       = self.db.authors(item_id=collection_id, item_type="collection")
            total         = formatter.format_collection_details_record (collection,
                                                                        fundings,
                                                                        categories,
                                                                        references,
                                                                        tags,
                                                                        authors,
                                                                        custom_fields)
            return self.response (json.dumps(total))

        except IndexError:
            response = self.response (json.dumps({
                "message": "This collection cannot be found."
            }))
            response.status_code = 404
            return response

    def api_private_collections (self, request):
        handler = self.default_error_handling (request, "GET")
        if handler is not None:
            return handler

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        ## Parameters
        ## ----------------------------------------------------------------
        page            = self.get_parameter (request, "page")
        page_size       = self.get_parameter (request, "page_size")
        limit           = self.get_parameter (request, "limit")
        offset          = self.get_parameter (request, "offset")
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

        records = self.db.collections (#page=page,
                                       #page_size=page_size,
                                       limit=limit,
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

    def api_private_collection_details (self, request, collection_id):
        handler = self.default_error_handling (request, "GET")
        if handler is not None:
            return handler

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        try:
            collection    = self.db.collections(collection_id = collection_id,
                                                account_id    = account_id,
                                                limit         = 1)[0]
            fundings      = self.db.fundings(item_id=collection_id, item_type="collection")
            categories    = self.db.categories(item_id=collection_id, item_type="collection")
            references    = self.db.references(item_id=collection_id, item_type="collection")
            custom_fields = self.db.custom_fields(item_id=collection_id, item_type="collection")
            tags          = self.db.tags(item_id=collection_id, item_type="collection")
            authors       = self.db.authors(item_id=collection_id, item_type="collection")
            total         = formatter.format_collection_details_record (collection,
                                                                        fundings,
                                                                        categories,
                                                                        references,
                                                                        tags,
                                                                        authors,
                                                                        custom_fields)
            return self.response (json.dumps(total))

        except IndexError:
            response = self.response (json.dumps({
                "message": "This collection cannot be found."
            }))
            response.status_code = 404
            return response

    def api_private_collections_search (self, request):
        handler = self.default_error_handling (request, "POST")
        if handler is not None:
            return handler

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        parameters = request.get_json()
        records = self.db.collections(
            resource_doi    = convenience.value_or_none(parameters, "resource_doi"),
            article_id      = convenience.value_or_none(parameters, "resource_id"),
            doi             = convenience.value_or_none(parameters, "doi"),
            handle          = convenience.value_or_none(parameters, "handle"),
            order           = convenience.value_or_none(parameters, "order"),
            search_for      = convenience.value_or_none(parameters, "search_for"),
            #page            = convenience.value_or_none(parameters, "page"),
            #page_size       = convenience.value_or_none(parameters, "page_size"),
            limit           = convenience.value_or_none(parameters, "limit"),
            offset          = convenience.value_or_none(parameters, "offset"),
            order_direction = convenience.value_or_none(parameters, "order_direction"),
            institution     = convenience.value_or_none(parameters, "institution"),
            published_since = convenience.value_or_none(parameters, "published_since"),
            modified_since  = convenience.value_or_none(parameters, "modified_since"),
            group           = convenience.value_or_none(parameters, "group"),
            account_id      = account_id
        )

        return self.default_list_response (records, formatter.format_article_record)

    def api_private_collection_authors (self, request, collection_id):
        handler = self.default_error_handling (request, "GET")
        if handler is not None:
            return handler

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        authors    = self.db.authors(item_id    = collection_id,
                                     account_id = account_id,
                                     item_type  = "collection")

        return self.default_list_response (authors, formatter.format_author_record)

    def api_private_collection_categories (self, request, collection_id):
        handler = self.default_error_handling (request, "GET")
        if handler is not None:
            return handler

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        categories    = self.db.categories(item_id    = collection_id,
                                           account_id = account_id,
                                           item_type  = "collection")

        return self.default_list_response (categories, formatter.format_category_record)

    def api_private_collection_articles (self, request, collection_id):
        handler = self.default_error_handling (request, "GET")
        if handler is not None:
            return handler

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        articles   = self.db.articles (collection_id = collection_id,
                                       account_id    = account_id)

        return self.default_list_response (articles, formatter.format_article_record)
