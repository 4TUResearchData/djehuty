"""This module implements the API server."""

import os.path
import logging
import json
from typing import NamedTuple
from werkzeug.utils import redirect
from werkzeug.wrappers import Request, Response
from werkzeug.serving import run_simple
from werkzeug.routing import Map, Rule
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.exceptions import HTTPException, NotFound
from jinja2 import Environment, FileSystemLoader
from djehuty.api import validator
from djehuty.api import formatter
from djehuty.api import database
from djehuty.utils import convenience

class Account(NamedTuple):
    """Named tuple to keep settings for an account."""
    account_id: int
    may_impersonate: bool

class ApiServer:
    """This class implements the API server."""

    ## INITIALISATION
    ## ------------------------------------------------------------------------

    def __init__ (self, address="127.0.0.1", port=8080):
        self.address          = address
        self.port             = port
        self.base_url         = f"http://{self.address}:{self.port}"
        self.db               = database.SparqlInterface()

        ## This is a temporary predefined set of tokens to test the private
        ## articles functionality.
        self.tokens           = {
            "2bc2d4c4ea5e3c5f3da70e2aa697c51730d66adadc5c4503e0ff7b4541683b99": Account(2391394, True),
            "e33bfd5e4b05a342f496f53939d4ab29d835d7bbe2d925b69d40a712908ccddc": Account(2397553, True),
            "60b2a1fbae694cb7c85105aeaa57a2d04644f078db32c23732b420c68abb0efe": Account(1000002, False)
        }

        self.defined_type_options = [
            "figure", "online resource", "preprint", "book",
            "conference contribution", "media", "dataset",
            "poster", "journal contribution", "presentation",
            "thesis", "software"
        ]

        ## Routes to all API calls.
        ## --------------------------------------------------------------------

        self.url_map = Map([
            ## ----------------------------------------------------------------
            ## UI
            ## ----------------------------------------------------------------
            Rule("/",                                         endpoint = "home"),
            Rule("/portal",                                   endpoint = "portal"),
            Rule("/agriculture-animal-plant-sciences",        endpoint = "agriculture_animal_plant_sciences"),
            Rule("/chemistry",                                endpoint = "chemistry"),

            ## ----------------------------------------------------------------
            ## API
            ## ----------------------------------------------------------------
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
            Rule("/v2/account/collections/<collection_id>/categories", endpoint = "private_collection_categories"),
            Rule("/v2/account/collections/<collection_id>/articles", endpoint = "private_collection_articles"),

            ## ----------------------------------------------------------------
            ## V3 API
            ## ----------------------------------------------------------------
            Rule("/v3/articles",                              endpoint = "v3_articles"),
            Rule("/v3/articles/top/<item_type>",              endpoint = "v3_articles_top"),
            Rule("/v3/articles/timeline/<item_type>",         endpoint = "v3_articles_timeline"),
          ])

        ## Static resources and HTML templates.
        ## --------------------------------------------------------------------

        self.jinja   = Environment(loader = FileSystemLoader(
                        os.path.join(os.path.dirname(__file__),
                                     "resources/html_templates")),
                                     autoescape = True)

        self.wsgi    = SharedDataMiddleware(self.__respond, {
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

    def __render_template (self, template_name, **context):
        template = self.jinja.get_template (template_name)
        return self.response (template.render(context),
                              mimetype='text/html; charset=utf-8')

    def __dispatch_request (self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            return getattr(self, f"api_{endpoint}")(request, **values)
        except NotFound:
            return self.error_404 (request)
        except HTTPException as error:
            logging.error("Unknown error in dispatch_request: %s", error)
            return error

    def __respond (self, environ, start_response):
        request  = Request(environ)
        response = self.__dispatch_request(request)
        return response(environ, start_response)

    def start (self):
        run_simple (self.address,
                    self.port,
                    self,
                    use_debugger=True,
                    use_reloader=False)

    ## ERROR HANDLERS
    ## ------------------------------------------------------------------------

    def error_400 (self, message, code):
        response = self.response (json.dumps({
            "message": message,
            "code":    code
        }))
        response.status_code = 400
        return response

    def error_403 (self, request):
        response = None
        if self.accepts_html (request):
            response = self.__render_template ("403.html")
        else:
            response = self.response (json.dumps({
                "message": "Not allowed."
            }))
        response.status_code = 403
        return response

    def error_404 (self, request):
        response = None
        if self.accepts_html (request):
            response = self.__render_template ("404.html")
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

    def error_500 (self):
        response = self.response ("")
        response.status_code = 500
        return response

    def error_authorization_failed (self):
        response = self.response (json.dumps({
            "message": "Invalid or unknown OAuth token",
            "code":    "OAuthInvalidToken"
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


    def token_from_request (self, request):
        token_string = None
        token = ""

        ## Get the token from the "Authorization" HTTP header.
        ## If no such header is provided, we cannot authenticate.
        try:
            token_string = request.environ["HTTP_AUTHORIZATION"]
        except KeyError:
            return None

        if token_string.startswith("token "):
            token = token_string[6:]

        return token

    def impersonated_account_id (self, request, account):
        try:
            if account.may_impersonate:
                ## Handle the "impersonate" URL parameter.
                impersonate = self.get_parameter (request, "impersonate")

                ## "impersonate" can also be passed in the request body.
                if impersonate is None:
                    body  = request.get_json()
                    impersonate = convenience.value_or_none (body, "impersonate")

                if impersonate is not None:
                    return impersonate
        except KeyError:
            return account.account_id

        return account.account_id

    def account_id_from_request (self, request):
        account_id = None
        token = self.token_from_request (request)

        ## Match the token to an account_id.  If the token does not
        ## exist, we cannot authenticate.
        try:
            account_id = self.impersonated_account_id (request, self.tokens[token])
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

    def api_portal (self, request):
        if self.accepts_html (request):
            summary_data = self.db.repository_statistics()
            return self.__render_template ("portal.html",
                                           base_url=self.base_url,
                                           summary_data=summary_data)

        return self.response (json.dumps({
            "message": "This page is meant for humans only."
        }))

    def api_agriculture_animal_plant_sciences (self, request):
        if self.accepts_html (request):
            return self.__render_template ("agriculture-animal-plant-sciences.html", base_url=self.base_url)

        return self.response (json.dumps({
            "message": "This page is meant for humans only."
        }))

    def api_chemistry (self, request):
        if self.accepts_html (request):
            return self.__render_template ("chemistry.html", base_url=self.base_url)

        return self.response (json.dumps({
            "message": "This page is meant for humans only."
        }))

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

        try:
            validator.limit (limit)
            validator.offset (offset)
            validator.order_direction (order_direction)
            validator.institution (institution)
            validator.group (group)
        except validator.ValidationException as error:
            return self.error_400 (error.message, error.code)

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

    def api_article_versions (self, request, article_id):
        if request.method != 'GET':
            return self.error_405 ("GET")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        versions = self.db.article_versions(article_id=article_id)
        return self.default_list_response (versions, formatter.format_version_record)

    def api_article_version_details (self, request, article_id, version):
        if request.method != 'GET':
            return self.error_405 ("GET")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        try:
            article       = self.db.articles(article_id=article_id, version=version)[0]
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

    def api_article_version_embargo (self, request, article_id, version):
        if request.method != 'GET':
            return self.error_405 ("GET")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        try:
            article         = self.db.articles (article_id=article_id, version=version)[0]
            embargo_options = self.db.article_embargo_options (article_id=article_id)
            total           = formatter.format_article_embargo_record (article, embargo_options)
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
            article         = self.db.articles (article_id=article_id, version=version)[0]
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
            return self.error_authorization_failed()

        parameters = request.get_json()
        file_id    = convenience.value_or_none (parameters, "file_id")
        if not self.db.article_update_thumb (article_id, version, account_id, file_id):
            return self.respond_205()

        return self.error_500()

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
        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        if request.method == 'GET':

            ## Parameters
            ## ----------------------------------------------------------------
            page            = self.get_parameter (request, "page")
            page_size       = self.get_parameter (request, "page_size")
            limit           = self.get_parameter (request, "limit")
            offset          = self.get_parameter (request, "offset")

            try:
                validator.page (page)
                validator.page_size (page_size)
                validator.limit (limit)
                validator.offset (offset)
            except validator.ValidationException as error:
                return self.error_400 (error.message, error.code)

            records = self.db.articles(#page=page,
                                       #page_size=page_size,
                                       limit=limit,
                                       offset=offset,
                                       account_id=account_id)

            return self.default_list_response (records, formatter.format_article_record)

        if request.method == 'POST':
            record = request.get_json()

            try:
                timeline   = validator.object_value (record, "timeline", False)
                article_id = self.db.insert_article (
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
                    "location": f"http://{self.address}:{self.port}/v2/account/articles/{article_id}",
                    "warnings": []
                }))
            except validator.ValidationException as error:
                return self.error_400 (error.message, error.code)

        return self.error_405 (["GET", "POST"])

    def api_private_article_details (self, request, article_id):

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        if request.method == 'GET':
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

        if request.method == 'DELETE':
            if self.db.delete_article (article_id, account_id):
                return self.respond_204()
            return self.error_500 ()

        return self.error_405 (["GET", "DELETE"])

    def api_private_article_authors (self, request, article_id):
        """Implements /v2/account/articles/<id>/authors."""

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        article_id = int(article_id)

        if request.method == 'GET':
            authors    = self.db.authors(item_id    = article_id,
                                         account_id = account_id,
                                         item_type  = "article")

            return self.default_list_response (authors, formatter.format_author_record)

        if request.method == 'PUT':
            parameters = request.get_json()
            try:
                records = parameters["authors"]
                author_ids = []
                for record in records:
                    author_id = self.db.insert_author (
                        author_id  = validator.integer_value (record, "id",         0, pow(2, 63), False),
                        full_name  = validator.string_value  (record, "name",       0, 255,        False),
                        first_name = validator.string_value  (record, "first_name", 0, 255,        False),
                        last_name  = validator.string_value  (record, "last_name",  0, 255,        False),
                        email      = validator.string_value  (record, "email",      0, 255,        False),
                        orcid_id   = validator.string_value  (record, "orcid_id",   0, 255,        False),
                        job_title  = validator.string_value  (record, "job_title",  0, 255,        False),
                        is_active  = False,
                        is_public  = True)
                    if author_id is None:
                        logging.error("Adding a single author failed.")
                        return self.error_500()

                    author_ids.append(author_id)

                self.db.delete_authors_for_article (article_id, account_id)
                for author_id in author_ids:
                    if self.db.insert_article_author (article_id, author_id) is None:
                        logging.error("Adding a single author failed.")
                        return self.error_500()

            except KeyError:
                self.error_400 ("Expected an 'authors' field.", "NoAuthorsField")
            except validator.ValidationException as error:
                return self.error_400 (error.message, error.code)
            except Exception as error:
                logging.error("An error occurred when adding an author record:")
                logging.error("Exception: %s", error)

            return self.error_500()

        if request.method == 'POST':
            ## The 'parameters' will be a dictionary containing a key "authors",
            ## which can contain multiple dictionaries of author records.
            parameters = request.get_json()

            try:
                records = parameters["authors"]
                for record in records:
                    # The following fields are allowed:
                    # id, name, first_name, last_name, email, orcid_id, job_title.
                    #
                    # We assume values for is_active and is_public.
                    author_id = self.db.insert_author (
                        author_id  = validator.integer_value (record, "id",         0, pow(2, 63), False),
                        full_name  = validator.string_value  (record, "name",       0, 255,        False),
                        first_name = validator.string_value  (record, "first_name", 0, 255,        False),
                        last_name  = validator.string_value  (record, "last_name",  0, 255,        False),
                        email      = validator.string_value  (record, "email",      0, 255,        False),
                        orcid_id   = validator.string_value  (record, "orcid_id",   0, 255,        False),
                        job_title  = validator.string_value  (record, "job_title",  0, 255,        False),
                        is_active  = False,
                        is_public  = True)
                    if author_id is None:
                        logging.error("Adding a single author failed.")
                        return self.error_500()

                    if self.db.insert_article_author (article_id, author_id) is None:
                        logging.error("Adding a single author failed.")
                        return self.error_500()

                return self.respond_205()

            except KeyError:
                self.error_400 ("Expected an 'authors' field.", "NoAuthorsField")
            except validator.ValidationException as error:
                return self.error_400 (error.message, error.code)
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
            return self.error_authorization_failed()

        result = self.db.delete_authors_for_article (article_id, account_id, author_id)
        if result is not None:
            return self.respond_204()

        return self.error_403 (request)

    def api_private_article_categories (self, request, article_id):

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        if request.method == 'GET':
            categories    = self.db.categories(item_id    = article_id,
                                               account_id = account_id,
                                               item_type  = "article")

            return self.default_list_response (categories, formatter.format_category_record)

        if request.method == 'PUT' or request.method == 'POST':
            try:
                parameters = request.get_json()
                categories = parameters["categories"]

                # First, validate all values passed by the user.
                # This way, we can be as certain as we can be that performing
                # a PUT will not end in having no categories associated with
                # an article.
                for index, category_id in enumerate(categories):
                    validator.integer_value (categories, index)

                # When we are dealing with a PUT request, we must clear the previous
                # values first.
                if request.method == 'PUT':
                    self.db.delete_article_categories (article_id, account_id)

                # Lastly, insert the validated values.
                for category_id in categories:
                    self.db.insert_article_category (int(article_id), int(category_id))

                return self.respond_205()

            except KeyError:
                self.error_400 ("Expected an array for 'categories'.", "NoCategoriesField")
            except validator.ValidationException as error:
                return self.error_400 (error.message, error.code)
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
            return self.error_authorization_failed()

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
            return self.error_authorization_failed()

        if request.method == 'GET':
            article    = self.db.articles (article_id=article_id, account_id=account_id)
            if not article:
                return self.response (json.dumps([]))

            try:
                article = article[0]
                options = self.db.article_embargo_options(article_id = article_id)
                return self.response (json.dumps (formatter.format_article_embargo_record (article, options)))
            except IndexError:
                response = self.response (json.dumps({
                    "message": "No embargo options found."
                }))
                response.status_code = 404
                return response

        if request.method == 'DELETE':
            if self.db.delete_article_embargo (article_id=article_id, account_id=account_id):
                return self.respond_204()
            return self.error_500 ()

        return self.error_405 (["GET", "DELETE"])

    def api_private_article_files (self, request, article_id):

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        if request.method == 'GET':
            files         = self.db.article_files (article_id = article_id,
                                                   account_id = account_id)

            return self.default_list_response (files, formatter.format_file_for_article_record)

        if request.method == 'POST':
            parameters = request.get_json()
            try:
                link = validator.string_value (parameters, "link", 0, 1000, False)
                if link is not None:
                    file_id = self.db.insert_file (is_link_only=True, download_url=link)
                    if file_id is None:
                        return self.error_500()

                    link_id = self.db.insert_article_file (int(article_id), file_id)
                    if link_id is None:
                        return self.error_500()

                    return self.respond_201({
                        "location": f"{self.base_url}/v2/account/articles/{article_id}/files/{file_id}"
                    })

                file_id = self.db.insert_file (
                    is_link_only  = False,
                    upload_token  = self.token_from_request (request),
                    supplied_md5  = validator.string_value  (parameters, "md5",  32, 32,         False),
                    name          = validator.string_value  (parameters, "name", 0,  255,        True),
                    size          = validator.integer_value (parameters, "size", 0,  pow(2, 63), True))
                if file_id is None:
                    return self.error_500()

                link_id = self.db.insert_article_file (int(article_id), file_id)
                if link_id is None:
                    return self.error_500()

                return self.respond_201({
                    "location": f"{self.base_url}/v2/account/articles/{article_id}/files/{file_id}"
                })

            except validator.ValidationException as error:
                return self.error_400 (error.message, error.code)

        return self.error_405 (["GET", "POST"])

    def api_private_article_file_details (self, request, article_id, file_id):

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        if request.method == 'GET':
            files         = self.db.article_files (article_id = article_id,
                                                   account_id = account_id,
                                                   file_id    = file_id)

            return self.default_list_response (files, formatter.format_file_details_record)

        if request.method == 'DELETE':
            result = self.db.delete_file_for_article (article_id = article_id,
                                                      account_id = account_id,
                                                      file_id    = file_id)
            if result is not None:
                return self.respond_204()

            return self.error_500()

        return self.error_405 (["GET", "POST", "DELETE"])

    def api_private_article_private_links (self, request, article_id):

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        if request.method == 'GET':
            links = self.db.private_links (
                        item_id    = article_id,
                        account_id = account_id,
                        item_type  = "article")

            return self.default_list_response (links, formatter.format_private_links_record)

        if request.method == 'POST':
            parameters = request.get_json()
            try:
                expires_date = validator.string_value (parameters, "expires_date", 0, 255, False)
                read_only    = validator.boolean_value (parameters, "read_only", False)
                id_string    = self.db.insert_private_link (
                                   expires_date = expires_date,
                                   read_only    = read_only,
                                   is_active    = True,
                                   item_id      = int(article_id),
                                   item_type    = "article")

                if id_string is None:
                    return self.error_500()

                return self.response(json.dumps({
                    "location": f"{self.base_url}/articles/{id_string}"
                }))

            except validator.ValidationException as error:
                return self.error_400 (error.message, error.code)

            return self.error_500 ()
            # INSERT and return { "location": id_string }

        return self.error_500 ()

    def api_private_article_private_links_details (self, request, article_id, link_id):

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        if request.method == 'GET':
            links = self.db.private_links (
                        item_id    = article_id,
                        id_string  = link_id,
                        account_id = account_id,
                        item_type  = "article")

            return self.default_list_response (links, formatter.format_private_links_record)

        if request.method == 'PUT':
            parameters = request.get_json()
            try:
                expires_date = validator.string_value (parameters, "expires_date", 0, 255, False)
                is_active    = validator.boolean_value (parameters, "is_active", False)

                result = self.db.update_private_link (article_id,
                                                      account_id,
                                                      link_id,
                                                      expires_date = expires_date,
                                                      is_active    = is_active,
                                                      item_type    = "article")

                if result is None:
                    return self.error_500()

                return self.response(json.dumps({
                    "location": f"{self.base_url}/articles/{link_id}"
                }))

            except validator.ValidationException as error:
                return self.error_400 (error.message, error.code)

            return self.error_500 ()

        if request.method == 'DELETE':
            result = self.db.delete_private_links (article_id,
                                                  account_id,
                                                  link_id,
                                                  item_type    = "article")

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

        try:
            validator.page (page)
            validator.page_size (page_size)
            validator.limit (limit)
            validator.offset (offset)
            validator.order_direction (order_direction)
            validator.institution (institution)
            validator.group (group)
        except validator.ValidationException as error:
            return self.error_400 (error.message, error.code)

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
            articles_count= self.db.collections_article_count(collection_id=collection_id)
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
                                                                        custom_fields,
                                                                        articles_count)
            return self.response (json.dumps(total))

        except IndexError:
            response = self.response (json.dumps({
                "message": "This collection cannot be found."
            }))
            response.status_code = 404
            return response

    def api_collection_versions (self, request, collection_id):
        if request.method != 'GET':
            return self.error_405 ("GET")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        versions = self.db.collection_versions(collection_id=collection_id)
        return self.default_list_response (versions, formatter.format_version_record)

    def api_collection_version_details (self, request, collection_id, version):
        if request.method != 'GET':
            return self.error_405 ("GET")

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        try:
            collection    = self.db.collections(collection_id=collection_id, limit=1, version=version)[0]
            articles_count= self.db.collections_article_count(collection_id=collection_id)
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
                                                                        custom_fields,
                                                                        articles_count)
            return self.response (json.dumps(total))
        except IndexError:
            response = self.response (json.dumps({
                "message": "This collection cannot be found."
            }))
            response.status_code = 404
            return response

    def api_private_collections (self, request):

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        if request.method == 'GET':
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
                    "location": f"http://{self.address}:{self.port}/v2/account/collections/{collection_id}",
                    "warnings": []
                }))
            except validator.ValidationException as error:
                return self.error_400 (error.message, error.code)

        return self.error_405 (["GET", "POST"])


    def api_private_collection_details (self, request, collection_id):

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        if request.method == 'GET':
            try:
                collection    = self.db.collections(collection_id = collection_id,
                                                    account_id    = account_id,
                                                    limit         = 1)[0]
                articles_count= self.db.collections_article_count(collection_id=collection_id)
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
                                                                            custom_fields,
                                                                            articles_count)
                return self.response (json.dumps(total))

            except IndexError:
                response = self.response (json.dumps({
                    "message": "This collection cannot be found."
                }))
                response.status_code = 404
                return response

        if request.method == 'DELETE':
            if self.db.delete_collection (collection_id, account_id):
                return self.respond_204()

        return self.error_500 ()

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
            resource_id     = convenience.value_or_none(parameters, "resource_id"),
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
        """Implements /v2/account/collections/<id>/authors."""

        if not self.accepts_json(request):
            return self.error_406 ("application/json")

        ## Authorization
        ## ----------------------------------------------------------------
        account_id = self.account_id_from_request (request)
        if account_id is None:
            return self.error_authorization_failed()

        collection_id = int(collection_id)

        if request.method == 'GET':
            authors    = self.db.authors(item_id    = collection_id,
                                         account_id = account_id,
                                         item_type  = "collection")

            return self.default_list_response (authors, formatter.format_author_record)

        if request.method == 'PUT':
            parameters = request.get_json()
            try:
                records = parameters["authors"]
                author_ids = []
                for record in records:
                    author_id = self.db.insert_author (
                        author_id  = validator.integer_value (record, "id",         0, pow(2, 63), False),
                        full_name  = validator.string_value  (record, "name",       0, 255,        False),
                        first_name = validator.string_value  (record, "first_name", 0, 255,        False),
                        last_name  = validator.string_value  (record, "last_name",  0, 255,        False),
                        email      = validator.string_value  (record, "email",      0, 255,        False),
                        orcid_id   = validator.string_value  (record, "orcid_id",   0, 255,        False),
                        job_title  = validator.string_value  (record, "job_title",  0, 255,        False),
                        is_active  = False,
                        is_public  = True)
                    if author_id is None:
                        logging.error("Adding a single author failed.")
                        return self.error_500()

                    author_ids.append(author_id)

                self.db.delete_authors_for_collection (collection_id, account_id)
                for author_id in author_ids:
                    if self.db.insert_collection_author (collection_id, author_id) is None:
                        logging.error("Adding a single author failed.")
                        return self.error_500()

            except KeyError:
                self.error_400 ("Expected an 'authors' field.", "NoAuthorsField")
            except validator.ValidationException as error:
                return self.error_400 (error.message, error.code)
            except Exception as error:
                logging.error("An error occurred when adding an author record:")
                logging.error("Exception: %s", error)

            return self.error_500()

        if request.method == 'POST':
            ## The 'parameters' will be a dictionary containing a key "authors",
            ## which can contain multiple dictionaries of author records.
            parameters = request.get_json()

            try:
                records = parameters["authors"]
                for record in records:
                    # The following fields are allowed:
                    # id, name, first_name, last_name, email, orcid_id, job_title.
                    #
                    # We assume values for is_active and is_public.
                    author_id = self.db.insert_author (
                        author_id  = validator.integer_value (record, "id",         0, pow(2, 63), False),
                        full_name  = validator.string_value  (record, "name",       0, 255,        False),
                        first_name = validator.string_value  (record, "first_name", 0, 255,        False),
                        last_name  = validator.string_value  (record, "last_name",  0, 255,        False),
                        email      = validator.string_value  (record, "email",      0, 255,        False),
                        orcid_id   = validator.string_value  (record, "orcid_id",   0, 255,        False),
                        job_title  = validator.string_value  (record, "job_title",  0, 255,        False),
                        is_active  = False,
                        is_public  = True)
                    if author_id is None:
                        logging.error("Adding a single author failed.")
                        return self.error_500()

                    if self.db.insert_collection_author (collection_id, author_id) is None:
                        logging.error("Adding a single author failed.")
                        return self.error_500()

                return self.respond_205()

            except KeyError:
                self.error_400 ("Expected an 'authors' field.", "NoAuthorsField")
            except validator.ValidationException as error:
                return self.error_400 (error.message, error.code)
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

    def api_collection_articles (self, request, collection_id):
        handler = self.default_error_handling (request, "GET")
        if handler is not None:
            return handler

        articles   = self.db.articles (collection_id = collection_id)
        return self.default_list_response (articles, formatter.format_article_record)

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

        except validator.ValidationException as error:
            return self.error_400 (error.message, error.code)

        records = self.db.articles (limit           = record["limit"],
                                    offset          = record["offset"],
                                    order           = record["order"],
                                    order_direction = record["order_direction"],
                                    institution     = record["institution"],
                                    published_since = record["published_since"],
                                    modified_since  = record["modified_since"],
                                    group           = record["group"],
                                    resource_doi    = record["resource_doi"],
                                    item_type       = record["item_type"],
                                    doi             = record["doi"],
                                    handle          = record["handle"],
                                    category_ids    = record["categories"],
                                    return_count    = record["return_count"])
        if record["return_count"]:
            return self.response (json.dumps(records[0]))

        return self.default_list_response (records, formatter.format_article_record)

    def __api_v3_articles_parameters (self, request, item_type):
        record = {}
        record["article_id"]      = self.get_parameter (request, "article_id")
        record["limit"]           = self.get_parameter (request, "limit")
        record["offset"]          = self.get_parameter (request, "offset")
        record["order"]           = self.get_parameter (request, "order")
        record["order_direction"] = self.get_parameter (request, "order_direction")
        record["categories"]      = self.get_parameter (request, "categories")
        record["item_type"]       = item_type

        validator.integer_value (record, "article_id")
        validator.integer_value (record, "limit")
        validator.integer_value (record, "offset")
        validator.string_value  (record, "order", maximum_length=32)
        validator.order_direction (record["order_direction"])
        validator.string_value  (record, "item_type", maximum_length=32)

        if item_type not in {"downloads", "views", "shares", "cites"}:
            raise validator.InvalidValue(
                message = "The last URL parameter must be one of 'downloads', 'views', 'shares' or 'cites'.",
                code    = "InvalidURLParameterValue")

        if record["categories"] is not None:
            record["categories"] = record["categories"].split(",")
            validator.array_value   (record, "categories")
            for index, _ in enumerate(record["categories"]):
                record["categories"][index] = validator.integer_value (record["categories"], index)

        return record

    def api_v3_articles_top (self, request, item_type):
        handler = self.default_error_handling (request, "GET")
        if handler is not None:
            return handler

        record = {}
        try:
            record = self.__api_v3_articles_parameters (request, item_type)

        except validator.ValidationException as error:
            return self.error_400 (error.message, error.code)

        records = self.db.article_statistics (
            limit           = record["limit"],
            offset          = record["offset"],
            order           = record["order"],
            order_direction = record["order_direction"],
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
            return self.error_400 (error.message, error.code)

        records = self.db.article_statistics_timeline (
            article_id      = record["article_id"],
            limit           = record["limit"],
            offset          = record["offset"],
            order           = record["order"],
            order_direction = record["order_direction"],
            category_ids    = record["categories"],
            item_type       = item_type)

        return self.response (json.dumps(records))
