import os.path
import logging
import json
from werkzeug.wrappers import Request, Response
from werkzeug.utils import redirect
from werkzeug.urls import url_parse
from werkzeug.serving import run_simple
from werkzeug.routing import Map, Rule
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.exceptions import HTTPException, NotFound
from jinja2 import Environment, FileSystemLoader
from rdbackup.api import formatter
from rdbackup.api import database
from rdbackup.utils import convenience

class ApiServer:

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
            Rule("/v2/account/articles/<article_id>/files/<file_id>", endpoint = "private_article_file_details")
        ])

        ## Static resources and HTML templates.
        ## --------------------------------------------------------------------

        self.jinja   = Environment(loader = FileSystemLoader(
                        os.path.join(os.path.dirname(__file__),
                                     "resources/templates")),
                                     autoescape = True)

        self.wsgi    = SharedDataMiddleware(self.wsgi, {
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
        return Response(template.render(context), mimetype='text/html; charset=utf-8')

    def dispatch_request (self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            return getattr(self, f"api_{endpoint}")(request, **values)
        except NotFound:
            return self.error_404 (request)
        except HTTPException as e:
            logging.error(f"Unknown error in dispatch_request: {e}")
            return e

    def wsgi (self, environ, start_response):
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
        if self.accepts_html (request):
            return self.render_template ("404.html")
        else:
            response = Response(json.dumps({
                "message": "This call does not exist."
            }), mimetype='application/json; charset=utf-8')
        response.status_code = 404
        return response

    def error_405 (request, allowed_methods):
        response = Response(f"Acceptable methods: {allowed_methods}",
                            mimetype="text/plain")
        response.status_code = 405
        return response

    def error_406 (request, allowed_formats):
        response = Response(f"Acceptable formats: {allowed_formats}",
                            mimetype="text/plain")
        response.status_code = 406
        return response

    def error_authorization_failed (self):
        return Response(json.dumps({
            "message": "Invalid or unknown OAuth token",
            "code":    "OAuthInvalidToken"
        }), mimetype='application/json; charset=utf-8')

    ## CONVENIENCE PROCEDURES
    ## ------------------------------------------------------------------------

    def accepts_html (self, request):
        acceptable = request.headers['Accept']
        if not acceptable:
            return False
        else:
            return "text/html" in acceptable

    def accepts_json (self, request):
        acceptable = request.headers['Accept']
        if not acceptable:
            return False
        else:
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
            logging.error(f"Attempt to authenticate with {token} failed.")

        return account_id

    ## API CALLS
    ## ------------------------------------------------------------------------

    def api_home (self, request):
        if self.accepts_html (request):
            return self.render_template ("home.html")
        else:
            logging.info(f"Request: {request.environ}.")
            print(f"Environment: {request.environ}.")
            print(f"Headers: {request.headers['Accept']}.")

            return Response(json.dumps({ "status": "OK" }),
                            mimetype='application/json; charset=utf-8')

    def api_authorize (self, request):
        return False

    def api_token (self, request):
        return False

    def api_articles (self, request):
        if request.method != 'GET':
            return self.error_405 ("GET")
        elif not self.accepts_json(request):
            return self.error_406 ("application/json")
        else:
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
            output = []
            try:
                output = list(map (formatter.format_article_record, records))
            except TypeError:
                logging.error("api_articles: A TypeError occurred.")

            return Response(json.dumps(output),
                            mimetype='application/json; charset=utf-8')

    def api_articles_search (self, request):
        if request.method != 'POST':
            return self.error_405 ("POST")
        elif not self.accepts_json(request):
            return self.error_406 ("application/json")
        else:
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
            output  = []
            try:
                output = list(map (formatter.format_article_record, records))
            except TypeError:
                logging.error("api_articles_search: A TypeError occurred.")

            return Response(json.dumps(output),
                            mimetype='application/json; charset=utf-8')

    def api_article_details (self, request, article_id):
        if request.method != 'GET':
            return self.error_405 ("GET")
        elif not self.accepts_json(request):
            return self.error_406 ("application/json")
        else:
            article       = self.db.articles(id=article_id)[0]
            authors       = self.db.article_authors(article_id=article_id)
            files         = self.db.article_files(article_id=article_id)
            custom_fields = self.db.article_custom_fields(article_id=article_id)
            tags          = self.db.article_tags(article_id=article_id)
            categories    = self.db.article_categories(article_id=article_id)
            total         = formatter.format_article_details_record (article,
                                                                     authors,
                                                                     files,
                                                                     custom_fields,
                                                                     tags,
                                                                     categories)
            return Response(json.dumps(total),
                            mimetype='application/json; charset=utf-8')

    def api_article_files (self, request, article_id):
        if request.method != 'GET':
            return self.error_405 ("GET")
        elif not self.accepts_json(request):
            return self.error_406 ("application/json")
        else:
            files = self.db.article_files(article_id=article_id)
            results = list (map (formatter.format_file_for_article_record, files))
            return Response(json.dumps(results),
                            mimetype='application/json; charset=utf-8')

    def api_article_file_details (self, request, article_id, file_id):
        if request.method != 'GET':
            return self.error_405 ("GET")
        elif not self.accepts_json(request):
            return self.error_406 ("application/json")
        else:
            files = self.db.article_files(id=file_id, article_id=article_id)[0]
            results = formatter.format_file_for_article_record(files)
            return Response(json.dumps(results),
                            mimetype='application/json; charset=utf-8')

    def api_private_articles (self, request):
        if request.method != 'GET':
            return self.error_405 ("GET")
        elif not self.accepts_json(request):
            return self.error_406 ("application/json")
        else:
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
            output = []
            try:
                output = list(map (formatter.format_article_record, records))
            except TypeError:
                logging.error("api_private_articles: A TypeError occurred.")

            return Response(json.dumps(output),
                            mimetype='application/json; charset=utf-8')

    def api_private_article_details (self, request, article_id):
        if request.method != 'GET':
            return self.error_405 ("GET")
        elif not self.accepts_json(request):
            return self.error_406 ("application/json")
        else:
            ## Authorization
            ## ----------------------------------------------------------------
            account_id = self.account_id_from_request (request)
            if account_id is None:
                return self.error_authorization_failed()

            article       = self.db.articles (id=article_id, account_id=account_id)
            if not article:
                return Response(json.dumps([]),
                                mimetype='application/json; charset=utf-8')

            article       = article[0]
            authors       = self.db.article_authors(article_id=article_id)
            files         = self.db.article_files(article_id=article_id)
            custom_fields = self.db.article_custom_fields(article_id=article_id)
            tags          = self.db.article_tags(article_id=article_id)
            categories    = self.db.article_categories(article_id=article_id)
            total         = formatter.format_article_details_record (article,
                                                                     authors,
                                                                     files,
                                                                     custom_fields,
                                                                     tags,
                                                                     categories)

            return Response(json.dumps(total),
                            mimetype='application/json; charset=utf-8')

    def api_private_article_authors (self, request, article_id):
        if request.method != 'GET':
            return self.error_405 ("GET")
        elif not self.accepts_json(request):
            return self.error_406 ("application/json")
        else:
            ## Authorization
            ## ----------------------------------------------------------------
            account_id = self.account_id_from_request (request)
            if account_id is None:
                return self.error_authorization_failed()


            authors       = self.db.article_authors(article_id = article_id,
                                                    account_id = account_id)
            if not authors:
                return Response(json.dumps([]),
                                mimetype='application/json; charset=utf-8')
            output        = list (map (formatter.format_author_for_article_record, authors))

            return Response(json.dumps(output),
                            mimetype='application/json; charset=utf-8')

    def api_private_article_categories (self, request, article_id):
        if request.method != 'GET':
            return self.error_405 ("GET")
        elif not self.accepts_json(request):
            return self.error_406 ("application/json")
        else:
            ## Authorization
            ## ----------------------------------------------------------------
            account_id = self.account_id_from_request (request)
            if account_id is None:
                return self.error_authorization_failed()

            categories    = self.db.article_categories(article_id = article_id,
                                                       account_id = account_id)
            if not categories:
                return Response(json.dumps([]),
                                mimetype='application/json; charset=utf-8')

            output        = list (map (formatter.format_category_for_article_record, categories))

            return Response(json.dumps(output),
                            mimetype='application/json; charset=utf-8')

    def api_private_article_files (self, request, article_id):
        if request.method != 'GET':
            return self.error_405 ("GET")
        elif not self.accepts_json(request):
            return self.error_406 ("application/json")
        else:
            ## Authorization
            ## ----------------------------------------------------------------
            account_id = self.account_id_from_request (request)
            if account_id is None:
                return self.error_authorization_failed()

            files         = self.db.article_files (article_id = article_id,
                                                   account_id = account_id)
            if not files:
                return Response(json.dumps([]),
                                mimetype='application/json; charset=utf-8')

            output        = list (map (formatter.format_file_for_article_record, files))

            return Response(json.dumps(output),
                            mimetype='application/json; charset=utf-8')

    def api_private_article_file_details (self, request, article_id, file_id):
        if request.method != 'GET':
            return self.error_405 ("GET")
        elif not self.accepts_json(request):
            return self.error_406 ("application/json")
        else:
            ## Authorization
            ## ----------------------------------------------------------------
            account_id = self.account_id_from_request (request)
            if account_id is None:
                return self.error_authorization_failed()

            files         = self.db.article_files (article_id = article_id,
                                                   account_id = account_id,
                                                   id         = file_id)
            if not files:
                return Response(json.dumps([]),
                                mimetype='application/json; charset=utf-8')

            output        = list (map (formatter.format_file_details_record, files))

            return Response(json.dumps(output),
                            mimetype='application/json; charset=utf-8')

    def api_private_articles_search (self, request):
        if request.method != 'POST':
            return self.error_405 ("POST")
        elif not self.accepts_json(request):
            return self.error_406 ("application/json")
        else:
            parameters = request.get_json()
            records = self.db.articles(
                resource_doi    = convenience.value_or_none(parameters, "resource_doi"),
                id              = convenience.value_or_none(parameters, "resource_id"),
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
            )
            output  = []
            try:
                output = list(map (formatter.format_article_record, records))
            except TypeError:
                logging.error("api_articles_search: A TypeError occurred.")

            return Response(json.dumps(output),
                            mimetype='application/json; charset=utf-8')
