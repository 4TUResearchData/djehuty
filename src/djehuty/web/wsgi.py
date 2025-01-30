"""This module implements the entire HTTP interface for users."""

from datetime import date, datetime, timedelta
from urllib.parse import quote, unquote
from io import StringIO
import os
import shutil
import tempfile
import getpass
import logging
import json
import hashlib
import subprocess
import secrets
import re
import base64
import csv
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
from PIL import Image, ImageSequence, UnidentifiedImageError
from djehuty.web import validator
from djehuty.web import formatter
from djehuty.web import xml_formatter
from djehuty.web import database
from djehuty.web import email_handler
from djehuty.web import locks
from djehuty.utils.convenience import pretty_print_size, decimal_coords
from djehuty.utils.convenience import value_or, value_or_none, deduplicate_list
from djehuty.utils.convenience import self_or_value_or_none, parses_to_int
from djehuty.utils.convenience import make_citation, is_opendap_url, landing_page_url
from djehuty.utils.convenience import split_author_name, split_string, html_to_plaintext
from djehuty.utils.constants import group_to_member, member_url_names, filetypes_by_extension
from djehuty.utils.rdf import uuid_to_uri, uri_to_uuid, uris_from_records
from djehuty.web.config import config
from djehuty.web import zipfly

## Error handling for loading python3-saml is done in 'ui'.
## So if it fails here, we can safely assume we don't need it.
try:
    from onelogin.saml2.auth import OneLogin_Saml2_Auth
    from onelogin.saml2.errors import OneLogin_Saml2_Error
    from xmlsec import Error as xmlsecError
except (ImportError, ModuleNotFoundError):
    pass

## Similarly, error handling for loading pyvips is done in 'ui'.
try:
    import pyvips
except (OSError, ImportError, ModuleNotFoundError):
    pass

def R (uri_path, endpoint):  # pylint: disable=invalid-name
    """
    Short-hand for defining a route between a URI and its
    entry-point procedure.
    """
    return Rule (uri_path, endpoint=endpoint)

class WebServer:
    """This class implements the HTTP interface for users."""

    def __init__ (self, address="127.0.0.1", port=8080):
        config.base_url         = f"http://{address}:{port}"
        self.db               = database.SparqlInterface()  # pylint: disable=invalid-name
        self.email            = email_handler.EmailInterface()
        self.cookie_key       = "djehuty_session"
        self.impersonator_cookie_key = f"impersonator_{self.cookie_key}"
        self.log_access          = self.log_access_directly
        self.log                 = logging.getLogger(__name__)
        self.locks               = locks.Locks()
        self.static_pages = {}

        ## Routes to all reachable pages and API calls.
        ## --------------------------------------------------------------------

        self.url_map = Map([
            ## ----------------------------------------------------------------
            ## UI
            ## ----------------------------------------------------------------
            R("/",                                                               self.ui_home),
            R("/portal",                                                         self.ui_redirect_to_home),
            R("/browse",                                                         self.ui_redirect_to_home),
            R("/robots.txt",                                                     self.robots_txt),
            R("/theme/colors.css",                                               self.colors_css),
            R("/theme/loader.svg",                                               self.loader_svg),
            R("/login",                                                          self.ui_login),
            R("/account/home",                                                   self.ui_account_home),
            R("/logout",                                                         self.ui_logout),
            R("/my/dashboard",                                                   self.ui_dashboard),
            R("/my/datasets",                                                    self.ui_my_data),
            R("/my/datasets/<dataset_id>/edit",                                  self.ui_edit_dataset),
            R("/my/datasets/<dataset_id>/delete",                                self.ui_delete_dataset),
            R("/my/datasets/<dataset_uuid>/private_links",                       self.ui_dataset_private_links),
            R("/my/datasets/<dataset_uuid>/private_link/<link_id>/delete",       self.ui_dataset_delete_private_link),
            R("/my/datasets/<dataset_uuid>/private_link/new",                    self.ui_dataset_new_private_link),
            R("/my/datasets/new",                                                self.ui_new_dataset),
            R("/my/datasets/<dataset_id>/new-version-draft",                     self.ui_new_version_draft_dataset),
            R("/my/datasets/submitted-for-review",                               self.ui_dataset_submitted),
            R("/my/collections",                                                 self.ui_my_collections),
            R("/my/collections/<collection_id>/edit",                            self.ui_edit_collection),
            R("/my/collections/<collection_id>/delete",                          self.ui_delete_collection),
            R("/my/collections/<collection_uuid>/private_links",                 self.ui_collection_private_links),
            R("/my/collections/<collection_uuid>/private_link/<link_id>/delete", self.ui_collection_delete_private_link),
            R("/my/collections/<collection_uuid>/private_link/new",              self.ui_collection_new_private_link),
            R("/my/collections/new",                                             self.ui_new_collection),
            R("/my/collections/<collection_id>/new-version-draft",               self.ui_new_version_draft_collection),
            R("/my/sessions/<session_uuid>/edit",                                self.ui_edit_session),
            R("/my/sessions/<session_uuid>/delete",                              self.ui_delete_session),
            R("/my/sessions/<session_uuid>/activate",                            self.ui_activate_session),
            R("/my/sessions/new",                                                self.ui_new_session),
            R("/my/profile",                                                     self.ui_profile),
            R("/my/profile/connect-with-orcid",                                  self.ui_profile_connect_with_orcid),
            R("/review/overview",                                                self.ui_review_overview),
            R("/review/goto-dataset/<dataset_id>",                               self.ui_review_impersonate_to_dataset),
            R("/review/assign-to-me/<dataset_id>",                               self.ui_review_assign_to_me),
            R("/review/unassign/<dataset_id>",                                   self.ui_review_unassign),
            R("/review/published/<dataset_id>",                                  self.ui_review_published),
            R("/admin/approve-quota-request/<quota_request_uuid>",               self.ui_admin_approve_quota_request),
            R("/admin/dashboard",                                                self.ui_admin_dashboard),
            R("/admin/deny-quota-request/<quota_request_uuid>",                  self.ui_admin_deny_quota_request),
            R("/admin/users",                                                    self.ui_admin_users),
            R("/admin/exploratory",                                              self.ui_admin_exploratory),
            R("/admin/quota-requests",                                           self.ui_admin_quota_requests),
            R("/admin/sparql",                                                   self.ui_admin_sparql),
            R("/admin/reports",                                                  self.ui_admin_reports),
            R("/admin/reports/restricted_datasets",                              self.ui_admin_reports_restricted_datasets),
            R("/admin/reports/embargoed_datasets",                               self.ui_admin_reports_embargoed_datasets),
            R("/admin/impersonate/<account_uuid>",                               self.ui_admin_impersonate),
            R("/admin/maintenance/clear-cache",                                  self.ui_admin_clear_cache),
            R("/admin/maintenance/clear-sessions",                               self.ui_admin_clear_sessions),
            R("/admin/maintenance/repair-doi-registrations",                     self.ui_admin_repair_doi_registrations),
            R("/admin/maintenance/recalculate-statistics",                       self.ui_admin_recalculate_statistics),
            R("/categories/<category_id>",                                       self.ui_categories),
            R("/category",                                                       self.ui_category),
            R("/institutions/<institution_name>",                                self.ui_institution),
            R("/opendap_to_doi",                                                 self.ui_opendap_to_doi),
            R("/datasets/<dataset_id>",                                          self.ui_dataset),
            R("/datasets/<dataset_id>/<version>",                                self.ui_dataset),
            R("/private_datasets/<private_link_id>",                             self.ui_private_dataset),
            R("/private_collections/<private_link_id>",                          self.ui_private_collection),
            R("/file/<dataset_id>/<file_id>",                                    self.ui_download_file),
            R("/collections/<collection_id>",                                    self.ui_collection),
            R("/collections/<collection_id>/<version>",                          self.ui_collection),
            R("/my/collections/published/<collection_id>",                       self.ui_collection_published),
            R("/authors/<author_uuid>",                                          self.ui_author),
            R("/search",                                                         self.ui_search),
            R("/ndownloader/items/<dataset_id>/versions/<version>",              self.ui_download_all_files),
            R("/data_access_request",                                            self.ui_data_access_request),
            R("/feedback",                                                       self.ui_feedback),
            R("/sitemap.xml",                                                    self.sitemap),


            ## Export formats
            ## ----------------------------------------------------------------
            R("/export/<citation_format>/<item_type>s/<item_id>",                self.ui_export_citation),
            R("/export/<citation_format>/<item_type>s/<item_id>/<version>",      self.ui_export_citation),

            ## SAML 2.0
            ## ----------------------------------------------------------------
            R("/saml/metadata",                                                  self.saml_metadata),
            R("/saml/login",                                                     self.ui_login),

            ## Compatibility
            ## ----------------------------------------------------------------
            R("/articles/<slug>/<dataset_id>",                                   self.ui_compat_dataset),
            R("/articles/<slug>/<dataset_id>/<version>",                         self.ui_compat_dataset),
            R("/articles/dataset/<slug>/<dataset_id>",                           self.ui_compat_dataset),
            R("/articles/dataset/<slug>/<dataset_id>/<version>",                 self.ui_compat_dataset),
            R("/articles/software/<slug>/<dataset_id>",                          self.ui_compat_dataset),
            R("/articles/software/<slug>/<dataset_id>/<version>",                self.ui_compat_dataset),
            # "/collections/<slug>/<collection_id>" is handled by "/collections/<collection_id>/<version>"
            R("/collections/<slug>/<collection_id>/<version>",                   self.ui_compat_collection),

            ## ----------------------------------------------------------------
            ## V2 API
            ## ----------------------------------------------------------------
            R("/v2/account/applications/authorize",                              self.api_authorize),
            R("/v2/token",                                                       self.api_token),
            R("/v2/collections",                                                 self.api_collections),

            ## Private institutions
            ## ----------------------------------------------------------------
            R("/v2/account/institution",                                         self.api_private_institution),
            R("/v2/account/institution/users/<account_uuid>",                    self.api_private_institution_account),
            R("/v2/account/institution/accounts",                                self.api_private_institution_accounts),

            ## Public articles
            ## ----------------------------------------------------------------
            R("/v2/articles",                                                    self.api_datasets),
            R("/v2/articles/search",                                             self.api_datasets_search),
            R("/v2/articles/<dataset_id>",                                       self.api_dataset_details),
            R("/v2/articles/<dataset_id>/versions",                              self.api_dataset_versions),
            R("/v2/articles/<dataset_id>/versions/<version>",                    self.api_dataset_version_details),
            R("/v2/articles/<dataset_id>/versions/<version>/embargo",            self.api_dataset_version_embargo),
            R("/v2/articles/<dataset_id>/versions/<version>/confidentiality",    self.api_dataset_version_confidentiality),
            R("/v2/articles/<dataset_id>/versions/<version>/update_thumb",       self.api_dataset_version_update_thumb),
            R("/v2/articles/<dataset_id>/files",                                 self.api_dataset_files),
            R("/v2/articles/<dataset_id>/files/<file_id>",                       self.api_dataset_file_details),

            ## Private articles
            ## ----------------------------------------------------------------
            R("/v2/account/articles",                                            self.api_private_datasets),
            R("/v2/account/articles/search",                                     self.api_private_datasets_search),
            R("/v2/account/articles/<dataset_id>",                               self.api_private_dataset_details),
            R("/v2/account/articles/<dataset_id>/authors",                       self.api_private_dataset_authors),
            R("/v2/account/articles/<dataset_id>/authors/<author_id>",           self.api_private_dataset_author_delete),
            R("/v2/account/articles/<dataset_id>/funding",                       self.api_private_dataset_funding),
            R("/v2/account/articles/<dataset_id>/funding/<funding_id>",          self.api_private_dataset_funding_delete),
            R("/v2/account/articles/<dataset_id>/categories",                    self.api_private_dataset_categories),
            R("/v2/account/articles/<dataset_id>/categories/<category_id>",      self.api_private_delete_dataset_category),
            R("/v2/account/articles/<dataset_id>/embargo",                       self.api_private_dataset_embargo),
            R("/v2/account/articles/<dataset_id>/files",                         self.api_private_dataset_files),
            R("/v2/account/articles/<dataset_id>/files/<file_id>",               self.api_private_dataset_file_details),
            R("/v2/account/articles/<dataset_id>/private_links",                 self.api_private_dataset_private_links),
            R("/v2/account/articles/<dataset_id>/private_links/<link_id>",       self.api_private_dataset_private_links_details),
            R("/v2/account/articles/<dataset_id>/reserve_doi",                   self.api_private_dataset_reserve_doi),
            R("/v2/account/articles/<dataset_id>/publish",                       self.api_v3_dataset_publish),

            ## Public collections
            ## ----------------------------------------------------------------
            R("/v2/collections",                                                 self.api_collections),
            R("/v2/collections/search",                                          self.api_collections_search),
            R("/v2/collections/<collection_id>",                                 self.api_collection_details),
            R("/v2/collections/<collection_id>/versions",                        self.api_collection_versions),
            R("/v2/collections/<collection_id>/versions/<version>",              self.api_collection_version_details),
            R("/v2/collections/<collection_id>/articles",                        self.api_collection_datasets),

            ## Private collections
            ## ----------------------------------------------------------------
            R("/v2/account/collections",                                         self.api_private_collections),
            R("/v2/account/collections/search",                                  self.api_private_collections_search),
            R("/v2/account/collections/<collection_id>",                         self.api_private_collection_details),
            R("/v2/account/collections/<collection_id>/authors",                 self.api_private_collection_authors),
            R("/v2/account/collections/<collection_id>/authors/<author_id>",     self.api_private_collection_author_delete),
            R("/v2/account/collections/<collection_id>/categories",              self.api_private_collection_categories),
            R("/v2/account/collections/<collection_id>/categories/<category_id>", self.api_private_delete_collection_category),
            R("/v2/account/collections/<collection_id>/articles",                self.api_private_collection_datasets),
            R("/v2/account/collections/<collection_id>/articles/<dataset_id>",   self.api_private_collection_dataset_delete),
            R("/v2/account/collections/<collection_id>/reserve_doi",             self.api_private_collection_reserve_doi),
            R("/v2/account/collections/<collection_id>/funding",                 self.api_private_collection_funding),
            R("/v2/account/collections/<collection_id>/funding/<funding_id>",    self.api_private_collection_funding_delete),

            ## Private authors
            ## ----------------------------------------------------------------
            R("/v2/account/authors/search",                                      self.api_private_authors_search),
            R("/v2/account/authors/<author_id>",                                 self.api_private_author_details),

            ## Other
            ## ----------------------------------------------------------------
            R("/v2/account/funding/search",                                      self.api_private_funding_search),
            R("/v2/licenses",                                                    self.api_licenses),
            R("/v2/categories",                                                  self.api_categories),
            R("/v2/account",                                                     self.api_account),

            ## ----------------------------------------------------------------
            ## V3 API
            ## ----------------------------------------------------------------
            R("/v3/datasets",                                                    self.api_v3_datasets),
            R("/v3/datasets/codemeta",                                           self.api_v3_datasets_codemeta),
            R("/v3/datasets/search",                                             self.api_v3_datasets_search),
            R("/v3/datasets/top/<item_type>",                                    self.api_v3_datasets_top),
            R("/v3/datasets/<dataset_id>/submit-for-review",                     self.api_v3_dataset_submit),
            R("/v3/datasets/<dataset_id>/publish",                               self.api_v3_dataset_publish),
            R("/v3/datasets/<dataset_id>/decline",                               self.api_v3_dataset_decline),
            R("/v3/datasets/<container_uuid>/repair_md5s",                       self.api_v3_repair_md5s),
            R("/v3/datasets/<dataset_id>/doi-badge-v<version>.svg",              self.api_v3_doi_badge),
            R("/v3/datasets/<dataset_id>/doi-badge.svg",                         self.api_v3_doi_badge),
            R("/v3/collections/<collection_id>/publish",                         self.api_v3_collection_publish),
            R("/v3/datasets/timeline/<item_type>",                               self.api_v3_datasets_timeline),
            R("/v3/datasets/<dataset_id>/upload",                                self.api_v3_dataset_upload_file),
            R("/v3/datasets/<dataset_id>/image-files",                           self.api_v3_dataset_image_files),
            R("/v3/datasets/<dataset_id>/update-thumbnail",                      self.api_v3_datasets_update_thumbnail),
            R("/v3/datasets/<dataset_id>.git/files",                             self.api_v3_dataset_git_files),
            R("/v3/datasets/<dataset_id>.git/branches",                          self.api_v3_dataset_git_branches),
            R("/v3/datasets/<dataset_id>.git/set-default-branch",                self.api_v3_datasets_git_set_default_branch),
            R("/v3/file/<file_id>",                                              self.api_v3_file),
            R("/v3/datasets/<container_uuid>/authors",                           self.api_v3_dataset_authors),
            R("/v3/datasets/<container_uuid>/authors/<author_uuid>",             self.api_v3_dataset_authors),
            R("/v3/datasets/<container_uuid>/reorder-authors",                   self.api_v3_datasets_authors_reorder),
            R("/v3/collections/<container_uuid>/reorder-authors",                self.api_v3_collections_authors_reorder),
            R("/v3/datasets/<dataset_id>/references",                            self.api_v3_dataset_references),
            R("/v3/collections/<collection_id>/references",                      self.api_v3_collection_references),
            R("/v3/datasets/<dataset_id>/tags",                                  self.api_v3_dataset_tags),
            R("/v3/collections/<collection_id>/tags",                            self.api_v3_collection_tags),
            R("/v3/groups",                                                      self.api_v3_groups),
            R("/v3/profile",                                                     self.api_v3_profile),
            R("/v3/profile/categories",                                          self.api_v3_profile_categories),
            R("/v3/profile/quota-request",                                       self.api_v3_profile_quota_request),
            R("/v3/profile/picture",                                             self.api_v3_profile_picture),
            R("/v3/profile/picture/<account_uuid>",                              self.api_v3_profile_picture_for_account),
            R("/v3/tags/search",                                                 self.api_v3_tags_search),
            R("/v3/datasets/<dataset_uuid>/collaborators",                       self.api_v3_dataset_collaborators),
            R("/v3/datasets/<dataset_uuid>/collaborators/<collaborator_uuid>",   self.api_v3_update_collaborators),
            R("/v3/accounts/search",                                             self.api_v3_accounts_search),
            R("/v3/authors/<author_uuid>",                                       self.api_v3_author_details),

            ## Data model exploratory
            ## ----------------------------------------------------------------
            R("/v3/explore/types",                                               self.api_v3_explore_types),
            R("/v3/explore/properties",                                          self.api_v3_explore_properties),
            R("/v3/explore/property_value_types",                                self.api_v3_explore_property_types),
            R("/v3/explore/clear-cache",                                         self.api_v3_explore_clear_cache),

            ## Reviewer
            ## ----------------------------------------------------------------
            R("/v3/datasets/<dataset_uuid>/assign-reviewer/<reviewer_uuid>",     self.api_v3_datasets_assign_reviewer),

            ## Administrative
            ## ----------------------------------------------------------------
            R("/v3/admin/files-integrity-statistics",                            self.api_v3_admin_files_integrity_statistics),
            R("/v3/admin/accounts/clear-cache",                                  self.api_v3_admin_accounts_clear_cache),
            R("/v3/admin/reviews/clear-cache",                                   self.api_v3_admin_reviews_clear_cache),

            ## ----------------------------------------------------------------
            ## GIT HTTP API
            ## ----------------------------------------------------------------
            R("/v3/datasets/<git_uuid>.git",                                     self.api_v3_private_dataset_git_instructions),
            R("/v3/datasets/<git_uuid>.git/info/refs",                           self.api_v3_private_dataset_git_refs),
            R("/v3/datasets/<git_uuid>.git/git-upload-pack",                     self.api_v3_private_dataset_git_upload_pack),
            R("/v3/datasets/<git_uuid>.git/git-receive-pack",                    self.api_v3_private_dataset_git_receive_pack),
            R("/v3/datasets/<git_uuid>.git/languages",                           self.api_v3_dataset_git_languages),
            R("/v3/datasets/<git_uuid>.git/contributors",                        self.api_v3_dataset_git_contributors),
            R("/v3/datasets/<git_uuid>.git/zip",                                 self.api_v3_dataset_git_zip),

            ## ----------------------------------------------------------------
            ## SHARED SUBMIT INTERFACE API
            ## ----------------------------------------------------------------
            R("/v3/receive-from-ssi",                                            self.api_v3_receive_from_ssi),
            R("/v3/redirect-from-ssi/<container_uuid>/<token>",                  self.api_v3_redirect_from_ssi),

            ## ----------------------------------------------------------------
            ## INTERNATIONAL IMAGE INTEROPERABILITY FRAMEWORK
            ## ----------------------------------------------------------------
            R("/iiif/v3/<file_uuid>/<region>/<size>/<rotation>/<quality>.<image_format>", self.iiif_v3_image),
            R("/iiif/v3/<file_uuid>",                                            self.iiif_v3_image_context_redirect),
            R("/iiif/v3/<file_uuid>/info.json",                                  self.iiif_v3_image_context),
        ])

        ## Static resources and HTML templates.
        ## --------------------------------------------------------------------

        resources_path = os.path.dirname(__file__)
        self.static_roots = { "/static": os.path.join(resources_path, "resources/static") }
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
        logging.getLogger('werkzeug').setLevel(logging.ERROR)

    ## WSGI AND WERKZEUG SETUP.
    ## ------------------------------------------------------------------------

    def add_static_root (self, uri, path, prepend=False):
        """Procedure to register a filesystem root for static files."""
        if uri is not None and path is not None:
            if prepend:
                self.static_roots = { **{ uri: path }, **self.static_roots }
            else:
                self.static_roots = { **self.static_roots, **{ uri: path } }

            self.wsgi = SharedDataMiddleware(self.__respond, self.static_roots)
            return True

        return False

    def __call__ (self, environ, start_response):
        return self.wsgi (environ, start_response)

    def __is_reviewing (self, request):
        token = self.__impersonator_token (request)
        if token is None:
            return False
        return self.db.may_review (token)

    def __impersonator_token (self, request):
        return self.token_from_cookie (request, self.impersonator_cookie_key)

    def __impersonating_account (self, request):
        admin_token = self.token_from_cookie (request, self.impersonator_cookie_key)
        if admin_token is None:
            return None

        user_token = self.token_from_cookie (request)
        account = self.db.account_by_session_token (user_token)
        return account

    def __generate_thumbnail (self, input_filename, dataset_uuid, max_width=300, max_height=300):
        try:
            original  = Image.open (input_filename)
            extension = original.format.lower()
            output_filename = os.path.join (config.thumbnail_storage, f"{dataset_uuid}.{extension}")

            # When the image is the exact thumbnail size.
            if original.width == max_width and original.height == max_height:
                original.save (output_filename)
                return None

            # Determine relative scaling.
            if original.width > original.height:
                thumb_height = int(original.height * (max_width / original.width))
                thumb_width = max_width
            else:
                thumb_height = max_height
                thumb_width = int(original.width * (max_height / original.height))

            # Preserve animation in GIFs.
            if extension == "gif":
                frames = []
                original_durations = []
                try:
                    original_durations = [frame.info['duration'] for frame in ImageSequence.Iterator(original)]
                except KeyError:
                    original_durations = 50
                for frame in ImageSequence.Iterator(original):
                    resized_frame = frame.resize ((thumb_width, thumb_height),
                                                  Image.Resampling.LANCZOS)
                    frames.append (resized_frame)

                first_frame_size = frames[0].size
                resized_image = Image.new("RGBA", (first_frame_size[0] * len(frames), first_frame_size[1]))

                for index, frame in enumerate(frames):
                    resized_image.paste(frame, (index * first_frame_size[0], 0))
                    frames[index] = resized_image.crop ((index * first_frame_size[0],
                                                         0,
                                                         (index + 1) * first_frame_size[0],
                                                         first_frame_size[1]))
                frames[0].save (output_filename, save_all=True, append_images=frames[1:], loop=0,
                                duration=original_durations)
                return extension

            thumbnail = original.resize ((thumb_width, thumb_height))
            thumbnail.save (output_filename)
            return extension

        except (FileNotFoundError, UnidentifiedImageError) as error:
            self.log.error ("Failed to create thumbnail due to %s", error)

        return None

    def __render_svg_template (self, template_name, **context):
        template = self.jinja.get_template (template_name)
        return self.response (template.render (context), mimetype="image/svg+xml")

    def __render_xml_template(self, template_name, **context):
        template = self.jinja.get_template(template_name)
        return self.response(template.render(context), mimetype="application/xml")

    def __render_css_template (self, template_name, **context):
        template = self.jinja.get_template (template_name)
        return self.response (template.render (context), mimetype="text/css")

    def __render_template (self, request, template_name, **context):
        template      = self.jinja.get_template (template_name)
        token         = self.token_from_cookie (request)
        account       = self.db.account_by_session_token (token)
        parameters    = {
            "base_url":            config.base_url,
            "identity_provider":   config.identity_provider,
            "in_production":       config.in_production,
            "is_logged_in":        account is not None,
            "may_deposit":         self.db.is_depositor (token, account),
            "large_footer":        config.large_footer,
            "maintenance_mode":    config.maintenance_mode,
            "menu":                config.menu,
            "orcid_client_id":     config.orcid_client_id,
            "orcid_endpoint":      config.orcid_endpoint,
            "path":                request.path,
            "sandbox_message":     config.sandbox_message,
            "sandbox_message_css": config.sandbox_message_css,
            "site_description":    config.site_description,
            "site_name":           config.site_name,
            "site_shorttag":       config.site_shorttag,
            "support_email_address": config.support_email_address,
            "small_footer":        config.small_footer,
        }
        if account is None:
            parameters = { **parameters,
                "session_token": None,
                "impersonating_account": None,
                "is_reviewing": None
            }
        else:
            impersonator_token = self.__impersonator_token (request)
            parameters = { **parameters,
                "impersonating_account": self.__impersonating_account (request),
                "is_reviewing":          self.db.may_review (impersonator_token),
                "may_administer":        self.db.may_administer (token, account),
                "may_impersonate":       self.db.may_impersonate (token, account),
                "may_query":             self.db.may_query (token, account),
                "may_review":            self.db.may_review (token, account),
                "may_review_institution": self.db.may_review_institution (token, account),
                "may_review_integrity":  self.db.may_review_integrity (token, account),
                "may_review_quotas":     self.db.may_review_quotas (token, account),
                "session_token":         self.token_from_request (request),
            }

            if not parameters["is_reviewing"]:
                parameters["is_reviewing"] = self.db.may_review_institution (impersonator_token)

        return self.response (template.render({ **context, **parameters }),
                              mimetype='text/html')

    def __render_email_templates (self, template_name, **context):
        """Render a plaintext and an HTML body for sending in an e-mail."""

        html_template = self.jinja.get_template (f"{template_name}.html")
        text_template = self.jinja.get_template (f"{template_name}.txt")

        parameters    = { "base_url": config.base_url }

        html_response = html_template.render({ **context, **parameters })
        text_response = text_template.render({ **context, **parameters })

        return text_response, html_response

    def __render_export_format (self, mimetype, template_name, **context):
        template      = self.metadata_jinja.get_template (template_name)
        return self.response (template.render(**context), mimetype=mimetype)

    def __dispatch_request (self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            self.log_access (request)
            if config.maintenance_mode:
                return self.ui_maintenance (request)
            endpoint, values = adapter.match() #  pylint: disable=unpacking-non-sequence
            return endpoint (request, **values)
        except NotFound:
            if request.path in self.static_pages:
                page = self.static_pages[request.path]
                if "filesystem-path" in page:
                    # Handle static pages.
                    try:
                        return self.__render_template(request, page["filesystem-path"])
                    except TemplateNotFound:
                        self.log.error ("Couldn't find template '%s'.", page["filesystem-path"])
                elif "redirect-to" in page:
                    # Handle redirect
                    return redirect(location=page["redirect-to"], code=page["code"])

            return self.error_404 (request)
        except BadRequest as error:
            self.log.error ("Received bad request: %s", error)
            return self.error_400 (request, error.description, 400)
        except HTTPException as error:
            self.log.error ("Unknown error in dispatch_request: %s", error)
            return error
        # Broad catch-all to improve logging/debugging of such situations.
        except Exception as error:
            self.log.error ("In request: %s", request.environ)
            raise error

    def __respond (self, environ, start_response):
        request  = Request(environ)
        response = self.__dispatch_request(request)
        return response(environ, start_response)

    def __send_templated_email (self, email_addresses, subject, template_name, **context):
        """Procedure to send an email according to a template to the list of EMAIL_ADDRESSES."""

        if not email_addresses or not self.email.is_properly_configured ():
            return False

        failure_count = 0
        for email_address in email_addresses:
            if not self.db.may_receive_email_notifications (email_address):
                self.log.info ("Did not send e-mail to '%s' due to settings.", email_address)
                continue

            text, html = self.__render_email_templates (f"email/{template_name}",
                                                        recipient_email=email_address,
                                                        **context)
            if not self.email.send_email (email_address, subject, text, html):
                failure_count += 1

        if failure_count > 0:
            self.log.info ("Failed to send e-mail to %d out of %d address(es): %s", failure_count, len(email_addresses), subject)
            return False

        self.log.info ("Sent e-mail to %d address(es): %s", len(email_addresses), subject)
        return True

    def __send_email_to_reviewers (self, subject, template_name, **context):
        """Procedure to send an email to all accounts configured with 'may_review' privileges."""
        addresses = self.db.reviewer_email_addresses()
        account_email = context.get("account_email")
        if account_email is not None:
            domain = value_or_none (account_email.rsplit("@", 1), 1)
            addresses += self.db.institutional_reviewer_email_addresses (domain)
            # Remove potential duplicate addresses
            addresses = list(set(addresses))
        return self.__send_templated_email (addresses, subject, template_name, **context)

    def __send_email_to_quota_reviewers (self, subject, template_name, **context):
        """Procedure to send an email to all accounts configured with 'may_review' privileges."""
        addresses = self.db.quota_reviewer_email_addresses()
        return self.__send_templated_email (addresses, subject, template_name, **context)

    def token_from_cookie (self, request, cookie_key=None):
        """Procedure to gather an access token from a HTTP cookie."""
        if cookie_key is None:
            cookie_key = self.cookie_key
        return value_or_none (request.cookies, cookie_key)

    def __log_event (self, request, item_uuid, item_type, event_type):
        """Records a view or download event."""
        try:
            timestamp  = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
            ip_address = request.remote_addr
            if self.log_access == self.log_access_using_x_forwarded_for:
                ip_address = request.headers["X-Forwarded-For"]

            return self.db.insert_log_entry (timestamp, ip_address, item_uuid,
                                             item_type=item_type,
                                             event_type=event_type)
        except KeyError as error:
            self.log.error ("Failed to capture log event due to: %s", repr(error))

        return False

    def __git_repository_url_for_dataset (self, dataset):
        """Returns the Git URL when a repository exists for DATASET or None otherwise."""
        git_repository_url = None
        if value_or_none (dataset, "defined_type_name") == "software":
            try:
                if os.path.exists (os.path.join (config.storage, f"{dataset['git_uuid']}.git")):
                    git_repository_url = f"{config.base_url}/v3/datasets/{dataset['git_uuid']}.git"
            except KeyError:
                pass

        return git_repository_url

    ## ERROR HANDLERS
    ## ------------------------------------------------------------------------

    def error_400_list (self, request, errors):
        """Procedure to respond with HTTP 400 with a list of error messages."""
        response = None
        if self.accepts_html (request, strict=True):
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

    def error_403 (self, request, audit_log_message=None):
        """Procedure to respond with HTTP 403."""
        response = None
        if audit_log_message is not None:
            self.log.audit (audit_log_message)
        if self.accepts_html (request, strict=True):
            response = self.__render_template (request, "403.html")
        else:
            response = self.response (json.dumps ({"message": "Not allowed."}))
        response.status_code = 403
        return response

    def error_404 (self, request):
        """Procedure to respond with HTTP 404."""
        response = None
        if self.accepts_html (request, strict=True):
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

    def error_409 (self):
        """Procedure to respond with HTTP 409."""
        response = self.response (json.dumps({
            "message": "The resource is already available."
        }))
        response.status_code = 409
        return response

    def error_410 (self, request):
        """Procedure to respond with HTTP 410."""
        if self.accepts_html (request, strict=True):
            response = self.__render_template (request, "410.html")
        else:
            response = self.response (json.dumps({
                "message": "This resource is gone."
            }))
        response.status_code = 410
        return response

    def error_413 (self, request):
        """Procedure to respond with HTTP 413."""
        response = None
        message  = "You've reached your storage quota. "
        message += "<a href=\"/my/dashboard\">Request more storage here</a>."
        if self.accepts_json (request):
            response = self.response (json.dumps({ "message": message }))
        else:
            response = self.response (message, mimetype="text/plain")
        response.status_code = 413
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

    def error_500 (self, audit_log_message=None):
        """Procedure to respond with HTTP 500."""
        response = self.response ("")
        response.status_code = 500
        if audit_log_message is None:
            audit_log_message = "An unexpected error has occurred (HTTP 500)."
        self.log.audit (audit_log_message)
        return response

    def error_authorization_failed (self, request):
        """Procedure to handle authorization failures."""
        if self.accepts_html (request, strict=True):
            response = self.__render_template (request, "403.html")
        else:
            response = self.response (json.dumps({
                "message": "Invalid or unknown session token",
                "code":    "InvalidSessionToken"
            }))

        response.status_code = 403
        return response

    def default_error_handling (self, request, methods, content_type):
        """Procedure to handle both method and content type mismatches."""
        if isinstance (methods, str):
            methods = [methods]

        if (request.method not in methods and
            (not ("GET" in methods and request.method == "HEAD"))):
            return self.error_405 (methods)

        if not self.accepts_content_type (request, content_type, strict=False):
            return self.error_406 (content_type)

        return None

    def default_authenticated_error_handling (self, request, methods, content_type,
                                              privilege_test=None):
        """Procedure to handle method and content type mismatches as well authentication."""

        handler = self.default_error_handling (request, methods, content_type)
        if handler is not None:
            return handler

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed (request)

        if privilege_test is not None:
            token = self.token_from_request (request)
            if not privilege_test (token):
                return self.error_403 (request, (f"account:{account_uuid} "
                                                 "didn't pass privilege test "
                                                 f"{privilege_test.__name__}."))

        return account_uuid

    def response (self, content, mimetype='application/json'):
        """Returns a self.response object with some tweaks."""

        output                   = Response(content, mimetype=mimetype)
        output.headers["Server"] = config.site_name
        return output

    ## GENERAL HELPERS
    ## ----------------------------------------------------------------------------

    def __standard_doi (self, container_uuid, version=None, container_doi=None):
        """Standard doi for datasets/collections."""

        if not container_doi:
            container_doi = f'{config.datacite_prefix}/{container_uuid}'
        doi = container_doi
        if version:
            doi += f'.v{version}'
        return doi

    def __dataset_by_id_or_uri (self, identifier, account_uuid=None,
                                is_published=True, is_latest=False,
                                is_under_review=None, version=None,
                                use_cache=True):
        try:
            if version is not None and not parses_to_int (version):
                return None

            parameters = {
                "is_published": is_published,
                "is_latest": is_latest,
                "is_under_review": is_under_review,
                "version": version,
                "account_uuid": account_uuid,
                "use_cache": use_cache,
                "limit": 1
            }
            dataset = None
            if parses_to_int (identifier):
                dataset = self.db.datasets (dataset_id = int(identifier),
                                            **parameters)[0]
            elif validator.is_valid_uuid (identifier):
                dataset = self.db.datasets (container_uuid = identifier,
                                            **parameters)[0]

            return dataset

        except IndexError:
            return None

    def __collection_by_id_or_uri (self, identifier, account_uuid=None,
                                   is_published=True, is_latest=False,
                                   version=None, use_cache=True):
        try:
            if version is not None and not parses_to_int (version):
                return None

            parameters = {
                "is_published": is_published,
                "is_latest": is_latest,
                "version": version,
                "account_uuid": account_uuid,
                "use_cache": use_cache,
                "limit": 1
            }
            collection = None
            if parses_to_int (identifier):
                collection = self.db.collections (collection_id = int(identifier),
                                                  **parameters)[0]
            elif validator.is_valid_uuid (identifier):
                collection = self.db.collections (container_uuid = identifier,
                                                  **parameters)[0]

            return collection

        except IndexError:
            return None

    def __files_by_id_or_uri (self, identifier=None,
                              account_uuid=None,
                              dataset_uri=None,
                              private_view=False):
        try:
            parameters = {
                "dataset_uri": dataset_uri,
                "account_uuid": account_uuid,
                "private_view": private_view
            }
            file = None
            if parses_to_int (identifier):
                file = self.db.dataset_files (file_id = int(identifier), **parameters)
            elif (validator.is_valid_uuid (identifier) and
                  validator.is_valid_uuid (uri_to_uuid (dataset_uri))):
                file = self.db.dataset_files (file_uuid = identifier, **parameters)
            elif validator.is_valid_uuid (identifier):
                parameters["dataset_uri"] = None
                file = self.db.dataset_files (file_uuid = identifier, **parameters)
            elif (validator.is_valid_uuid (uri_to_uuid (dataset_uri))):
                file = self.db.dataset_files (file_uuid = None, **parameters)

            return file

        except IndexError:
            return None

    def __needs_collaborative_permissions (self, account_uuid, request,
                                           item_type, item, permissions):
        """Returns a Response when insufficient permissions, None otherwise."""
        if not value_or (item, "is_shared_with_me", False):
            return None, None

        if "uuid" not in item:
            return None, self.error_403 (request, f"Missing 'uuid' in item for account:{account_uuid}.")

        record = self.db.item_collaborative_permissions (item_type, item["uuid"], account_uuid)
        if not permissions:
            return None, self.error_403 (request, ("Could not find permissions for "
                                                   f"account:{account_uuid} on {item['uuid']}."))

        # Provide syntatic leniency for a single permission
        if isinstance (permissions, str):
            permissions = [ permissions ]

        for permission in permissions:
            if not value_or (record, permission, False):
                return None, self.error_403 (request, (f"account:{account_uuid} attempted action "
                                                       f"requiring '{permission}' on {item['uuid']}."))

        return record, None

    def __file_by_id_or_uri (self, identifier,
                             account_uuid=None,
                             dataset_uri=None,
                             private_view=False):
        try:
            return self.__files_by_id_or_uri (identifier, account_uuid,
                                              dataset_uri, private_view)[0]
        except (TypeError, IndexError):
            return None

    def __paging_offset_and_limit (self, request, error_list=None):
        """Return the OFFSET and LIMIT from paging parameters."""
        return validator.paging_to_offset_and_limit ({
            "page":      self.get_parameter (request, "page"),
            "page_size": self.get_parameter (request, "page_size"),
            "limit":     self.get_parameter (request, "limit"),
            "offset":    self.get_parameter (request, "offset")
        }, error_list=error_list)

    def __default_dataset_api_parameters (self, request):

        record = {
            "categories":   validator.string_value  (self.get_parameter (request, "categories"), None, maximum_length=512),
            "doi":          validator.string_value  (self.get_parameter (request, "doi"), None, maximum_length=255),
            "groups":       validator.integer_value (self.get_parameter (request, "group"), None),
            "handle":       validator.string_value  (self.get_parameter (request, "handle"), None, maximum_length=255),
            "institution":  validator.integer_value (self.get_parameter (request, "institution"), None),
            "is_latest":    validator.boolean_value (self.get_parameter (request, "is_latest"), None),
            "item_type":    validator.integer_value (self.get_parameter (request, "item_type"), None),
            "modified_since": validator.string_value (self.get_parameter (request, "modified_since"), None, maximum_length=32),
            "order":        validator.string_value  (self.get_parameter (request, "order"), None, maximum_length=32),
            "order_direction": validator.order_direction (self.get_parameter (request, "order_direction"), None),
            "published_since": validator.string_value (self.get_parameter (request, "published_since"), None, maximum_length=32),
            "resource_doi": validator.string_value  (self.get_parameter (request, "resource_doi"), None, maximum_length=255),
            "search_for":   self.parse_search_terms (self.get_parameter (request, "search_for")),
            "search_format": validator.boolean_value (self.get_parameter (request, "search_format"), None),
        }
        offset, limit = self.__paging_offset_and_limit (request)
        record["offset"] = offset
        record["limit"]  = limit

        try:
            validator.string_value (record, "search_for", maximum_length=1024, strip_html=False)
        except validator.InvalidValueType:
            validator.array_value  (record, "search_for" )

        record["categories"] = split_string (record["categories"], delimiter=",")
        if "categories" in record and record["categories"] is not None:
            for category_id in record["categories"]:
                validator.integer_value (record, "category_id", category_id)

        # Rewrite the group parameter to match the database's plural form.
        if record["groups"] is not None:
            record["groups"] = [record["groups"]]

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
            collection["base_url"] = config.base_url
            datasets_count = self.db.collections_dataset_count (collection_uri = uri)
            fundings       = self.db.fundings (item_uri = uri, item_type="collection")
            categories     = self.db.categories (item_uri = uri, limit = None)
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
            self.log.access ("%s requested %s %s.",  # pylint: disable=no-member
                             request.headers["X-Forwarded-For"],
                             request.method,
                             request.full_path)
        except KeyError:
            self.log.error ("Missing X-Forwarded-For header.")

    def log_access_directly (self, request):
        """Log interactions using the 'remote_addr' property."""
        self.log.access ("%s requested %s %s.",  # pylint: disable=no-member
                         request.remote_addr,
                         request.method,
                         request.full_path)

    def __add_or_update_git_uuid_for_dataset (self, dataset, account_uuid):
        """Adds or updates the Git UUID for DATASET."""
        if "uuid" not in dataset:
            self.log.error ("Refusing to update Git UUID for dataset without UUID.")
            return False

        succeeded, git_uuid = self.db.update_dataset_git_uuid (dataset["uuid"], account_uuid)
        if not succeeded:
            self.log.error ("Updating the Git UUID of '%s' failed.", dataset["uuid"])
            return False

        self.log.info ("Updated the Git UUID of '%s'.", dataset["uuid"])
        dataset["git_uuid"] = git_uuid
        return True

    def __export_report_in_format (self, request, report_name, report_data, report_format):
        """Exports a report in a given format."""
        if not report_data:
            return self.error_400 (request, "Report data is empty", 400)

        if report_format == "csv":
            if isinstance(report_data, list) and isinstance(report_data[0], dict):
                # dicts in report_data sometimes have different keys.
                # Therefore, all keys need to be collected.
                fieldnames = set()
                for row in report_data:
                    fieldnames.update(row.keys())
                fieldnames = sorted(fieldnames)
            else:
                return self.error_400 (request, "Report data's format is unknown", 400)

            inmemory_file = StringIO()
            writer = csv.DictWriter(inmemory_file, fieldnames=fieldnames)
            writer.writeheader()
            for row in report_data:
                writer.writerow(row)

            report_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{report_name}"
            output = self.response (inmemory_file.getvalue(), mimetype="text/csv")
            output.headers["Content-disposition"] = f"attachment; filename={report_name}.csv"
            return output

        if report_format == "json":
            return self.response (json.dumps(report_data))

        self.log.error ("Unknown report format '%s'.", report_format)
        return self.error_400 (request, "Unknown report format.", 400)

    ## AUTHENTICATION HANDLERS
    ## ------------------------------------------------------------------------

    def obtain_orcid_read_public_token (self):
        """Requests a read-public token from ORCID."""

        url_parameters = {
            "client_id":     config.orcid_client_id,
            "client_secret": config.orcid_client_secret,
            "grant_type":    "client_credentials",
            "scope":         "/read-public"
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        response = requests.post(f"{config.orcid_endpoint}/token",
                                 params  = url_parameters,
                                 headers = headers,
                                 timeout = 10)

        if response.status_code != 200:
            self.log.error ("Failed to obtain read-public token from ORCID (%d).",
                            response.status_code)
            return False

        record = response.json()
        token = value_or_none (record, "access_token")
        if token is not None:
            config.orcid_read_public_token = token
            return True

        self.log.error ("Unexpected response for read-public token from ORCID.")
        self.log.error ("Response was:\n---\n%s\n---", json.dumps(record))
        return False

    def authenticate_using_orcid (self, request, redirect_path="/login"):
        """Returns a record upon success, None upon failure."""

        record = { "code": self.get_parameter (request, "code") }
        try:
            url_parameters = {
                "client_id":     config.orcid_client_id,
                "client_secret": config.orcid_client_secret,
                "grant_type":    "authorization_code",
                "redirect_uri":  f"{config.base_url}{redirect_path}",
                "code":          validator.string_value (record, "code", 0, 10, required=True)
            }
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            response = requests.post(f"{config.orcid_endpoint}/token",
                                     params  = url_parameters,
                                     headers = headers,
                                     timeout = 10)

            if response.status_code == 200:
                return response.json()

            self.log.error ("ORCID response was %d", response.status_code)
        except validator.ValidationException:
            self.log.error ("ORCID parameter validation error")

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
            "http_host":   config.base_url.split("://")[1],
            "script_name": request.path,
            "get_data":    request.args.copy(),
            "post_data":   request.form.copy()
        }

    def __saml_auth (self, request):
        """Returns an instance of OneLogin_Saml2_Auth."""
        http_fields = self.__request_to_saml_request (request)
        return OneLogin_Saml2_Auth (http_fields, custom_base_path=config.saml_config_path)

    def authenticate_using_saml (self, request):
        """Returns a record upon success, None otherwise."""

        http_fields = self.__request_to_saml_request (request)
        saml_auth   = OneLogin_Saml2_Auth (http_fields, custom_base_path=config.saml_config_path)
        try:
            saml_auth.process_response ()
        except OneLogin_Saml2_Error as error:
            if error.code == OneLogin_Saml2_Error.SAML_RESPONSE_NOT_FOUND:
                self.log.error ("Missing SAMLResponse in POST data.")
            else:
                self.log.error ("SAML error %d occured.", error.code)
            return None

        errors = saml_auth.get_errors()
        if errors:
            self.log.error ("Errors in the SAML authentication:")
            self.log.error ("%s", ", ".join(errors))
            return None

        if not saml_auth.is_authenticated():
            self.log.error ("SAML authentication failed.")
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
        try:
            record["email"]      = attributes[config.saml_attribute_email][0]
            record["first_name"] = attributes[config.saml_attribute_first_name][0]
            record["last_name"]  = attributes[config.saml_attribute_last_name][0]
            record["common_name"] = attributes[config.saml_attribute_common_name][0]
            record["domain"] = None
            record["group_uuid"] = None

            if config.saml_attribute_groups is not None:
                groups = attributes[config.saml_attribute_groups]
                for group in groups:
                    prefix = f"{config.saml_attribute_group_prefix}:"
                    if group.startswith(prefix):
                        domain = group[len(prefix):].replace("_", ".")
                        group = self.db.group (association=domain)
                        if group:
                            record["domain"] = domain
                            record["group_uuid"] = group[0]["uuid"]
                            break

        except (KeyError, IndexError):
            self.log.error ("Didn't receive expected fields in SAMLResponse.")
            self.log.error ("Received attributes: %s", attributes)

        if not record["email"]:
            self.log.error ("Didn't receive required fields in SAMLResponse.")
            self.log.error ("Received attributes: %s", attributes)
            return None

        # Fall-back to determining the domain based on the e-mail address.
        if record["domain"] is None:
            record["domain"] = record["email"].partition("@")[2]

        return record

    def saml_metadata (self, request):
        """Communicates the service provider metadata for SAML 2.0."""

        if not (self.accepts_content_type (request, "application/samlmetadata+xml", strict=False) or
                self.accepts_xml (request)):
            return self.error_406 ("text/xml")

        if config.identity_provider != "saml":
            return self.error_404 (request)

        try:
            saml_auth = self.__saml_auth (request)
            settings  = saml_auth.get_settings ()
            metadata  = settings.get_sp_metadata ()
            errors    = settings.validate_metadata (metadata)
            if len(errors) == 0:
                return self.response (metadata, mimetype="text/xml")

            self.log.error ("SAML SP Metadata validation failed.")
            self.log.error ("Errors: %s", ", ".join(errors))
        except xmlsecError as error:
            self.log.error ("SAML configuration error: %s", error)

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
            # No "Accept" header can be treated as equivalent to "Accept: */*".
            return not strict

    def accepts_html (self, request, strict=False):
        """Procedure to check whether the client accepts HTML."""
        return self.accepts_content_type (request, "text/html", strict=strict)

    def accepts_plain_text (self, request):
        """Procedure to check whether the client accepts plain text."""
        return (self.accepts_content_type (request, "text/plain") or
                self.accepts_content_type (request, "*/*"))

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
        try:
            token_string = self.token_from_cookie (request)
            if token_string is None:
                token_string = request.environ["HTTP_AUTHORIZATION"]
            if isinstance(token_string, str) and token_string.startswith("token "):
                token_string = token_string[6:]
            return token_string
        except KeyError:
            return None

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
                    self.log.access ("Account %s impersonating account %s.", #  pylint: disable=no-member
                                    account["uuid"], impersonate)
                    return impersonate

        except (KeyError, IndexError, TypeError):
            pass

        return account["uuid"]

    def account_uuid_from_request (self, request, allow_impersonation=True):
        """Procedure to the account UUID for a HTTP request."""
        uuid  = None
        token = self.token_from_request (request)

        ## Match the token to an account_uuid.  If the token does not
        ## exist, we cannot authenticate.
        try:
            account  = self.db.account_by_session_token (token)
            if account is None:
                return None
            if allow_impersonation:
                uuid = self.impersonated_account_uuid (request, account)
            else:
                uuid = value_or_none (account, "uuid")
        except KeyError:
            self.log.error ("Attempt to authenticate with %s failed.", token)

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
            error_response = self.error_403 (request, (f"account:{account_uuid} "
                                                       "didn't pass privilege test "
                                                       f"'{privilege_test.__name__}'."))

        return account_uuid, error_response

    def __depositor_account_uuid (self, request):
        return self.__account_uuid_for_privilege (request, self.db.is_depositor)

    def __reviewer_account_uuid (self, request):
        return self.__account_uuid_for_privilege (request, self.db.may_review)

    def default_list_response (self, records, format_function, **parameters):
        """Procedure to respond a list of items."""
        output     = []
        try:
            for record in records:
                output.append(format_function ({ **parameters, **record}))
        except TypeError:
            self.log.error ("%s: A TypeError occurred.", format_function)

        return self.response (json.dumps(output))

    def respond_201 (self, body):
        """Procedure to respond with HTTP 201."""
        output = self.response (json.dumps(body))
        output.status_code = 201
        return output

    def respond_204 (self):
        """Procedure to respond with HTTP 204."""
        output = Response("", 204, {})
        output.headers["Server"] = config.site_name
        return output

    def respond_205 (self):
        """Procedure to respond with HTTP 205."""
        output = Response("", 205, {})
        output.headers["Server"] = config.site_name
        return output

    ## API CALLS
    ## ------------------------------------------------------------------------

    def ui_redirect_to_home (self, request):
        """Implements /."""
        if self.accepts_html (request, strict=True):
            return redirect ("/", code=301)

        return self.response (json.dumps({ "status": "OK" }))

    def robots_txt (self, request):  # pylint: disable=unused-argument
        """Implements /robots.txt."""

        output = "User-agent: *\n"
        if config.allow_crawlers:
            output += "Allow: /\n"
        else:
            output += "Disallow: /\n"

        output += f"Sitemap: {config.base_url}/sitemap.xml\n"
        return self.response (output, mimetype="text/plain")

    def colors_css (self, request):
        """Implements /theme/colors.css."""

        if not self.accepts_content_type (request, "text/css", strict=False):
            return self.error_406 ("text/css")

        return self.__render_css_template (
            "colors.css",
            primary_color            = config.colors['primary-color'],
            primary_color_hover      = config.colors['primary-color-hover'],
            primary_color_active     = config.colors['primary-color-active'],
            primary_foreground_color = config.colors['primary-foreground-color'],
            footer_background_color  = config.colors['footer-background-color'],
            privilege_button_color   = config.colors['privilege-button-color'])

    def loader_svg (self, request):
        """Implements /theme/loader.svg."""

        if not self.accepts_content_type (request, "image/svg+xml", strict=False):
            return self.error_406 ("image/svg+xml")

        return self.__render_svg_template ("loader.svg",
            primary_color = config.colors["primary-color"])

    def sitemap (self, request):
        """Implements /sitemap.xml."""
        if not self.accepts_content_type(request, "application/xml", strict=False):
            return self.error_406("application/xml")

        datasets = self.db.datasets(is_published=True, is_latest=True,
                                    limit=50000)
        return self.__render_xml_template("sitemap_template.xml",
                                          base_url = config.base_url,
                                          datasets = datasets)

    def ui_maintenance (self, request):
        """Implements a maintenance page."""
        if not config.maintenance_mode:
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

        if config.identity_provider == "saml":
            return redirect ("/login", code=302)

        if config.identity_provider == "orcid":
            return redirect ((f"{config.orcid_endpoint}/authorize?client_id="
                              f"{config.orcid_client_id}&response_type=code"
                              "&scope=/authenticate&redirect_uri="
                              f"{config.base_url}/login"), 302)

        return self.error_403 (request)

    def __send_sram_collaboration_invite (self, saml_record):

        if (config.sram_organization_api_token is None or
            config.sram_collaboration_id is None or
            "email" not in saml_record):
            return None

        invitation_expiry = datetime.now() + timedelta(days=2)
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {config.sram_organization_api_token}",
            "Content-Type": "application/json"
        }
        json_data = {
            "collaboration_identifier": config.sram_collaboration_id,
            "intended_role": "member",
            # SRAM wants the epoch time in milliseconds.
            "invitation_expiry_date": int(invitation_expiry.timestamp()) * 1000,
            "invites": [saml_record["email"]]
        }
        response = requests.put ("https://sram.surf.nl/api/invitations/v1/collaboration_invites",
                                 headers = headers,
                                 timeout = 60,
                                 json    = json_data)
        if response.status_code == 201:
            self.log.info ("Sent invite to '%s' for SRAM collaboration membership.",
                           saml_record["email"])
        elif response.status_code == 401:
            self.log.warning ("Missing Authorization for SRAM API.")
        elif response.status_code == 403:
            self.log.warning ("SRAM API authentication failed.")
        elif response.status_code == 404:
            self.log.warning ("SRAM API endpoint not found.")
        else:
            self.log.info ("SRAM unexpectedly responded with: %s", response.status_code)

        return None

    def __already_in_sram_collaboration (self, saml_record):

        if (config.sram_organization_api_token is None or
            config.sram_collaboration_id is None or
            "email" not in saml_record):
            return None

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {config.sram_organization_api_token}",
            "Content-Type": "application/json"
        }
        response = requests.get (f"https://sram.surf.nl/api/collaborations/v1/{config.sram_collaboration_id}",
                                 headers = headers,
                                 timeout = 60)
        if response.status_code != 200:
            self.log.error ("Retrieving SRAM collaboration members failed with status code %s",
                            response.status_code)
            return False

        try:
            record = response.json()
            memberships = record["collaboration_memberships"]
            for member in memberships:
                expiry_date = value_or_none (member, "expiry_date")
                if expiry_date is not None and expiry_date < datetime.now().timestamp():
                    continue
                if saml_record["email"].lower() == member["user"]["email"].lower():
                    self.log.info ("Account '%s' is already part of an SRAM collaboration.",
                                   saml_record["email"])
                    return True
        except (TypeError, KeyError) as error:
            self.log.error ("Checking SRAM response failed with %s.", error)
            return False

        return False

    def ui_login (self, request):
        """Implements /login."""

        account_uuid = None
        account      = None

        ## Automatic log in for development purposes only.
        ## --------------------------------------------------------------------
        if config.automatic_login_email is not None and not config.in_production:
            account = self.db.account_by_email (config.automatic_login_email)
            if account is None:
                return self.error_403 (request)
            account_uuid = account["uuid"]
            self.log.access ("Account %s logged in via auto-login.", account_uuid) #  pylint: disable=no-member

        ## ORCID authentication
        ## --------------------------------------------------------------------
        elif config.identity_provider == "orcid":
            orcid_record = self.authenticate_using_orcid (request)
            if orcid_record is None:
                return self.error_403 (request, "Failed login attempt through ORCID.")

            if not self.accepts_html (request):
                return self.error_406 ("text/html")

            account_uuid = self.db.account_uuid_by_orcid (orcid_record['orcid'])
            if account_uuid is None:
                try:
                    account_uuid = self.db.insert_account (
                        # We don't receive the user's e-mail address,
                        # so we construct an artificial one that doesn't
                        # resolve so no accidental e-mails will be sent.
                        email       = f"{orcid_record['orcid']}@orcid",
                        common_name = orcid_record["name"],
                        orcid_id    = orcid_record['orcid']
                    )
                    if not account_uuid:
                        return self.error_403 (request, ("Failed to create account "
                                                         f"for {orcid_record['orcid']}."))

                    self.log.access ("Account %s created via ORCID.", account_uuid) #  pylint: disable=no-member
                except KeyError:
                    return self.error_403 (request, "Received an unexpected record from ORCID.")
            else:
                self.log.access ("Account %s logged in via ORCID.", account_uuid) #  pylint: disable=no-member

        ## SAML 2.0 authentication
        ## --------------------------------------------------------------------
        elif config.identity_provider == "saml":

            ## Initiate the login procedure.
            if request.method == "GET":
                saml_auth   = self.__saml_auth (request)
                redirect_url = saml_auth.login()
                response    = redirect (redirect_url)

                return response

            ## Retrieve signed data from the IdP via the user.
            if request.method == "POST":
                if not self.accepts_html (request):
                    return self.error_406 ("text/html")

                saml_record = self.authenticate_using_saml (request)
                if saml_record is None:
                    return self.error_403 (request, "Failed to receive SAML record.")

                try:
                    if "email" not in saml_record:
                        return self.error_400 (request, "Invalid request", "MissingEmailProperty")

                    account = self.db.account_by_email (saml_record["email"].lower())
                    if account:
                        account_uuid = account["uuid"]

                        # Reset previous group association.
                        if value_or_none (saml_record, "domain") is None:
                            saml_record["domain"] = ""

                        if not self.db.update_account (account_uuid, domain=saml_record["domain"]):
                            self.log.error ("Unable to update domain for account:%s", account_uuid)
                        else:
                            self.log.info ("Updated domain to '%s' for account:%s.",
                                           saml_record["domain"], account_uuid)

                            # When a dataset was created before the owner
                            # was placed in a group, assign those datasets
                            # to the group automatically.
                            datasets = self.db.datasets (account_uuid = account_uuid,
                                                         is_published = False,
                                                         limit        = 10000,
                                                         use_cache    = False)
                            for dataset in datasets:
                                if "group_name" not in dataset:
                                    self.db.associate_dataset_with_group (dataset["uri"],
                                                                          saml_record["domain"],
                                                                          account_uuid)

                            # The supervisor privileges are defined in the XML configuration.
                            if (value_or_none (saml_record, "group_uuid") is not None and
                                self.db.insert_group_member (saml_record["group_uuid"],
                                                             account_uuid, False)):
                                self.log.info ("Added account:%s to group group:%s.",
                                               account_uuid, saml_record["group_uuid"])
                            else:
                                self.log.info ("Failed to add account:%s to group group:%s.",
                                               account_uuid, value_or_none (saml_record, "group_uuid"))

                        self.log.access ("Account %s logged in via SAML.", account_uuid) #  pylint: disable=no-member
                    else:
                        account_uuid = self.db.insert_account (
                            email       = saml_record["email"],
                            first_name  = value_or_none (saml_record, "first_name"),
                            last_name   = value_or_none (saml_record, "last_name"),
                            common_name = value_or_none (saml_record, "common_name"),
                            domain      = value_or_none (saml_record, "domain")
                        )
                        if account_uuid is None:
                            return self.error_500 (f"Creating account for {saml_record['email']} failed.")
                        self.log.access ("Account %s created via SAML.", account_uuid) #  pylint: disable=no-member

                    if (config.sram_collaboration_id is not None and
                        config.sram_organization_api_token is not None):
                        try:
                            if not self.__already_in_sram_collaboration (saml_record):
                                self.__send_sram_collaboration_invite (saml_record)
                        except (TypeError, KeyError) as error:
                            self.log.warning ("An error (%s) occurred when sending invite to %s.",
                                              error, value_or_none (saml_record, "email"))
                        except requests.exceptions.ConnectionError:
                            self.log.error ("Failed to send invite through SRAM due to a connection error.")

                    # For a while we didn't create author records for accounts.
                    # This check creates the missing author records upon login
                    # for such accounts.
                    authors = self.db.authors (account_uuid=account_uuid, limit = 1)
                    if not value_or (authors, 0, True):
                        author_uuid = self.db.insert_author (
                            account_uuid = account_uuid,
                            first_name   = value_or_none (saml_record, "first_name"),
                            last_name    = value_or_none (saml_record, "last_name"),
                            full_name    = value_or_none (saml_record, "common_name"),
                            email        = saml_record["email"],
                            is_active    = True,
                            is_public    = True)
                        self.log.info ("Created author record %s for account %s.",
                                       author_uuid, account_uuid)

                except TypeError:
                    pass
        else:
            return self.error_500 (f"Unknown identity provider '{config.identity_provider}'.")

        if account_uuid is not None:
            token, mfa_token, session_uuid = self.db.insert_session (account_uuid, name="Website login")
            if session_uuid is None:
                return self.error_500 (f"Failed to create a session for account {account_uuid}.")

            self.log.access ("Created session %s for account %s.", session_uuid, account_uuid) #  pylint: disable=no-member

            if mfa_token is None:
                response = redirect ("/my/dashboard", code=302)
                response.set_cookie (key=self.cookie_key, value=token, secure=config.in_production)
                return response

            ## Send e-mail
            if account is None:
                account = self.db.account_by_uuid (account_uuid)
            self.__send_templated_email (
                [account["email"]],
                "Two-factor authentication log-in token",
                "2fa_token", token = mfa_token)

            response = redirect (f"/my/sessions/{session_uuid}/activate", code=302)
            response.set_cookie (key=self.cookie_key, value=token, secure=config.in_production)
            return response

        return self.error_500 ("Failed to complete the log in procedure for an unknown reason.")

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
                                 secure = config.in_production)
            response.delete_cookie (key = self.impersonator_cookie_key)
            response.delete_cookie (key = "redirect_to")
            return response

        response = redirect ("/", code=302)
        self.db.delete_session (self.token_from_cookie (request))
        response.delete_cookie (key=self.cookie_key)
        return response

    def ui_review_impersonate_to_dataset (self, request, dataset_id):
        """Implements /review/goto-dataset/<id>."""

        account_uuid = self.default_authenticated_error_handling (request, "GET", "text/html",
                                                                  self.db.may_impersonate)
        if isinstance (account_uuid, Response):
            return account_uuid

        if not validator.is_valid_uuid (dataset_id):
            return self.error_404 (request)

        dataset = None
        try:
            dataset = self.db.datasets (dataset_uuid    = dataset_id,
                                        is_published    = False,
                                        is_under_review = True)[0]
        except (IndexError, TypeError):
            pass

        if dataset is None:
            return self.error_403 (request, (f"account:{account_uuid} attempted "
                                             f"impersonation on dataset:{dataset_id}."))

        try:
            review = self.db.reviews (dataset_uri = dataset["uri"])[0]
            assigned_uuid = uri_to_uuid (review["assigned_to"])
            if account_uuid == assigned_uuid:
                self.db.dataset_update_seen_by_reviewer (dataset["uuid"])
        except (KeyError, TypeError, IndexError):
            pass

        # Add a secondary cookie to go back to at one point.
        response = redirect (f"/my/datasets/{dataset['container_uuid']}/edit", code=302)
        response.set_cookie (key    = self.impersonator_cookie_key,
                             value  = self.token_from_request (request),
                             secure = config.in_production)
        response.set_cookie (key    = "redirect_to",
                             value  = "/review/overview",
                             secure = config.in_production)

        # Create a new session for the user to be impersonated as.
        new_token, _, _ = self.db.insert_session (dataset["account_uuid"],
                                                  name="Reviewer",
                                                  override_mfa=True)
        response.set_cookie (key    = self.cookie_key,
                             value  = new_token,
                             secure = config.in_production)
        return response

    def ui_admin_impersonate (self, request, account_uuid):
        """Implements /admin/impersonate/<id>."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        if not validator.is_valid_uuid (account_uuid):
            return self.error_404 (request)

        token = self.token_from_cookie (request)
        if not self.db.may_impersonate (token):
            return self.error_403 (request)

        # Add a secondary cookie to go back to at one point.
        response = redirect ("/my/dashboard", code=302)
        response.set_cookie (key    = self.impersonator_cookie_key,
                             value  = token,
                             secure = config.in_production)
        response.set_cookie (key    = "redirect_to",
                             value  = "/admin/users",
                             secure = config.in_production)

        # Create a new session for the user to be impersonated as.
        new_token, _, _ = self.db.insert_session (account_uuid,
                                                  name="Impersonation",
                                                  override_mfa=True)
        response.set_cookie (key    = self.cookie_key,
                             value  = new_token,
                             secure = config.in_production)
        return response

    def ui_dashboard (self, request):
        """Implements /my/dashboard."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed (request)

        account      = self.db.account_by_uuid (account_uuid)
        storage_used = self.db.account_storage_used (account_uuid)
        pending_quota_requests = self.db.quota_requests (status       = "unresolved",
                                                         account_uuid = account_uuid)

        account_quota   = 0
        percentage_used = 0
        requested_quota = None
        try:
            account_quota   = account["quota"]
            percentage_used = round(storage_used / account_quota * 100, 2)

            if pending_quota_requests:
                requested_bytes = int(pending_quota_requests[0]["requested_size"])
                requested_quota = pretty_print_size (requested_bytes)
        except (TypeError, KeyError):
            pass

        sessions     = self.db.sessions (account_uuid)
        return self.__render_template (
            request, "depositor/dashboard.html",
            storage_used = pretty_print_size (storage_used),
            quota        = pretty_print_size (account_quota),
            requested_quota = requested_quota,
            percentage_used = percentage_used,
            sessions     = sessions)

    def __datasets_with_storage_usage (self, datasets):
        for dataset in datasets:
            used = 0
            if not value_or (dataset, "is_metadata_record", False):
                used = self.db.dataset_storage_used (dataset["uuid"])
            dataset["storage_used"] = pretty_print_size (used)
        return datasets

    def ui_my_data (self, request):
        """Implements /my/datasets."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed (request)

        draft_datasets     = self.db.datasets (account_uuid = account_uuid,
                                               limit           = 10000,
                                               is_published    = False,
                                               is_under_review = False)
        review_datasets    = self.db.datasets (account_uuid    = account_uuid,
                                               limit           = 10000,
                                               is_published    = False,
                                               is_under_review = True)
        published_datasets = self.db.datasets (account_uuid    = account_uuid,
                                               limit           = 10000,
                                               is_latest       = True,
                                               is_under_review = False)

        draft_datasets     = self.__datasets_with_storage_usage (draft_datasets)
        review_datasets    = self.__datasets_with_storage_usage (review_datasets)
        published_datasets = self.__datasets_with_storage_usage (published_datasets)

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
            self.log.error ("Attempt to create dataset for account:%s was denied.", account_uuid)
            return error_response

        account = self.db.account_by_uuid (account_uuid)
        container_uuid, dataset_uuid = self.db.insert_dataset(title = "Untitled item",
                                                              account_uuid = account_uuid,
                                                              group_id = value_or_none (account, "group_id"))
        if container_uuid is not None and dataset_uuid is not None:
            # Add oneself as author but don't bail if that doesn't work.
            try:
                author_uri = URIRef(uuid_to_uri(account["author_uuid"], "author"))
                self.db.update_item_list (dataset_uuid, account_uuid,
                                          [author_uri], "authors")
            except (TypeError, KeyError):
                self.log.warning ("No author record for account %s.", account_uuid)

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
        container_uuid = value_or_none (dataset, "container_uuid")

        if dataset is None or container_uuid is None:
            return self.error_403 (request, (f"account:{account_uuid} attempted to create "
                                             f"new version of dataset:{dataset_id}."))

        existing_draft = self.__dataset_by_id_or_uri (container_uuid,
                                                      is_published = False,
                                                      account_uuid = account_uuid,
                                                      use_cache    = False)
        if existing_draft is not None:
            self.log.info ("Refusing to create two drafts for one dataset.")
            return redirect (f"/my/datasets/{container_uuid}/edit", code=302)

        draft_uuid = self.db.create_draft_from_published_dataset (container_uuid,
                                                                  account_uuid=account_uuid)
        if draft_uuid is None:
            self.log.info ("There is no draft dataset.")
            return self.error_500()

        return redirect (f"/my/datasets/{container_uuid}/edit", code=302)

    def ui_edit_dataset (self, request, dataset_id):
        """Implements /my/datasets/<id>/edit."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed (request)

        try:
            dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                   is_published = False,
                                                   account_uuid = account_uuid,
                                                   use_cache    = False)

            if dataset is None:
                return self.error_403 (request, (f"account:{account_uuid} attempted "
                                                 f"to access dataset:{dataset_id}."))

            permissions, error_response = self.__needs_collaborative_permissions (
                account_uuid, request, "dataset", dataset, "metadata_read")
            if error_response is not None:
                return error_response

            # Pre-Djehuty datasets may not have a Git UUID. We therefore
            # assign one when needed.
            if "git_uuid" not in dataset:
                if not self.__add_or_update_git_uuid_for_dataset (dataset, account_uuid):
                    return self.error_500 ()

            categories = self.db.categories_tree ()
            account    = self.db.account_by_uuid (dataset["account_uuid"])
            groups     = self.__groups_for_account (dataset["account_uuid"])

            try:
                # Historically, some datasets have multiple values for
                # 'derived_from'.  Going forward, we only allow a single
                # value for 'derived_from'.  Therefore, we pick the first
                # (and only) value from the 'derived_from' list.
                derived_from = self.db.derived_from (dataset["uri"], limit=1)[0]
                dataset["derived_from"] = derived_from
            except IndexError:
                pass  # No value for derived_from.

            return self.__render_template (
                request,
                "depositor/edit-dataset.html",
                container_uuid = dataset["container_uuid"],
                disable_collaboration = config.disable_collaboration,
                article    = dataset,
                permissions = permissions,
                account    = account,
                categories = categories,
                groups     = groups,
                api_token  = self.token_from_request (request))

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
                return self.error_403 (request, (f"account:{account_uuid} attempted "
                                                 f"to delete dataset:{dataset_id}."))

            container_uuid = dataset["container_uuid"]
            if self.db.delete_dataset_draft (container_uuid, dataset["uuid"], account_uuid, dataset["account_uuid"]):
                return redirect ("/my/datasets", code=303)

            return self.error_404 (request)
        except (IndexError, KeyError):
            pass

        return self.error_500 ()

    def ui_dataset_private_links (self, request, dataset_uuid):
        """Implements /my/datasets/<uuid>/private_links."""

        account_uuid = self.default_authenticated_error_handling (request, "GET", "text/html")
        if isinstance (account_uuid, Response):
            return account_uuid

        if not validator.is_valid_uuid (dataset_uuid):
            return self.error_404 (request)

        try:
            dataset = self.db.datasets (dataset_uuid = dataset_uuid,
                                        account_uuid = account_uuid,
                                        is_published = None,
                                        is_latest    = None,
                                        limit        = 1)[0]
        except IndexError:
            return self.error_403 (request, (f"account:{account_uuid} attempted "
                                             "to get private links of "
                                             f"dataset:{dataset_uuid}."))

        if not dataset:
            return self.error_404 (request)

        links = self.db.private_links (item_uri     = dataset["uri"],
                                       account_uuid = account_uuid)

        for link in links:
            link["is_expired"] = False
            if "expires_date" in link:
                if datetime.fromisoformat(link["expires_date"]) < datetime.now():
                    link["is_expired"] = True

        show_back = self.get_parameter (request, "go_back")
        show_back = (show_back is None or show_back != "no")

        return self.__render_template (request,
                                       "depositor/dataset-private-links.html",
                                       dataset       = dataset,
                                       show_back     = show_back,
                                       private_links = links)

    def ui_collection_private_links (self, request, collection_uuid):
        """Implements /my/collections/<uuid>/private_links."""

        account_uuid = self.default_authenticated_error_handling (request, "GET", "text/html")
        if isinstance (account_uuid, Response):
            return account_uuid

        if not validator.is_valid_uuid (collection_uuid):
            return self.error_404 (request)

        try:
            collection = self.db.collections (collection_uuid = collection_uuid,
                                              account_uuid = account_uuid,
                                              is_published = None,
                                              is_latest    = None,
                                              use_cache    = False,
                                              limit        = 1)[0]
        except IndexError:
            return self.error_403 (request, (f"account:{account_uuid} attempted "
                                             "to get private links of "
                                             f"collection:{collection_uuid}."))

        if not collection:
            return self.error_404 (request)

        links = self.db.private_links (item_uri     = collection["uri"],
                                       account_uuid = account_uuid)

        show_back = self.get_parameter (request, "go_back")
        show_back = (show_back is None or show_back != "no")

        return self.__render_template (request,
                                       "depositor/collection-private-links.html",
                                       show_back     = show_back,
                                       collection    = collection,
                                       private_links = links)

    def ui_my_collections (self, request):
        """Implements /my/collections."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed (request)

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

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed (request)

        try:
            collection = self.__collection_by_id_or_uri(
                collection_id,
                account_uuid = account_uuid,
                is_published = False)

            if collection is None:
                return self.error_403 (request, (f"account:{account_uuid} attempted "
                                                 f"to edit collection:{collection_id}."))

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

        container_uuid, collection_uuid = self.db.insert_collection(
            title = "Untitled collection",
            account_uuid = account_uuid)

        if container_uuid is not None and collection_uuid is not None:
            # Add oneself as author but don't bail if that doesn't work.
            try:
                account    = self.db.account_by_uuid (account_uuid)
                author_uri = URIRef(uuid_to_uri(account["author_uuid"], "author"))
                self.db.update_item_list (collection_uuid, account_uuid,
                                          [author_uri], "authors")
            except (TypeError, KeyError):
                self.log.warning ("No author record for account %s.", account_uuid)

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
        container_uuid = value_or_none (collection, "container_uuid")

        if collection is None or container_uuid is None:
            return self.error_403 (request, (f"account:{account_uuid} attempted "
                                             "to create new version of "
                                             f"collection:{collection_id}."))

        existing_draft = self.__collection_by_id_or_uri (collection_id,
                                                         is_published = False,
                                                         account_uuid = account_uuid,
                                                         use_cache    = False)
        if existing_draft is not None:
            self.log.info ("Refusing to create two drafts for one collection.")
            return redirect (f"/my/collections/{container_uuid}/edit", code=302)

        draft_uuid = self.db.create_draft_from_published_collection (container_uuid)
        if draft_uuid is None:
            self.log.info ("There is no draft collection.")
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
                return self.error_403 (request, (f"account:{account_uuid} attempted "
                                                 f"to delete collection:{collection_id}."))

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

        if not validator.is_valid_uuid (session_uuid):
            return self.error_404 (request)

        if request.method in ("GET", "HEAD"):
            if self.accepts_html (request):
                try:
                    session = self.db.sessions (account_uuid, session_uuid=session_uuid)[0]
                    if not session["editable"]:
                        return self.error_403 (request, (f"account:{account_uuid} attempted to "
                                                         f"edit non-editable session:{session_uuid}."))

                    return self.__render_template (
                        request,
                        "depositor/edit-session.html",
                        session = session)
                except IndexError:
                    return self.error_403 (request, (f"account:{account_uuid} attempted to edit "
                                                     f"non-existing session:{session_uuid}."))

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
                                                     editable = True,
                                                     override_mfa = True)
        if session_uuid is not None:
            return redirect (f"/my/sessions/{session_uuid}/edit", code=302)

        return self.error_500()

    def __remove_session_due_to_2fa_mismatch (self, session_uuid):
        """Procedure to log and delete session upon 2FA mismatch."""
        if self.db.delete_inactive_session_by_uuid (session_uuid):
            self.log.access ("Removed session %s due to 2FA mismatch.", #  pylint: disable=no-member
                            session_uuid)
        else:
            self.log.error ("Failed to remove session %s to protect 2FA.", session_uuid)

    def ui_activate_session (self, request, session_uuid):
        """Implements /my/sessions/<id>/activate"""

        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        if not validator.is_valid_uuid (session_uuid):
            return self.error_404 (request)

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
                return self.error_403 (request, (f"session:{session_uuid} invalidated "
                                                 "due to wrong MFA."))

            account   = self.db.account_by_session_token (token, mfa_token=mfa_token)
            if account is None or "uuid" not in account:
                self.__remove_session_due_to_2fa_mismatch (session_uuid)
                return self.error_authorization_failed (request)

            session = self.db.sessions (account["uuid"],
                                        session_uuid = session_uuid,
                                        mfa_token    = mfa_token)

            if session is None:
                self.__remove_session_due_to_2fa_mismatch (session_uuid)
                return self.error_403 (request, (f"session:{session_uuid} invalidated "
                                                 "due to wrong MFA."))

            if self.db.update_session (account["uuid"], session_uuid, active=True):
                return redirect ("/my/dashboard", code=302)

        return self.error_405 (["GET", "POST"])

    def ui_delete_session (self, request, session_uuid):
        """Implements /my/sessions/<id>/delete."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        if not validator.is_valid_uuid (session_uuid):
            return self.error_404 (request)

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        response   = redirect (request.referrer, code=302)
        self.db.delete_session_by_uuid (account_uuid, session_uuid)
        return response

    def api_v3_dataset_collaborators (self, request, dataset_uuid):
        """Implements /v3/datasets/dataset_uuid/collaborator"""

        if not self.accepts_json (request):
            return self.error_406 ("application/json")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed (request)

        if not validator.is_valid_uuid (dataset_uuid):
            return self.error_404 (request)

        try:
            dataset = self.db.datasets (container_uuid=dataset_uuid,
                                        account_uuid=account_uuid,
                                        is_published=None,
                                        is_latest=None,
                                        limit=1)[0]
        except IndexError:
            return self.error_403 (request)

        if dataset is None:
            return self.error_403 (request)

        if request.method == "GET":

            _, error_response = self.__needs_collaborative_permissions (
                account_uuid, request, "dataset", dataset, "metadata_read")
            if error_response is not None:
                return error_response

            collaborators = self.db.collaborators (dataset["uuid"])
            return self.default_list_response (collaborators, formatter.format_collaborator_record)

        if request.method == "POST":
            if value_or (dataset, "is_shared_with_me", False):
                return self.error_403 (request, (f"account:{account_uuid} attempted "
                                                 f"to modify dataset:{dataset_uuid}."))

            try:
                parameters = request.get_json()
                metadata = parameters["metadata"]
                data = parameters["data"]
                collaborator_account_uuid = validator.string_value (parameters, "account")

                if not validator.is_valid_uuid (collaborator_account_uuid):
                    raise validator.InvalidValueType(
                        field_name = "account",
                        message = "Expected a valid UUID for 'account'",
                        code = "WrongValueType"
                    )

            except validator.ValidationException as error:
                return self.error_400(request, error.message, error.code)

            account = self.db.account_by_uuid (collaborator_account_uuid)
            if account is None:
                self.log.error ("Requesting collaborator account uuid failed. ")

            collaborators = self.db.insert_collaborator (dataset["uuid"],
                                                         collaborator_account_uuid,
                                                         account_uuid,
                                                         metadata["read"],
                                                         metadata["edit"],
                                                         False,
                                                         data["read"],
                                                         data["edit"],
                                                         data["remove"],
                                                         )

            if collaborators is None:
                return self.error_500 ("Inserting collaborator failed. ")

            return self.respond_205()

        return self.error_500 ()

    def api_v3_update_collaborators (self, request, dataset_uuid, collaborator_uuid):
        """Implements /v3/datasets/<dataset_uuid>/collaborators/<collaborator_uuid>"""
        account_uuid = self.default_authenticated_error_handling(request,
                                                                 ["PUT", "DELETE"],
                                                                 "application/json")
        if isinstance(account_uuid, Response):
            return account_uuid

        if (not validator.is_valid_uuid (dataset_uuid) or
                not validator.is_valid_uuid (collaborator_uuid)):
            return self.error_404 (request)
        try:
            dataset = self.db.datasets (container_uuid=dataset_uuid,
                                        account_uuid=account_uuid,
                                        is_published=False,
                                        is_latest=None,
                                        limit=1)[0]

            _, error_response = self.__needs_collaborative_permissions(
                account_uuid, request, "dataset", dataset, "metadata_edit")
            if error_response is not None:
                return error_response

            collaborators = self.db.collaborators (dataset["uuid"])
            for collaborator in collaborators:
                if collaborator["account_uuid"] == account_uuid and not collaborator["is_supervisor"]:
                    return self.error_403 (request, (f"account:{account_uuid} attempted "
                                                     f"to {request.method} collaborators "
                                                     f"for dataset:{dataset_uuid}."))

        except IndexError:
            return self.error_403 (request, (f"account:{account_uuid} attempted to modify "
                                             f"collaborators for dataset:{dataset_uuid}."))

        if request.method == "PUT":
            parameters = request.get_json()
            metadata = parameters["metadata"]
            data = parameters["data"]
            if not self.db.update_collaborator (dataset["uuid"],
                                                collaborator_uuid,
                                                metadata["read"],
                                                metadata["edit"],
                                                False,
                                                data["read"],
                                                data["edit"],
                                                data["remove"]):
                return self.error_500 (("Could not update permissions for "
                                        f"collaborator:{collaborator_uuid} in "
                                        f"dataset:{dataset['uuid']}"))

            return self.respond_204()

        if request.method == "DELETE":
            if self.db.delete_collaborator(dataset["uuid"], collaborator_uuid) is None:
                return self.error_500()
            return self.respond_204()

        return self.error_403(request)

    def api_v3_accounts_search (self, request):
        """Search and autocomplete to add collaborator"""
        if not self.accepts_json(request):
            return self.error_406("application/json")

        account_uuid = self.account_uuid_from_request(request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        if request.method != "POST":
            return self.error_405 ("POST")

        try:
            parameters = request.get_json()
            search_for = validator.string_value (parameters, "search_for", 0, 32, required=True, strip_html=False)
            exclude = validator.array_value (parameters, "exclude", required=False)
            accounts   = self.db.accounts (search_for=search_for, limit=5)
            for index,_ in enumerate(accounts):
                account = accounts[index]
                if account["uuid"] in exclude:
                    accounts.pop(index)
            return self.default_list_response (accounts, formatter.format_account_details_record)
        except (validator.ValidationException, KeyError) as error:
            return self.error_400(request, error.message, error.code)

    def ui_dataset_new_private_link (self, request, dataset_uuid):
        """Implements /my/datasets/<uuid>/private_link/new."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed (request)

        if not validator.is_valid_uuid (dataset_uuid):
            return self.error_404 (request)

        dataset = None
        try:
            dataset = self.db.datasets (dataset_uuid = dataset_uuid,
                                        account_uuid = account_uuid,
                                        is_published = None,
                                        is_latest    = None,
                                        limit        = 1)[0]
        except IndexError:
            pass

        if dataset is None:
            return self.error_403 (request, (f"account:{account_uuid} attempted to create "
                                             f"private link for dataset:{dataset_uuid}."))

        if request.method in ("GET", "HEAD"):
            return self.__render_template (request, "depositor/new_private_link.html",
                                           dataset_uuid=dataset_uuid)

        if request.method == "POST":
            try:
                whom         = validator.string_value (request.form, "whom", 0, 128)
                purpose      = validator.string_value (request.form, "purpose", 0, 128)
                anonymize    = validator.string_value (request.form, "anonymize_link", 0, 2)
                anonymize    = bool(anonymize == "on")
                current_time = datetime.now()
                options      = ["1 day", "7 days", "30 days", "indefinitely"]
                expires_date = validator.options_value (request.form, "expires_date",
                                                        options, required=True)
                delta        = None
                feed_expire_time = None
                if expires_date == "1 day":
                    feed_expire_time = timedelta(days=1)
                elif expires_date == "7 days":
                    feed_expire_time = timedelta(days=7)
                elif expires_date == "30 days":
                    feed_expire_time = timedelta(days=30)

                if feed_expire_time is not None:
                    delta = current_time + feed_expire_time

                self.locks.lock (locks.LockTypes.PRIVATE_LINKS)
                self.db.insert_private_link (dataset["uuid"], account_uuid, whom=whom,
                                             purpose=purpose, expires_date=delta,
                                             anonymize=anonymize, item_type="dataset")
                self.locks.unlock (locks.LockTypes.PRIVATE_LINKS)
                return redirect (f"/my/datasets/{dataset_uuid}/private_links", code=302)
            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

        return self.error_405 (["GET", "HEAD", "POST"])

    def ui_collection_new_private_link (self, request, collection_uuid):
        """Implements /my/collections/<id>/private_link/new."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed (request)

        if not validator.is_valid_uuid (collection_uuid):
            return self.error_404 (request)

        collection = self.db.collections (collection_uuid = collection_uuid,
                                          account_uuid = account_uuid,
                                          is_published = None,
                                          is_latest    = None,
                                          limit        = 1)[0]

        if collection is None:
            return self.error_403 (request, (f"account:{account_uuid} attempted to create "
                                             f"private link for collection:{collection_uuid}."))

        self.locks.lock (locks.LockTypes.PRIVATE_LINKS)
        self.db.insert_private_link (collection["uuid"], account_uuid, item_type="collection")
        self.locks.unlock (locks.LockTypes.PRIVATE_LINKS)
        return redirect (f"/my/collections/{collection_uuid}/private_links", code=302)

    def __delete_private_link (self, request, item, account_uuid, private_link_id):
        """Deletes the private link for ITEM and responds appropriately."""
        if not item:
            return self.error_403 (request)

        response = redirect (request.referrer, code=302)
        self.locks.lock (locks.LockTypes.PRIVATE_LINKS)
        if self.db.delete_private_links (item["container_uuid"],
                                         account_uuid,
                                         private_link_id) is None:
            self.locks.unlock (locks.LockTypes.PRIVATE_LINKS)
            return self.error_500()

        self.locks.unlock (locks.LockTypes.PRIVATE_LINKS)
        return response

    def ui_dataset_delete_private_link (self, request, dataset_uuid, link_id):
        """Implements /my/datasets/<uuid>/private_link/<pid>/delete."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed (request)

        if not validator.is_valid_uuid (dataset_uuid):
            return self.error_404 (request)

        dataset = self.db.datasets (dataset_uuid = dataset_uuid,
                                    account_uuid = account_uuid,
                                    is_published = None,
                                    is_latest    = None,
                                    limit        = 1)[0]

        return self.__delete_private_link (request, dataset, account_uuid, link_id)

    def ui_collection_delete_private_link (self, request, collection_uuid, link_id):
        """Implements /my/collections/<id>/private_link/<pid>/delete."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed (request)

        if not validator.is_valid_uuid (collection_uuid):
            return self.error_404 (request)

        collection = self.db.collections (collection_uuid = collection_uuid,
                                          account_uuid = account_uuid,
                                          is_published = None,
                                          is_latest    = None,
                                          limit        = 1)[0]

        return self.__delete_private_link (request, collection, account_uuid, link_id)

    def ui_profile (self, request):
        """Implements /my/profile."""
        handler = self.default_error_handling (request, "GET", "text/html")
        if handler is not None:
            return handler

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed (request)

        try:
            return self.__render_template (
                request, "depositor/profile.html",
                account = self.db.accounts (account_uuid=account_uuid)[0],
                categories = self.db.categories_tree ())
        except IndexError:
            return self.error_403 (request)

    def ui_profile_connect_with_orcid (self, request):
        """Implements /my/profile/connect-with-orcid."""

        handler = self.default_error_handling (request, "GET", "text/html")
        if handler is not None:
            return handler

        # Start the authentication process for ORCID.
        if self.get_parameter (request, "code") is None:
            return redirect ((f"{config.orcid_endpoint}/authorize?client_id="
                              f"{config.orcid_client_id}&response_type=code"
                              "&scope=/authenticate&redirect_uri="
                              f"{config.base_url}/my/profile/connect-with-orcid"), 302)

        # Catch the response of the authentication process of ORCID.
        orcid_record = self.authenticate_using_orcid (
            request,
            redirect_path="/my/profile/connect-with-orcid")

        if orcid_record is None:
            return self.error_403 (request)

        orcid        = value_or_none (orcid_record, "orcid")
        full_name    = value_or_none (orcid_record, "name")
        first_name   = None
        last_name    = None

        # Attempt to split the full_name into first and last names.
        try:
            name_split = full_name.split (" ", 1)
            first_name = name_split[0]
            last_name  = name_split[1]
        except (AttributeError, IndexError):
            first_name = None
            last_name = None

        account_uuid = self.account_uuid_from_request (request)
        if orcid is None or account_uuid is None:
            return self.error_403 (request, (f"account:{account_uuid} failed "
                                             "to authenticate ORCID."))

        authors = self.db.authors (account_uuid=account_uuid, limit = 1)
        if not value_or (authors, 0, True):
            author_uuid = self.db.insert_author (
                account_uuid = account_uuid,
                orcid_id     = orcid,
                first_name   = first_name,
                last_name    = last_name,
                full_name    = full_name,
                is_active    = True,
                is_public    = True)
            self.log.info ("Created author record %s for account %s.",
                           author_uuid, account_uuid)

        if not self.db.update_orcid_for_account (account_uuid, orcid):
            return self.error_500 (f"Failed to update ORCID for {account_uuid}")

        return redirect ("/my/profile", 302)

    def ui_review_overview (self, request):
        """Implements /review/overview."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        token = self.token_from_cookie (request)
        may_review_all = self.db.may_review (token)
        may_review_institution = self.db.may_review_institution (token)
        if (not may_review_all and not may_review_institution):
            return self.error_403 (request)

        domain = None
        if may_review_institution:
            account = self.db.account_by_session_token (token)
            domain = value_or_none (account, "domain")

        reviewers = self.db.reviewer_accounts ()
        reviewers += self.db.institutional_reviewer_accounts (None)
        reviews = self.db.reviews (limit           = 10000,
                                   domain          = domain,
                                   order           = "request_date",
                                   order_direction = "desc")
        return self.__render_template (request, "review/overview.html",
                                       reviewers = reviewers,
                                       reviews = reviews)

    def __review_assign_or_unassign (self, request, dataset_id, status):
        """Simplifies the implementations to assign or unassign a reviewer."""

        account_uuid, error_response = self.__reviewer_account_uuid (request)
        if error_response is not None:
            return error_response

        if not validator.is_valid_uuid (dataset_id):
            return self.error_404 (request)

        dataset    = None
        try:
            dataset = self.db.datasets (dataset_uuid    = dataset_id,
                                        is_published    = False,
                                        is_under_review = True)[0]
        except (IndexError, TypeError):
            pass

        if dataset is None:
            return self.error_403 (request)

        if status == "unassigned":
            account_uuid = None

        if self.db.update_review (dataset["review_uri"],
                                  author_account_uuid = dataset["account_uuid"],
                                  assigned_to = account_uuid,
                                  status      = status):
            return redirect ("/review/overview", code=302)

        return self.error_500()

    def ui_review_assign_to_me (self, request, dataset_id):
        """Implements /review/assign-to-me/<id>."""
        return self.__review_assign_or_unassign (request, dataset_id, "assigned")

    def ui_review_unassign (self, request, dataset_id):
        """Implements /review/unassign/<id>."""
        return self.__review_assign_or_unassign (request, dataset_id, "unassigned")

    def ui_review_published (self, request, dataset_id):
        """Implements /review/published/<id>."""
        account_uuid, error_response = self.__reviewer_account_uuid (request)
        if error_response is not None:
            self.log.error ("Account %s attempted a reviewer action.", account_uuid)
            return error_response

        dataset = self.__dataset_by_id_or_uri (dataset_id,
                                               is_published = True,
                                               is_latest    = True)

        if dataset is None:
            return self.error_403 (request)

        return self.__render_template (request, "review/published.html",
                                       container_uuid=dataset["container_uuid"])

    def __process_quota_request (self, request, quota_request_uuid, status):
        token = self.token_from_cookie (request)
        if not self.db.may_review_quotas (token):
            return self.error_403 (request)

        if not validator.is_valid_uuid (quota_request_uuid):
            return self.error_400 (request, "Invalid quota request UUID.",
                                   "InvalidQuotaRequestUUIError")

        if self.db.update_quota_request (quota_request_uuid, status = status):
            if status == "approved":
                try:
                    record = self.db.quota_requests (quota_request_uuid=quota_request_uuid)[0]
                    subject = "Quota request approved"
                    requested_size = int(record["requested_size"] / 1000000000)
                    self.__send_templated_email ([record["email"]],
                                                 subject,
                                                 "quota_approved",
                                                 title          = subject,
                                                 email_address  = record["email"],
                                                 first_name     = record["first_name"],
                                                 requested_size = requested_size,
                                                 base_url       = config.base_url,
                                                 support_email  = config.support_email_address)
                except (IndexError, KeyError):
                    self.log.error ("Unable to send e-mail for quota request %s.",
                                    quota_request_uuid)
            return redirect ("/admin/quota-requests", code=302)

        return self.error_500 ()

    def ui_admin_approve_quota_request (self, request, quota_request_uuid):
        """Implements /admin/approve-quota-request/<id>."""
        return self.__process_quota_request (request, quota_request_uuid, "approved")

    def ui_admin_deny_quota_request (self, request, quota_request_uuid):
        """Implements /admin/approve-quota-request/<id>."""
        return self.__process_quota_request (request, quota_request_uuid, "denied")

    def ui_admin_quota_requests (self, request):
        """Implements /admin/quota-requests."""

        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        token = self.token_from_cookie (request)
        if not self.db.may_review_quotas (token):
            return self.error_403 (request)

        quota_requests = self.db.quota_requests (status="unresolved")
        return self.__render_template (request, "admin/quota_requests.html",
                                       quota_requests = quota_requests)

    def ui_admin_dashboard (self, request):
        """Implements /admin/dashboard."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        token = self.token_from_cookie (request)
        if not self.db.may_administer (token):
            return self.error_403 (request)

        missing_doi_items = self.db.missing_dois ()
        return self.__render_template (request, "admin/dashboard.html",
                                       missing_dois = len(missing_doi_items))

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

    def ui_admin_sparql (self, request):
        """Implements /admin/sparql."""

        token = self.token_from_cookie (request)
        if not self.db.may_query (token):
            return self.error_403 (request)

        if request.method == "GET":
            return self.__render_template (request, "admin/sparql.html")

        if request.method == "POST":
            query  = request.get_data().decode("utf-8")
            output = self.db.run_query (query, token)
            return self.response (json.dumps(output, indent=True))

        return self.error_500 ()

    def ui_admin_reports (self, request):
        """Implements /admin/reports."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        token = self.token_from_cookie (request)
        if not self.db.may_administer (token):
            return self.error_403 (request)

        return self.__render_template (request, "admin/reports/dashboard.html")

    def ui_admin_reports_restricted_datasets (self, request):
        """Implements /admin/reports/restricted_datasets."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        token = self.token_from_cookie (request)
        if not self.db.may_administer (token):
            return self.error_403 (request)

        restricted_datasets = self.db.datasets(is_restricted=True, limit=10000, is_latest=True, use_cache=False)

        export = self.get_parameter (request, "export")
        fileformat = self.get_parameter (request, "format")

        if export and fileformat:
            return self.__export_report_in_format (request, "restricted_datasets", restricted_datasets, fileformat)

        return self.__render_template (request, "admin/reports/restricted_datasets.html", datasets=restricted_datasets)

    def ui_admin_reports_embargoed_datasets (self, request):
        """Implements /admin/reports/embargoed_datasets."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        token = self.token_from_cookie (request)
        if not self.db.may_administer (token):
            return self.error_403 (request)

        embargoed_datasets = self.db.datasets(is_embargoed=True, limit=10000, is_latest=True, use_cache=False)

        export = self.get_parameter (request, "export")
        fileformat = self.get_parameter (request, "format")

        if export and fileformat:
            return self.__export_report_in_format (request, "embargoed_datasets", embargoed_datasets, fileformat)

        return self.__render_template (request, "admin/reports/embargoed_datasets.html", datasets=embargoed_datasets)

    def ui_admin_clear_cache (self, request):
        """Implements /admin/maintenance/clear-cache."""
        token = self.token_from_cookie (request)
        if self.db.may_administer (token):
            self.log.info ("Invalidating caches.")
            self.db.cache.invalidate_all ()
            return self.respond_204 ()

        return self.error_403 (request)

    def ui_admin_repair_doi_registrations (self, request):
        """Implements /admin/maintenance/repair-doi-registrations."""
        token = self.token_from_cookie (request)
        if not self.db.may_administer (token):
            return self.error_403 (request)

        items = self.db.missing_dois ()
        if items:
            self.log.info ("Repairing %s missing DOI registrations.", len(items))
            error_count = 0
            for item in items:
                if not self.__update_item_doi (item["container_uuid"],
                                               item_type  = item["item_type"],
                                               version    = item["version"],
                                               from_draft = False):
                    error_count += 1
                    self.log.error ("Registering DOI for publication of %s failed.",
                                    item["container_uuid"])
                    continue

                doi = self.__standard_doi (item["container_uuid"],
                                           version = item["version"])
                if not self.db.update_doi_after_publishing (item["uuid"],
                                                            item["item_type"],
                                                            doi):
                    self.log.error ("Updating the DOI '%s' in the database failed for %s.",
                                    doi, item["uuid"])

            if error_count == 0:
                return self.respond_204 ()

            return self.error_500 ()

        return self.respond_204 ()

    def ui_admin_recalculate_statistics (self, request):
        """Implements /admin/maintenance/recalculate-statistics."""
        token = self.token_from_cookie (request)
        if self.db.may_administer (token):
            if self.db.update_view_and_download_counts ():
                self.log.info ("Recalculated statistics.")
                return self.respond_204 ()

            return self.error_500 ("Failed to recalculate statistics.")

        return self.error_403 (request)

    def ui_admin_clear_sessions (self, request):
        """Implements /admin/maintenance/clear-sessions."""
        token = self.token_from_cookie (request)
        if self.db.may_administer (token):
            self.log.info ("Invalidating sessions.")
            self.db.delete_all_sessions ()
            return redirect ("/", code=302)

        return self.error_403 (request)

    def __email_from_request (self, request):
        """Attempts to find the e-mail address associated with REQUEST."""
        email = None
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid:
            try:
                account = self.db.accounts (account_uuid = account_uuid)[0]
                email   = account['email']
            except IndexError:
                self.log.warning ("No email found for account %s.", account_uuid)

        return email

    def ui_feedback (self, request):
        """Implement /feedback."""

        addresses = self.db.feedback_reviewer_email_addresses()
        if not addresses:
            return self.error_404 (request)

        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        if request.method in ("GET", "HEAD"):
            email = self.__email_from_request (request)
            return self.__render_template (request, "feedback.html", email=email)

        if request.method == "POST":
            record = {
                "email":       request.form.get("email"),
                "type":        request.form.get("feedback_type"),
                "description": request.form.get("description")
            }
            self.log.info("Received from feedback form: %s", record)
            try:
                validator.string_value (record, "email", 5, 255, False)
                validator.options_value (record, "type", ["bug", "missing", "other"], True)
                validator.string_value (record, "description", 10, 4096, True, strip_html=False)
            except validator.ValidationException as error:
                email = self.__email_from_request (request)
                return self.__render_template (request, "feedback.html",
                                               email = email,
                                               error_message = error.message)

            subject = "Feedback for Djehuty"
            if record["type"] == "bug":
                subject = "Bug report for Djehuty"
            elif record["type"] == "missing":
                subject = "Missing feature report for Djehuty"

            self.__send_templated_email (
                addresses,
                subject,
                "feedback",
                title         = subject,
                email_address = record["email"],
                report_type   = record["type"],
                description   = record["description"])

            return self.__render_template (request, "feedback.html",
                                           email = record["email"],
                                           success_message = "Thank you! Your feedback has been sent.")

        return self.error_405 (["GET", "POST"])

    def ui_home (self, request):
        """Implements /portal."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        summary_data = self.db.repository_statistics()
        try:
            for key in summary_data:
                summary_data[key] = f"{int(summary_data[key]):,}"
        except ValueError:
            summary_data = { "datasets": 0, "authors": 0, "collections": 0, "files": 0, "bytes": 0 }

        latest = []
        try:
            records = self.db.latest_datasets_portal(30)
            for rec in records:
                pub_date = rec['published_date'][:10]
                url = f'/datasets/{rec["container_uuid"]}'
                latest.append((url, rec['title'], pub_date))
        except (IndexError, KeyError):
            pass

        return self.__render_template (request, "portal.html",
                                       summary_data = summary_data,
                                       latest = latest,
                                       notice_message = config.notice_message,
                                       show_portal_summary = config.show_portal_summary,
                                       show_institutions = config.show_institutions,
                                       show_science_categories = config.show_science_categories,
                                       show_latest_datasets = config.show_latest_datasets)

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
            validator.integer_value ({ "id": category_id }, "id", required=True)
        except validator.ValidationException:
            return self.error_404 (request)

        category      = self.db.category_by_id (category_id)
        if category is None:
            return self.error_404 (request)

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
                                        is_published = None,
                                        is_latest    = None,
                                        use_cache    = False)[0]
            if value_or (dataset, "private_link_is_expired", False):
                return self.__render_template (request, "private_link_is_expired.html")

            self.__log_event (request, dataset["container_uuid"], "dataset", "privateView")
            return self.ui_dataset (request, dataset["container_uuid"],
                                    dataset=dataset, private_view=True,
                                    anonymize=value_or(dataset, "anonymize", False))
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
                                              is_published = None,
                                              is_latest    = None)[0]
            if value_or (collection, "private_link_is_expired", False):
                return self.__render_template (request, "private_link_is_expired.html")

            self.__log_event (request, collection["container_uuid"], "collection", "view")
            return self.ui_collection (request, collection["container_uuid"],
                                       collection=collection, private_view=True)
        except IndexError:
            pass

        return self.error_404 (request)

    def ui_compat_dataset (self, request, slug, dataset_id, version=None):  # pylint: disable=unused-argument
        """Implements backward-compatibility landing page URLs for datasets."""
        return self.ui_dataset (request, dataset_id, version)

    def ui_dataset (self, request, dataset_id, version=None, dataset=None, private_view=False, anonymize=False):
        """Implements /datasets/<id>."""

        handler = self.default_error_handling (request, "GET", "text/html")
        if handler is not None:
            return handler

        if dataset is None:
            if version is not None:
                dataset = self.__dataset_by_id_or_uri (dataset_id, is_published=True, version=version)
            else:
                dataset = self.__dataset_by_id_or_uri (dataset_id, is_published=True, is_latest=True)

            ## For retracted datasets we display a different error page.
            if dataset is None:
                dataset = self.__dataset_by_id_or_uri (dataset_id, is_published=None, is_latest=None)
                if dataset is not None and value_or (dataset, "is_public", 1) == 0:
                    return self.error_410 (request)
                return self.error_404 (request)

        my_collections = []
        my_email = None
        my_name  = None
        is_own_item = False
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid:
            dataset_account_uuid = value_or_none(dataset, 'account_uuid')
            is_own_item = dataset_account_uuid == account_uuid
            my_collections = self.db.collections_by_account (account_uuid = account_uuid)
            # Name and email may be needed to request access to data with restricted access.
            if value_or_none(dataset, 'is_restricted'):
                try:
                    my_account = self.db.accounts (account_uuid = account_uuid)[0]
                    my_email = my_account['email']
                    first_name = value_or(my_account, 'first_name', '')
                    last_name  = value_or(my_account, 'last_name' , '')
                    my_name = f'{first_name} {last_name}'.strip()
                except IndexError:
                    self.log.warning ("No email found for account %s.", account_uuid)

        versions      = self.db.dataset_versions (container_uri=dataset["container_uri"])
        if not versions:
            versions = [{"version": 1}]
        versions      = [v for v in versions if v["version"]]
        id_version    = f"{dataset_id}/{version}" if version else f"{dataset_id}"

        authors       = self.db.authors(item_uri=dataset["uri"], limit=None)
        files_params  = {'dataset_uri': dataset['uri'], 'order': 'order_name'}
        if is_own_item:
            files_params['account_uuid'] = account_uuid
        elif private_view:
            files_params['private_view'] = True
        files         = self.db.dataset_files(**files_params)
        files_size    = sum(value_or(f,'size',0) for f in files)
        tags          = self.db.tags(item_uri=dataset["uri"], limit=None)
        categories    = self.db.categories(item_uri=dataset["uri"], limit=None)
        references    = self.db.references(item_uri=dataset["uri"], limit=None)
        derived_from  = self.db.derived_from(item_uri=dataset["uri"], limit=None)
        fundings      = self.db.fundings(item_uri=dataset["uri"], limit=None)
        collections   = self.db.collections_from_dataset(dataset["container_uuid"])

        statistics    = {
            "views"  : value_or(dataset, "total_views",  0),
            "shares" : value_or(dataset, "total_shares", 0),
            "cites"  : value_or(dataset, "total_cites",  0)
        }

        if (value_or (dataset, "is_public", False) and
            not (value_or (dataset, "is_restricted", False) or
                 value_or (dataset, "is_embargoed", False))):
            statistics["downloads"] = value_or (dataset, "total_downloads", 0)

        statistics = {key:val for (key,val) in statistics.items() if val > 0}
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
            if is_opendap_url (url):
                opendap.append(url)
                del dataset['data_link']
        contributors = self.parse_contributors(value_or(dataset, 'contributors', ''))
        git_repository_url = self.__git_repository_url_for_dataset (dataset)

        if not private_view:
            self.__log_event (request, dataset["container_uuid"], "dataset", "view")

        defined_type_name = value_or (dataset, 'defined_type_name', 'dataset')
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
                                       files_size=files_size,
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
                                       posted_date=posted_date,
                                       private_view=private_view,
                                       my_email=my_email,
                                       my_name=my_name,
                                       is_own_item=is_own_item,
                                       anonymize=anonymize,
                                       page_title=f"{dataset['title']} ({defined_type_name})")

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
            reason     = validator.string_value (parameters, "reason", 0, 10000, required=True, strip_html=False)

            dataset = self.db.datasets (container_uuid=dataset_id, version=version)[0]

            if not value_or_none(dataset, 'is_confidential') and not (not value_or_none(dataset, 'embargo_until_date') and value_or_none(dataset, 'embargo_type')):
                return self.error_403 (request, (f"{email} attempted to request "
                                                 "access to non-confidential "
                                                 f"dataset:{dataset_id}."))

            # When in pre-production state, don't mind about DOI.
            doi = value_or_none(dataset, 'doi')
            if doi is None and config.in_production and not config.in_preproduction:
                return self.error_403 (request, f"dataset:{dataset_id} does not have a DOI.")
            title = dataset['title']
            contact_info = self.db.contact_info_from_container(dataset_id)
            addresses = self.db.reviewer_email_addresses()

            # When in pre-production state, don't send e-mails to depositors.
            owner_email = None
            if contact_info and config.in_production and not config.in_preproduction:
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
        except IndexError:
            return self.error_400 (request, "Dataset does not exist", 400)

        return self.error_500 ()

    def ui_compat_collection (self, request, slug, collection_id, version=None):  # pylint: disable=unused-argument
        """Implements backward-compatibility landing page URLs for collections."""
        return self.ui_collection (request, collection_id, version)

    def ui_collection (self, request, collection_id, version=None,
                       collection=None, private_view=False):
        """Implements /collections/<id>."""

        handler = self.default_error_handling (request, "GET", "text/html")
        if handler is not None:
            return handler

        #handle abnormal pattern /collections/<slug>/<collection_id> instead of /collections/<collection_id>/<version>
        if collection_id is not None and version is not None:
            normal_pattern = False
            try:
                version_number = int(version)
                if version_number < 10000:
                    normal_pattern = True
            except ValueError:
                pass
            if not normal_pattern:
                return self.ui_collection(request, version)

        if collection is None:
            if version is not None:
                collection = self.__collection_by_id_or_uri (collection_id, is_published=True, version=version)
            else:
                collection = self.__collection_by_id_or_uri (collection_id, is_published=True, is_latest=True)

        # For retracted collections we display a different error page.
        if collection is None:
            collection = self.__collection_by_id_or_uri (collection_id, is_published=None, is_latest=None)
            if collection is not None and value_or (collection, "is_public", 1) == 0:
                return self.error_410 (request)
            return self.error_404 (request)

        container_uuid = collection["container_uuid"]
        container_uri  = f"container:{container_uuid}"

        versions      = self.db.collection_versions(container_uri=container_uri)
        if not versions:
            versions = [{"version":1}]
        versions      = [v for v in versions if v['version']]

        collection_uri = collection['uri']
        authors       = self.db.authors(item_uri=collection_uri, item_type='collection', limit=None)
        tags          = self.db.tags(item_uri=collection_uri, limit=None)
        categories    = self.db.categories(item_uri=collection_uri, limit=None)
        references    = self.db.references(item_uri=collection_uri, limit=None)
        fundings      = self.db.fundings(item_uri=collection_uri, item_type='collection', limit=None)
        statistics    = {'downloads': value_or(collection, 'total_downloads', 0),
                         'views'    : value_or(collection, 'total_views'    , 0),
                         'shares'   : value_or(collection, 'total_shares'   , 0),
                         'cites'    : value_or(collection, 'total_cites'    , 0)}
        statistics    = {key:val for (key,val) in statistics.items() if val > 0}
        member = value_or(group_to_member, value_or_none (collection, "group_id"), 'other')
        member_url_name = member_url_names[member]
        tags = { t['tag'] for t in tags }
        collection['timeline_first_online'] = value_or_none (collection, 'timeline_first_online')
        dates = self.__pretty_print_dates_for_item (collection)

        posted_date = value_or_none (collection, "timeline_posted")
        if posted_date is not None:
            posted_date = posted_date[:4]
        else:
            posted_date = "unpublished"

        citation = make_citation(authors, posted_date, value_or (collection, 'title', 'Untitled'),
                                 value_or (collection, 'version', 0),
                                 'collection',
                                 value_or (collection, 'doi', 'unavailable'))

        lat = self_or_value_or_none(collection, 'latitude')
        lon = self_or_value_or_none(collection, 'longitude')
        lat_valid, lon_valid = decimal_coords(lat, lon)
        coordinates = {'lat': lat, 'lon': lon, 'lat_valid': lat_valid, 'lon_valid': lon_valid}

        contributors = self.parse_contributors(value_or(collection, 'contributors', ''))
        datasets     = self.db.collection_datasets(collection_uri)

        if not private_view:
            self.__log_event (request, container_uuid, "collection", "view")

        return self.__render_template (request, "collection.html",
                                       item=collection,
                                       version=version,
                                       versions=versions,
                                       citation=citation,
                                       container_doi=value_or_none(collection, 'container_doi'),
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
                                       private_view=private_view,
                                       page_title=f"{collection['title']} (collection)")

    def ui_author (self, request, author_uuid):
        """Implements /authors/<id>."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        if not validator.is_valid_uuid (author_uuid):
            return self.error_403 (request)

        author_uri = f'author:{author_uuid}'
        try:
            profile = self.db.author_profile (author_uri)[0]
            public_items = self.db.author_public_items(author_uri)
            datasets    = [pi for pi in public_items if pi['is_dataset']]
            collections = [pi for pi in public_items if not pi['is_dataset']]
            associated_authors = self.db.associated_authors (author_uri)
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
                                           associated_authors=associated_authors,
                                           member=member,
                                           member_url_name=member_url_name,
                                           categories=categories,
                                           statistics=statistics,
                                           page_title=f"{value_or(profile, 'full_name', 'unknown')} (profile)")
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

    def __dataset_by_referer (self, request):
        dataset = None
        try:
            referer       = request.headers.get ("Referer")
            referer_begin = f"{config.base_url}/private_datasets/"
            if referer.startswith (referer_begin):
                private_link_id = referer.partition (referer_begin)[2]

                dataset = self.db.datasets (private_link_id_string = private_link_id,
                                            is_published = None,
                                            is_latest    = None,
                                            use_cache    = False,
                                            limit        = 1)[0]

                if value_or (dataset, "private_link_is_expired", False):
                    dataset = None

        except (AttributeError, IndexError):
            pass

        return dataset

    def __filesystem_location (self, file_info):
        """Procedure to gather the filesystem location from file metadata."""

        # There are two ways to configure storage in Djehuty. The historical
        # way one can configure primary-storage-root and secondary-storage-root.
        # In the 'new way', one lists the storage locations in the 'storage'
        # configuration option.

        # This is only used for quirks-mode.
        allowed_chars = ".0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz"

        # Traverse the 'storage' locations -- the new way of configuring storage.
        file_path = None
        if config.storage_locations:
            for location in config.storage_locations:
                if "filename" in file_info:
                    file_path = os.path.join (location['path'], file_info['filename'])
                    if os.path.isfile (file_path):
                        return file_path
                elif "id" in file_info:
                    ## Data stored before Djehuty went into production requires a few tweaks.
                    ## Only apply these quirks when enabled.
                    name = file_info['name']
                    if value_or (location, "quirks", False):
                        name = ''.join(char for char in name if char in allowed_chars)
                    file_path = os.path.join (location['path'], f"{file_info['id']}", name)
                    if os.path.isfile (file_path):
                        return file_path

            self.log.error ("File %s could not be found in the configured storage locations.",
                            file_path)
            return None

        # Use primary-storage-root and secondary-storage-root -- the historical
        # way of configuring storage.

        ## The filesystem_location property was introduced in Djehuty.
        ## It isn't set for files deposited before Djehuty went into production.
        if "filesystem_location" in file_info:
            file_path = file_info["filesystem_location"]

        ## Files deposited pre-Djehuty have a numeric identifier (id)
        elif "id" in file_info:
            name = file_info['name']

            ## Data stored before Djehuty went into production requires a few tweaks.
            ## Only apply these quirks when enabled.
            if config.secondary_storage_quirks:
                name = ''.join(char for char in name if char in allowed_chars)
            file_path = os.path.join (config.secondary_storage, f"{file_info['id']}", name)

        return file_path

    def __accessible_files_for_dataset (self, request, dataset_id, file_id=None, version=None):
        """Implements /file/<id>/<fid>."""

        ## Access control
        ## --------------------------------------------------------------------
        metadata = None

        ## Check whether a download is requested from a private link.
        dataset = self.__dataset_by_referer (request)
        if dataset is not None:
            if file_id is None:
                self.log.info ("Files for %s accessed through private link.", dataset_id)
                metadata = self.__files_by_id_or_uri (dataset_uri = dataset["uri"],
                                                      private_view=True)
            else:
                self.log.info ("File %s accessed through private link.", file_id)
                metadata = self.__file_by_id_or_uri (file_id, private_view=True)

            return dataset, metadata

        # Published datasets
        dataset = self.__dataset_by_id_or_uri (dataset_id,
                                               is_published = True,
                                               version      = version,
                                               use_cache    = False)
        if dataset is not None:
            is_embargoed  = value_or (dataset, "is_embargoed", False)
            is_restricted = value_or (dataset, "is_restricted", False)
            if is_embargoed or is_restricted:
                # The uploader of the dataset may download it.
                account_uuid = self.account_uuid_from_request (request)
                if value_or_none (dataset, "account_uuid") == account_uuid:
                    if file_id is None:
                        self.log.info ("Files for %s accessed by owner or reviewer.", dataset_id)
                        metadata = self.__files_by_id_or_uri (dataset_uri = dataset["uri"],
                                                              account_uuid = account_uuid)
                    else:
                        self.log.info ("File %s accessed by owner or reviewer.", file_id)
                        metadata = self.__file_by_id_or_uri (file_id,
                                                             account_uuid = account_uuid)
            else:
                if file_id is None:
                    self.log.info ("Files for %s accessed through published dataset.", dataset_id)
                    metadata = self.__files_by_id_or_uri (dataset_uri = dataset["uri"])
                else:
                    self.log.info ("File %s accessed through published dataset.", file_id)
                    metadata = self.__file_by_id_or_uri (file_id)

            return dataset, metadata

        # Draft datasets
        # The uploader of the dataset may download it.
        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is not None:
            dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                   is_published = False,
                                                   account_uuid = account_uuid,
                                                   use_cache    = False)
            if file_id is None:
                self.log.info ("Files for draft %s accessed by owner or reviewer.", dataset_id)
                metadata = self.__files_by_id_or_uri (dataset_uri  = dataset["uri"],
                                                      account_uuid = account_uuid)
            else:
                self.log.info ("File %s for draft accessed by owner or reviewer.", file_id)
                metadata = self.__file_by_id_or_uri (file_id, account_uuid = account_uuid)

        return dataset, metadata

    def ui_download_file (self, request, dataset_id, file_id):
        """Implements /file/<id>/<fid>."""
        dataset, metadata = self.__accessible_files_for_dataset (request, dataset_id, file_id)

        ## If no dataset has been found that means the file is not
        ## publically accessible, the file isn't of the user and the user
        ## isn't coming from a private link viewing.
        if dataset is None or metadata is None:
            return self.error_403 (request, (f"Denied access to file:{file_id} "
                                             f"in dataset:{dataset_id}."))

        if "container_uuid" not in dataset or "container_uuid" not in metadata:
            return self.error_403 (request, ("Missing container UUID for dataset:"
                                             f"{dataset_id} or file:{file_id}."))

        if dataset["container_uuid"] != metadata["container_uuid"]:
            return self.error_403 (request, ("Found a mismatch between container UUID "
                                             f"for dataset:{dataset['container_uuid']} and "
                                             f"file:{metadata['container_uuid']}."))

        ## Filesystem interaction
        ## --------------------------------------------------------------------
        try:
            file_path = self.__filesystem_location (metadata)
            if file_path is None:
                return self.error_500 ("File download failed due to missing metadata.")

            if self.__is_reviewing (request):
                self.__log_event (request, dataset["container_uuid"], "dataset", "reviewerDownload")
            else:
                self.__log_event (request, dataset["container_uuid"], "dataset", "download")

            try:
                return send_file (file_path,
                                  request.environ,
                                  "application/octet-stream",
                                  as_attachment=True,
                                  download_name=metadata["name"])
            except PermissionError:
                self.log.error ("Back-end has no permission to access file %s.", file_path)
                return self.error_403 (request)

        except FileNotFoundError:
            self.log.error ("File download failed due to missing file: '%s'.", file_path)

        return self.error_404 (request)

    def ui_download_all_files (self, request, dataset_id, version):
        """Implements /ndownloader/items/<id>/versions/<version>"""

        dataset, metadata = self.__accessible_files_for_dataset (request, dataset_id, version=version)
        if dataset is None or metadata is None:
            return self.error_403 (request)

        try:
            file_paths = []
            for file_info in metadata:
                file_path = self.__filesystem_location (file_info)
                if file_path is None:
                    self.log.error ("Excluding missing file %s in ZIP of %s.",
                                    file_info["name"], dataset_id)
                    continue
                file_paths.append ({
                    "fs": file_path,
                    "n":  file_info["name"]
                })

            if not file_paths:
                self.log.error ("Download-all for %s failed: %s.",
                                dataset_id,
                                "No files associated with this dataset")
                return self.error_404 (request)

            writer = None
            try:
                zipfly_object = zipfly.ZipFly(paths = file_paths)
                writer = zipfly_object.generator()
            except TypeError:
                self.log.error ("Error in zipping files: %s", file_paths)
                return self.error_404 (request)

            response = self.response (writer, mimetype="application/zip")

            if version is None:
                version = "draft"
            if validator.index_exists (dataset["title"], 127):
                dataset["title"] = f"{dataset['title'][:126]}>"

            safe_title = dataset["title"].replace('"', '')
            safe_title_ascii = safe_title.encode('ascii', 'ignore').decode('ascii')
            filename = f'"{safe_title_ascii}_{version}_all.zip"'
            response.headers["Content-disposition"] = f"attachment; filename={filename}"
            if safe_title != safe_title_ascii:
                filename_utf8 = f"{quote(safe_title)}_{version}_all.zip"
                response.headers["Content-disposition"] += f"; filename*=UTF-8''{filename_utf8}"

            if self.__is_reviewing (request):
                self.__log_event (request, dataset["container_uuid"], "dataset", "reviewerDownload")
            else:
                self.__log_event (request, dataset["container_uuid"], "dataset", "download")

            return response

        except (FileNotFoundError, KeyError, IndexError, TypeError) as error:
            self.log.error ("Files download for %s failed due to: %s.", dataset_id, error)
            return self.error_404 (request)

    def ui_search (self, request):
        """Implements /search."""
        if not self.accepts_html (request):
            return self.error_406 ("text/html")

        search_for = self.get_parameter(request, "search")
        if search_for is None:
            search_for = ""

        search_for = search_for.strip()
        categories = self.db.categories(limit=None)
        licenses   = self.db.licenses()
        groups     = self.db.group()
        return self.__render_template (request, "search.html",
                                       search_for=search_for,
                                       licenses=licenses,
                                       institutions=groups,
                                       categories=categories,
                                       page_title=f"{search_for} (search)")

    def api_authorize (self, request):
        """Implements /v2/account/applications/authorize."""
        return self.error_404 (request)

    def api_token (self, request):
        """Implements /v2/token."""
        return self.error_404 (request)

    def api_private_institution (self, request):
        """Implements /v2/account/institution."""
        account_uuid = self.default_authenticated_error_handling (request, "GET", "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        ## Our API only contains data from 4TU.ResearchData.
        return self.response (json.dumps({ "id": 898, "name": config.site_name }))

    def api_private_institution_accounts (self, request):
        """Implements /v2/account/institution/accounts."""

        handler = self.default_authenticated_error_handling (request, "GET", "application/json",
                                                             self.db.may_administer)
        if isinstance (handler, Response):
            return handler

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
        account_uuid = self.default_authenticated_error_handling (request, "GET", "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

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
            record["is_latest"] = 1
            records = self.db.datasets (**record)
            return self.default_list_response (records, formatter.format_dataset_record,
                                               base_url = config.base_url)

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    def api_datasets_search (self, request):
        """Implements /v2/articles/search."""

        if request.method == "OPTIONS":
            response = self.respond_204 ()
            response.headers["Accept"] = "application/json"
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Request-Methods"] = "POST"
            return response

        handler = self.default_error_handling (request, "POST", "application/json")
        if handler is not None:
            return handler

        try:
            record  = self.__default_dataset_api_parameters (request.get_json())
            records = self.db.datasets (**record)
            output  = self.default_list_response (records, formatter.format_dataset_record,
                                                  base_url = config.base_url)
            output.headers["Access-Control-Allow-Origin"] = "*"
            return output
        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    def api_licenses (self, request):
        """Implements /v2/licenses."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        records = self.db.licenses()
        return self.default_list_response (records, formatter.format_license_record)

    def api_categories (self, request):
        """Implements /v2/categories."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        records = self.db.categories(limit=None)
        return self.default_list_response (records, formatter.format_category_record)

    def api_account (self, request):
        """Implements /v2/account."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        token   = self.token_from_request (request)
        account = self.db.account_by_session_token (token)
        if account is None:
            return self.error_authorization_failed (request)

        return self.response (json.dumps(formatter.format_account_record (account)))

    def api_dataset_details (self, request, dataset_id):
        """Implements /v2/articles/<id>."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        try:
            dataset         = self.__dataset_by_id_or_uri (dataset_id, account_uuid=None, is_latest=True)

            # Passing along the base_url here to generate the API links.
            dataset["base_url"] = config.base_url

            dataset_uri     = dataset["uri"]
            authors         = self.db.authors(item_uri=dataset_uri, item_type="dataset")
            files           = self.db.dataset_files(dataset_uri=dataset_uri)
            custom_fields   = self.db.custom_fields(item_uri=dataset_uri, item_type="dataset")
            tags            = self.db.tags(item_uri=dataset_uri)
            categories      = self.db.categories(item_uri=dataset_uri, limit=None)
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
            custom = value_or (total, "custom_fields", [])
            custom = [c for c in custom if c['name'] != 'Derived From']
            custom.append( {"name": "Derived From",
                            "value": self.db.derived_from(item_uri=dataset_uri)} )
            total['custom_fields'] = custom
            return self.response (json.dumps(total))
        except (IndexError, TypeError):
            return self.error_404 (request)

    def api_dataset_versions (self, request, dataset_id):
        """Implements /v2/articles/<id>/versions."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        container = self.__dataset_by_id_or_uri (dataset_id, is_published=True)
        if container is None:
            return self.error_404 (request)

        versions  = self.db.dataset_versions (container_uri=container["container_uri"])
        return self.default_list_response (versions, formatter.format_dataset_version_record,
                                           base_url = config.base_url)

    def api_dataset_version_details (self, request, dataset_id, version):
        """Implements /v2/articles/<id>/versions/<version>."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        dataset = self.__dataset_by_id_or_uri (dataset_id,
                                               is_published = True,
                                               version = version)
        if dataset is None:
            return self.error_404 (request)

        # Passing along the base_url here to generate the API links.
        dataset["base_url"] = config.base_url

        dataset_uri   = dataset["uri"]
        authors       = self.db.authors(item_uri=dataset_uri, item_type="dataset")
        files         = self.db.dataset_files(dataset_uri=dataset_uri)
        custom_fields = self.db.custom_fields(item_uri=dataset_uri, item_type="dataset")
        tags          = self.db.tags(item_uri=dataset_uri)
        categories    = self.db.categories(item_uri=dataset_uri, limit=None)
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

    def api_dataset_version_embargo (self, request, dataset_id, version):
        """Implements /v2/articles/<id>/versions/<version>/embargo."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        dataset = self.__dataset_by_id_or_uri (dataset_id,
                                               version      = version,
                                               is_published = True)
        if dataset is None:
            return self.error_404 (request)

        total   = formatter.format_dataset_embargo_record (dataset)
        return self.response (json.dumps(total))

    def api_dataset_version_confidentiality (self, request, dataset_id, version):
        """Implements /v2/articles/<id>/versions/<version>/confidentiality."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        dataset = self.__dataset_by_id_or_uri (dataset_id,
                                               version = version,
                                               is_published = True)
        if dataset is None:
            return self.error_404 (request)

        total = formatter.format_dataset_confidentiality_record (dataset)
        return self.response (json.dumps(total))

    def api_dataset_version_update_thumb (self, request, dataset_id, version):
        """Implements /v2/articles/<id>/versions/<version>/update_thumb."""
        account_uuid = self.default_authenticated_error_handling (request, "PUT", "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        parameters = request.get_json()
        file_id    = value_or_none (parameters, "file_id")
        dataset    = self.__dataset_by_id_or_uri (dataset_id, version = version)
        if dataset is None:
            return self.error_404 (request)

        metadata   = self.__file_by_id_or_uri (file_id,
                                               dataset_uri  = dataset["uri"],
                                               account_uuid = account_uuid)
        if metadata is None:
            return self.error_404 (request)

        input_filename = self.__filesystem_location (metadata)
        if input_filename is None:
            return self.error_404 (request)

        extension = self.__generate_thumbnail (self, input_filename, dataset["uuid"])
        if extension is None:
            return self.error_500 ()

        if not self.db.dataset_update_thumb (dataset_id, account_uuid,
                                             metadata["uuid"], extension, version):
            return self.error_500()

        return self.respond_205()

    def api_dataset_files (self, request, dataset_id):
        """Implements /v2/articles/<id>/files."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        dataset = self.__dataset_by_id_or_uri (dataset_id, is_published=True)
        if dataset is None:
            return self.error_404 (request)

        is_embargoed  = value_or (dataset, "is_embargoed", False)
        is_restricted = value_or (dataset, "is_restricted", False)
        files         = []
        if not (is_embargoed or is_restricted):
            files = self.db.dataset_files (dataset_uri=dataset["uri"])

        return self.default_list_response (files, formatter.format_file_for_dataset_record,
                                           base_url = config.base_url)

    def api_dataset_file_details (self, request, dataset_id, file_id):
        """Implements /v2/articles/<id>/files/<fid>."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        try:
            dataset = self.__dataset_by_id_or_uri (dataset_id, is_published=True)
            record = self.__file_by_id_or_uri (file_id, dataset_uri = dataset["uri"])
            record["base_url"] = config.base_url

            results = formatter.format_file_for_dataset_record (record)
            return self.response (json.dumps(results))
        except IndexError:
            response = self.response (json.dumps({
                "message": "This file cannot be found."
            }))
            response.status_code = 404
            return response

    def api_private_datasets (self, request):
        """Implements /v2/account/articles."""
        account_uuid = self.default_authenticated_error_handling (request,
                                                                  ["GET", "POST"],
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        if request.method in ("GET", "HEAD"):
            try:
                offset, limit = self.__paging_offset_and_limit (request)
                records = self.db.datasets (limit=limit,
                                            offset=offset,
                                            is_published = False,
                                            account_uuid=account_uuid)

                return self.default_list_response (records, formatter.format_dataset_record,
                                                   base_url = config.base_url)

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
                    description    = validator.string_value  (record, "description",    0, 10000, False, strip_html=False),
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
                    publisher_publication = validator.string_value (timeline, "publisherPublication",              False),
                    submission            = validator.string_value (timeline, "submission",                        False),
                    posted                = validator.string_value (timeline, "posted",                            False),
                    revision              = validator.string_value (timeline, "revision",                          False)
                )

                return self.response(json.dumps({
                    "location": f"{config.base_url}/v2/account/articles/{container_uuid}",
                    "warnings": []
                }))
            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

        return self.error_500 ()

    def api_private_dataset_details (self, request, dataset_id):
        """Implements /v2/account/articles/<id>."""
        account_uuid = self.default_authenticated_error_handling (request,
                                                                  ["GET", "PUT", "DELETE"],
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        if request.method in ("GET", "HEAD"):
            try:
                dataset     = self.__dataset_by_id_or_uri (dataset_id,
                                                           account_uuid=account_uuid,
                                                           is_published=False)

                dataset_uri     = value_or_none (dataset, "uri")
                if dataset_uri is None:
                    return self.response ("[]")

                _, error_response = self.__needs_collaborative_permissions (
                    account_uuid, request, "dataset", dataset, "metadata_read")
                if error_response is not None:
                    return error_response

                dataset["doi"]  = self.__standard_doi (dataset["container_uuid"],
                                                       version = None,
                                                       container_doi = value_or_none (dataset, "container_doi"))
                authors         = self.db.authors(item_uri=dataset_uri, item_type="dataset")
                files           = self.db.dataset_files(dataset_uri=dataset_uri, account_uuid=account_uuid)
                custom_fields   = self.db.custom_fields(item_uri=dataset_uri, item_type="dataset")
                tags            = self.db.tags(item_uri=dataset_uri)
                categories      = self.db.categories(item_uri=dataset_uri, limit=None)
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
                custom = value_or (total, "custom_fields", [])
                custom = [c for c in custom if c['name'] != 'Derived From']
                custom.append( {"name": "Derived From",
                                "value": self.db.derived_from(item_uri=dataset_uri)} )
                total['custom_fields'] = custom
                return self.response (json.dumps(total))
            except (IndexError, KeyError) as error:
                self.log.error ("Failed to retrieve dataset due to: %s", error)
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

                if dataset is None:
                    return self.error_403 (request, (f"account{account_uuid} attempted "
                                                     f"to modify dataset:{dataset_id}."))

                _, error_response = self.__needs_collaborative_permissions (
                    account_uuid, request, "dataset", dataset, "metadata_edit")
                if error_response is not None:
                    return error_response

                is_embargoed = validator.boolean_value (record, "is_embargoed", when_none=False)
                embargo_options = validator.array_value (record, "embargo_options")
                embargo_option  = value_or_none (embargo_options, 0)
                is_restricted   = value_or (embargo_option, "id", 0) == 1000
                is_closed       = value_or (embargo_option, "id", 0) == 1001
                is_temporary_embargo = is_embargoed and not is_restricted and not is_closed
                license_id  = validator.integer_value (record, "license_id", 0, pow(2, 63))
                license_url = self.db.license_url_by_id (license_id)

                if is_restricted or is_closed:
                    record["embargo_type"] = "file"

                result = self.db.update_dataset (dataset["uuid"],
                    account_uuid,
                    title           = validator.string_value  (record, "title",          3, 1000),
                    description     = validator.string_value  (record, "description",    0, 10000, strip_html=False),
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
                    mimetype        = validator.string_value  (record, "format",         0, 512),
                    data_link       = validator.string_value  (record, "data_link",      0, 255),
                    derived_from    = validator.string_value  (record, "derived_from",   0, 255),
                    same_as         = validator.string_value  (record, "same_as",        0, 255),
                    organizations   = validator.string_value  (record, "organizations",  0, 2048),
                    is_embargoed    = is_embargoed,
                    is_restricted   = is_restricted,
                    is_metadata_record = validator.boolean_value (record, "is_metadata_record", when_none=False),
                    metadata_reason = validator.string_value  (record, "metadata_reason",  0, 512, strip_html=False),
                    embargo_until_date = validator.date_value (record, "embargo_until_date",
                                                               is_temporary_embargo),
                    embargo_type    = validator.options_value (record, "embargo_type", validator.embargo_types),
                    embargo_title   = validator.string_value  (record, "embargo_title", 0, 1000),
                    embargo_reason  = validator.string_value  (record, "embargo_reason", 0, 10000, strip_html=False),
                    eula            = validator.string_value  (record, "eula", 0, 50000, strip_html=False),
                    defined_type_name = defined_type_name,
                    defined_type    = defined_type,
                    git_repository_name = validator.string_value  (record, "git_repository_name",  0, 255),
                    git_code_hosting_url = validator.string_value (record, "git_code_hosting_url",  0, 512),
                    agreed_to_deposit_agreement = validator.boolean_value (record, "agreed_to_deposit_agreement", False, False),
                    agreed_to_publish = validator.boolean_value (record, "agreed_to_publish", False, False),
                    categories      = validator.array_value   (record, "categories"),
                )

                if self.__is_reviewing (request):
                    try:
                        reviewer_account = self.db.account_by_session_token (self.__impersonator_token (request))
                        review = self.db.reviews (dataset_uri = dataset["uri"])[0]
                        if "assigned_to" not in review:
                            if self.db.update_review (dataset["review_uri"],
                                  author_account_uuid = dataset["account_uuid"],
                                  assigned_to = reviewer_account["uuid"],
                                  status      = "assigned"):
                                review["assigned_to"] = reviewer_account["uuid"]
                        assigned_uuid = uri_to_uuid (review["assigned_to"])
                        if reviewer_account["uuid"] == assigned_uuid:
                            self.db.dataset_update_seen_by_reviewer (dataset["uuid"])
                    except (TypeError, IndexError):
                        pass

                if not result:
                    return self.error_500()

                if value_or (dataset, "is_under_review", False):
                    self.db.cache.invalidate_by_prefix ("reviews")

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
                if self.db.delete_dataset_draft (container_uuid, dataset["uuid"], account_uuid, dataset["account_uuid"]):
                    return self.respond_204()
            except (IndexError, KeyError):
                pass

        return self.error_500 ()

    def __api_private_item_authors (self, request, item_type, item_id, item_by_id_procedure):
        """Implements /v2/account/[item]/<id>/authors."""
        account_uuid = self.default_authenticated_error_handling (request,
                                                                  ["GET", "POST", "PUT"],
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        if request.method in ("GET", "HEAD"):
            try:
                item = item_by_id_procedure (item_id,
                                             account_uuid=account_uuid,
                                             is_published=False)

                _, error_response = self.__needs_collaborative_permissions (
                    account_uuid, request, item_type, item, "metadata_read")
                if error_response is not None:
                    return error_response

                authors = self.db.authors (
                    item_uri     = item["uri"],
                    account_uuid = account_uuid,
                    is_published = False,
                    item_type    = item_type,
                    limit        = validator.integer_value (request.args, "limit"),
                    order        = validator.string_value (request.args, "order", 0, 32),
                    order_direction = validator.order_direction (request.args, "order_direction"))

                return self.default_list_response (authors, formatter.format_author_record)
            except (IndexError, KeyError, TypeError) as error:
                self.log.error ("Unable to retrieve authors: %s", error)
            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

            return self.error_500 ()

        if request.method in ('POST', 'PUT'):
            ## The 'parameters' will be a dictionary containing a key "authors",
            ## which can contain multiple dictionaries of author records.
            parameters = request.get_json()

            try:
                item = item_by_id_procedure (item_id,
                                             account_uuid=account_uuid,
                                             is_published=False)

                if item is None:
                    return self.error_403 (request, (f"account:{account_uuid} attempted to "
                                                     f"modify authors on {item_type}:{item_id}."))

                _, error_response = self.__needs_collaborative_permissions (
                    account_uuid, request, item_type, item, "metadata_edit")
                if error_response is not None:
                    return error_response

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
                            orcid_id   = validator.string_value  (record, "orcid_id",   0, 38,         False),
                            job_title  = validator.string_value  (record, "job_title",  0, 255,        False),
                            is_active  = False,
                            is_public  = True,
                            created_by = account_uuid)
                        if author_uuid is None:
                            return self.error_500 ("Adding a single author failed.")
                    new_authors.append(URIRef(uuid_to_uri (author_uuid, "author")))

                # The PUT method overwrites the existing authors, so we can
                # keep an empty starting list. For POST we must retrieve the
                # existing authors to preserve them.
                existing_authors = []
                if request.method == 'POST':
                    existing_authors = self.db.authors (
                        item_uri     = item["uri"],
                        account_uuid   = account_uuid,
                        item_type    = item_type,
                        is_published = False,
                        limit        = 10000)

                    existing_authors = list(map (lambda item: URIRef(uuid_to_uri(item["uuid"], "author")),
                                                 existing_authors))

                authors = existing_authors + new_authors
                if not self.db.update_item_list (item["uuid"], account_uuid,
                                                 authors, "authors"):
                    return self.error_500 ("Adding a single author failed.")

                return self.respond_205()

            except KeyError:
                return self.error_400 (request, "Expected an 'authors' field.", "NoAuthorsField")
            except IndexError:
                return self.error_500 ()
            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

        return self.error_500 ()

    def api_private_dataset_authors (self, request, dataset_id):
        """Implements /v2/account/articles/<id>/authors."""
        return self.__api_private_item_authors (request, "dataset", dataset_id,
                                                self.__dataset_by_id_or_uri)

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
                return self.error_403 (request, (f"account:{account_uuid} attempted to "
                                                 f"remove author on dataset:{dataset_id}."))

            _, error_response = self.__needs_collaborative_permissions (
                account_uuid, request, "dataset", dataset, "metadata_edit")
            if error_response is not None:
                return error_response

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
            if self.db.update_item_list (dataset["uuid"], account_uuid, authors, "authors"):
                return self.respond_204()

            return self.error_500()
        except (IndexError, KeyError):
            return self.error_500 ()

    def __api_private_item_funding (self, request, item_id, item_type,
                                    item_by_id_procedure):
        """Implements handling funding for both datasets and collections."""

        account_uuid = self.default_authenticated_error_handling (request,
                                                                  ["GET", "POST", "PUT"],
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        if request.method in ("GET", "HEAD"):
            try:
                item = item_by_id_procedure (item_id,
                                             account_uuid=account_uuid,
                                             is_published=False)

                if item is None:
                    return self.error_403 (request, (f"account:{account_uuid} attempted to "
                                                     f"view funding of {item_type}:{item_id}."))

                _, error_response = self.__needs_collaborative_permissions (
                    account_uuid, request, item_type, item, "metadata_read")
                if error_response is not None:
                    return error_response

                funding = self.db.fundings (item_uri     = item["uri"],
                                            account_uuid = account_uuid,
                                            is_published = False,
                                            item_type    = item_type,
                                            limit        = 10000)

                return self.default_list_response (funding, formatter.format_funding_record)
            except (IndexError, KeyError, TypeError):
                pass

            return self.error_500 ()

        if request.method in ('POST', 'PUT'):
            ## The 'parameters' will be a dictionary containing a key "funders",
            ## which can contain multiple dictionaries of funding records.
            parameters = request.get_json()

            try:
                item = item_by_id_procedure (item_id,
                                             account_uuid=account_uuid,
                                             is_published=False)

                if item is None:
                    return self.error_403 (request, (f"account:{account_uuid} attempted to "
                                                     f"modify funding of {item_type}:{item_id}."))

                _, error_response = self.__needs_collaborative_permissions (
                    account_uuid, request, item_type, item, "metadata_edit")
                if error_response is not None:
                    return error_response

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
                            return self.error_500 ("Adding a single funder failed.")
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
                if not self.db.update_item_list (item["uuid"], account_uuid,
                                                 fundings, "funding_list"):
                    return self.error_500 ("Adding a single funder failed.")

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
                return self.error_403 (request, (f"account:{account_uuid} attempted to "
                                                 f"remove funding of {item_type}:{item_id}."))

            _, error_response = self.__needs_collaborative_permissions (
                account_uuid, request, item_type, item, "metadata_edit")
            if error_response is not None:
                return error_response

            fundings = self.db.fundings (item_uri     = item["uri"],
                                         account_uuid = account_uuid,
                                         is_published = False,
                                         item_type    = item_type,
                                         limit        = 10000)
            if not fundings:
                return self.error_404 (request)

            fundings.remove (next (filter (lambda item: item['uuid'] == funding_id, fundings)))

            fundings = list(map (lambda item: URIRef(uuid_to_uri(item["uuid"], "funding")), fundings))
            if self.db.update_item_list (item["uuid"], account_uuid,
                                         fundings, "funding_list"):
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
                return self.error_403 (request, (f"account:{account_uuid} attempted "
                                                 f"to remove author:{author_id} "
                                                 f"from collection:{collection_id}."))

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

            if self.db.update_item_list (collection["uuid"], account_uuid,
                                         authors, "authors"):
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

            if self.db.delete_item_from_list (collection["uri"], "datasets",
                                              dataset["container_uri"]):
                self.db.cache.invalidate_by_prefix ("datasets")
                return self.respond_204()

            self.log.error ("Failed to delete dataset %s from collection %s.",
                            dataset_id, collection_id)
        except (IndexError, KeyError) as error:
            self.log.error ("Failed to delete dataset from collection: %s", error)

        return self.error_403 (request, (f"account:{account_uuid} attempted to remove remove "
                                         f"dataset:{dataset_id} from collection:{collection_id}"))

    def __api_private_item_categories (self, request, item_type, item_id,
                                       item_by_id_procedure):
        """Implements /v2/account/[item]/<id>/categories."""
        account_uuid = self.default_authenticated_error_handling (request,
                                                                  ["GET", "POST", "PUT"],
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        if request.method in ("GET", "HEAD"):
            try:
                item       = item_by_id_procedure (item_id,
                                                   account_uuid=account_uuid,
                                                   is_published=False)
                categories = self.db.categories (item_uri   = item["uri"],
                                                 account_uuid = account_uuid,
                                                 is_published = False,
                                                 limit        = None)
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

                item = item_by_id_procedure (item_id,
                                             account_uuid = account_uuid,
                                             is_published = False)
                if item is None:
                    return self.error_404 (request)

                _, error_response = self.__needs_collaborative_permissions (
                    account_uuid, request, item_type, item, "metadata_edit")
                if error_response is not None:
                    return error_response

                # First, validate all values passed by the user.  This way, we
                # can be as certain as we can be that performing a PUT will not
                # end in having no categories associated with an item.
                for index, _ in enumerate(categories):
                    try:
                        categories[index] = validator.string_value (categories, index, 0, 36)
                    except validator.ValidationException:
                        category_id = validator.integer_value (categories, index)
                        category = self.db.category_by_id (category_id=category_id)
                        if category is not None:
                            categories[index] = category["uuid"]

                ## Append when using POST, otherwise overwrite.
                if request.method == 'POST':
                    existing_categories = self.db.categories (item_uri     = item["uri"],
                                                              account_uuid = account_uuid,
                                                              is_published = False,
                                                              limit        = None)

                    existing_categories = list(map(lambda category: category["uuid"], existing_categories))

                    # Merge and remove duplicates
                    categories = list(dict.fromkeys(existing_categories + categories))

                categories = uris_from_records (categories, "category")
                if self.db.update_item_list (item["uuid"], account_uuid,
                                             categories, "categories"):
                    return self.respond_205()

            except IndexError:
                return self.error_500 ()
            except KeyError:
                return self.error_400 (request, "Expected an array for 'categories'.", "NoCategoriesField")
            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

        return self.error_500 ()

    def api_private_dataset_categories (self, request, dataset_id):
        """Implements /v2/account/articles/<id>/categories."""
        return self.__api_private_item_categories (request, "dataset", dataset_id,
                                                   self.__dataset_by_id_or_uri)

    def __api_private_delete_item_category (self, request, item_type, item_id, category_id, item_by_id_procedure):
        """Implements /v2/account/[item]/<id>/categories/<cid>."""

        account_uuid = self.default_authenticated_error_handling (request, "DELETE",
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        try:
            item = item_by_id_procedure (item_id,
                                         account_uuid=account_uuid,
                                         is_published=False)

            if item is None:
                return self.error_403 (request, (f"account:{account_uuid} attempted "
                                                 f"to remove category:{category_id} "
                                                 f"from {item_type}:{item_id}."))

            _, error_response = self.__needs_collaborative_permissions (
                account_uuid, request, item_type, item, "metadata_edit")
            if error_response is not None:
                return error_response

            category = None
            if parses_to_int (category_id):
                category = self.db.category_by_id (category_id = category_id)
            elif validator.is_valid_uuid (category_id):
                category = self.db.category_by_id (category_uuid = category_id)

            if category is None:
                return self.error_403 (request, (f"account:{account_uuid} failed "
                                                 f"to remove category:{category_id} "
                                                 f"from {item_type}:{item_id}."))

            if self.db.delete_item_from_list (item["uri"], "categories",
                                              uuid_to_uri (category["uuid"], "category")):
                return self.respond_204()

            self.log.error ("Failed to delete category %s from %s %s.",
                            category_id, item_type, item_id)
        except (IndexError, KeyError, StopIteration):
            pass

        return self.error_500()

    def api_private_delete_dataset_category (self, request, dataset_id, category_id):
        """Implements /v2/account/articles/<id>/categories/<cid>."""
        return self.__api_private_delete_item_category (request, "dataset", dataset_id,
                                                        category_id, self.__dataset_by_id_or_uri)

    def api_private_dataset_embargo (self, request, dataset_id):
        """Implements /v2/account/articles/<id>/embargo."""

        account_uuid = self.default_authenticated_error_handling (request,
                                                                  ["GET", "DELETE"],
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        if request.method in ("GET", "HEAD"):
            dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                   account_uuid = account_uuid,
                                                   is_published = False)
            if not dataset:
                return self.response ("[]")

            _, error_response = self.__needs_collaborative_permissions (
                account_uuid, request, "dataset", dataset, "metadata_read")
            if error_response is not None:
                return error_response

            return self.response (json.dumps (formatter.format_dataset_embargo_record (dataset)))

        if request.method == 'DELETE':
            try:
                dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                       account_uuid = account_uuid,
                                                       is_published = False)

                _, error_response = self.__needs_collaborative_permissions (
                    account_uuid, request, "dataset", dataset, "metadata_edit")
                if error_response is not None:
                    return error_response

                if self.db.delete_dataset_embargo (dataset_uri = dataset["uri"],
                                                   account_uuid = account_uuid):
                    return self.respond_204()
            except (IndexError, KeyError):
                pass

        return self.error_500 ()

    def api_private_dataset_files (self, request, dataset_id):
        """Implements /v2/account/articles/<id>/files."""
        account_uuid = self.default_authenticated_error_handling (request,
                                                                  ["GET", "POST", "DELETE"],
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        if request.method in ("GET", "HEAD"):
            try:
                dataset       = self.__dataset_by_id_or_uri (dataset_id,
                                                             account_uuid=account_uuid,
                                                             is_published=False)
                if dataset is None:
                    return self.error_403 (request, (f"account:{account_uuid} attempted to "
                                                     f"view files of dataset:{dataset_id}."))

                _, error_response = self.__needs_collaborative_permissions (
                    account_uuid, request, "dataset", dataset, "data_read")
                if error_response is not None:
                    return error_response

                files = self.db.dataset_files (
                    dataset_uri = dataset["uri"],
                    account_uuid = account_uuid,
                    limit      = validator.integer_value (request.args, "limit"))

                return self.default_list_response (files, formatter.format_file_for_dataset_record,
                                                   base_url = config.base_url)

            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)
            except (IndexError, KeyError):
                pass

            return self.error_500 ()

        if request.method == 'DELETE':
            parameters = request.get_json()

            try:
                yesno = validator.boolean_value(parameters, "remove_all", when_none=False)

                if yesno is False:
                    self.log.error ("Failed to delete all files from dataset"
                                    " %s due to a missing parameter.",
                                    dataset_id)
                    return self.error_400 (request, "Expected a 'remove_all' field.", "400")

                dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                       account_uuid=account_uuid,
                                                       is_published=False)

                if dataset is None:
                    return self.error_403 (request, (f"account:{account_uuid} attempted to remove "
                                                     f"all files from dataset:{dataset_id}."))

                if self.db.delete_items_all_from_list (dataset["uri"], "files"):
                    self.db.cache.invalidate_by_prefix (f"{account_uuid}_storage")
                    self.db.cache.invalidate_by_prefix (f"{dataset['uuid']}_dataset_storage")
                    return self.respond_204()

                self.log.error ("Failed to delete all files from dataset %s.",
                                dataset_id)

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
                    return self.error_403 (request, (f"account:{account_uuid} attempted "
                                                     f"to add link to dataset:{dataset_id}."))

                _, error_response = self.__needs_collaborative_permissions (
                    account_uuid, request, "dataset", dataset, "data_edit")
                if error_response is not None:
                    return error_response

                if link is not None:
                    file_id = self.db.insert_file (
                        dataset_uri        = dataset["uri"],
                        account_uuid       = account_uuid,
                        is_link_only       = True,
                        download_url       = link)

                    if file_id is None:
                        return self.error_500()

                    return self.respond_201({
                        "location": f"{config.base_url}/v2/account/articles/{dataset_id}/files/{file_id}"
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
                    "location": f"{config.base_url}/v2/account/articles/{dataset_id}/files/{file_id}"
                })

            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)
            except (IndexError, KeyError):
                pass

        return self.error_500 ()

    def api_private_dataset_file_details (self, request, dataset_id, file_id):
        """Implements /v2/account/articles/<id>/files/<fid>."""
        account_uuid = self.default_authenticated_error_handling (request,
                                                                  ["GET", "POST", "DELETE"],
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        if request.method in ("GET", "HEAD"):
            try:
                dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                       account_uuid = account_uuid,
                                                       is_published = False)

                if dataset is None:
                    return self.error_404 (request)

                _, error_response = self.__needs_collaborative_permissions (
                    account_uuid, request, "dataset", dataset, "data_read")
                if error_response is not None:
                    return error_response

                metadata = self.__file_by_id_or_uri (file_id,
                                                     account_uuid = account_uuid,
                                                     dataset_uri = dataset["uri"])
                metadata["base_url"] = config.base_url
                return self.response (json.dumps (formatter.format_file_details_record (metadata)))
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
                    return self.error_403 (request, (f"account:{account_uuid} attempted "
                                                     f"to remove dataset:{dataset_id}."))

                _, error_response = self.__needs_collaborative_permissions (
                    account_uuid, request, "dataset", dataset, "data_remove")
                if error_response is not None:
                    return error_response

                metadata = self.__file_by_id_or_uri (file_id,
                                                     account_uuid = account_uuid,
                                                     dataset_uri = dataset["uri"])
                if metadata is None:
                    return self.error_404 (request)

                if self.db.delete_item_from_list (dataset["uri"], "files",
                                                  uuid_to_uri (metadata["uuid"], "file")):
                    self.db.cache.invalidate_by_prefix (f"{account_uuid}_storage")
                    self.db.cache.invalidate_by_prefix (f"{dataset['uuid']}_dataset_storage")
                    return self.respond_204()

                self.log.error ("Failed to delete file %s from dataset %s.",
                                file_id, dataset_id)

            except (IndexError, KeyError, StopIteration):
                pass

        return self.error_500 ()

    def api_private_dataset_private_links (self, request, dataset_id):
        """Implements /v2/account/articles/<id>/private_links."""

        account_uuid = self.default_authenticated_error_handling (request,
                                                                  ["GET", "POST"],
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        if request.method in ("GET", "HEAD"):

            dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                   account_uuid = account_uuid,
                                                   is_published = False)

            if dataset is None:
                return self.error_404 (request)

            if value_or (dataset, "is_shared_with_me", False):
                return self.error_403 (request, (f"collaborator account:{account_uuid} attempted "
                                                 f"to view private links on dataset:{dataset_id}."))

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

                if value_or (dataset, "is_shared_with_me", False):
                    return self.error_403 (request, (f"collaborator account:{account_uuid} "
                                                     "attempted to modify private links of "
                                                     f"dataset:{dataset_id}."))

                id_string = secrets.token_urlsafe()
                expires_date = validator.date_value (parameters, "expires_date", False)

                # expires_date validates to YYYY-MM-DD but we need a full timestamp.
                if expires_date:
                    expires_date = expires_date + "T00:00:00Z"

                link_uri  = self.db.insert_private_link (
                    dataset["uuid"],
                    account_uuid,
                    item_type    = "dataset",
                    expires_date = expires_date,
                    read_only    = validator.boolean_value (parameters, "read_only", False),
                    id_string    = id_string,
                    is_active    = True)

                if link_uri is None:
                    return self.error_500 (("Creating a private link failed for "
                                            f"{dataset['uuid']}"))

                links    = self.db.private_links (item_uri   = dataset["uri"],
                                                  account_uuid = account_uuid)
                links    = list(map (lambda item: URIRef(item["uri"]), links))
                links    = links + [ URIRef(link_uri) ]

                if not self.db.update_item_list (dataset["uuid"], account_uuid,
                                                 links, "private_links"):
                    return self.error_500 (("Updating private links failed for "
                                            f"{dataset['container_uuid']}."))

                return self.response(json.dumps({
                    "location": f"{config.base_url}/private_datasets/{id_string}"
                }))

            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

        return self.error_500 ()

    def api_private_dataset_private_links_details (self, request, dataset_id, link_id):
        """Implements /v2/account/articles/<id>/private_links/<link_id>."""

        account_uuid = self.default_authenticated_error_handling (request,
                                                                  ["GET", "PUT", "DELETE"],
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        dataset = self.__dataset_by_id_or_uri (dataset_id,
                                               account_uuid = account_uuid,
                                               is_published = False)

        if dataset is None:
            return self.error_404 (request)

        if request.method in ("GET", "HEAD"):

            if value_or (dataset, "is_shared_with_me", False):
                return self.error_403 (request, (f"collaborator account:{account_uuid} attempted "
                                                 f"to view a private link of dataset:{dataset_id}."))

            links = self.db.private_links (
                        item_uri   = dataset["uri"],
                        id_string  = link_id,
                        account_uuid = account_uuid)

            return self.default_list_response (links, formatter.format_private_links_record)

        if request.method == 'PUT':

            if value_or (dataset, "is_shared_with_me", False):
                return self.error_403 (request, (f"collaborator account:{account_uuid} attempted "
                                                 f"to modify a private link of dataset:{dataset_id}."))

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
                    "location": f"{config.base_url}/private_datasets/{link_id}"
                }))

            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

        if request.method == 'DELETE':

            if value_or (dataset, "is_shared_with_me", False):
                return self.error_403 (request, (f"collaborator account:{account_uuid} "
                                                 "attempted to remove a private link "
                                                 f"of dataset:{dataset_id}."))

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
        attributes = { "doi": doi } if doi else { "prefix": config.datacite_prefix }
        json_data = { "data": { "type": "dois", "attributes": attributes } }

        try:
            response = requests.post(f"{config.datacite_url}/dois",
                                     headers = headers,
                                     auth    = (config.datacite_id,
                                                config.datacite_password),
                                     timeout = 60,
                                     json    = json_data)
            data = None
            if response.status_code in (201, 422): #422:already reserved
                data = response.json()
            else:
                self.log.error ("DataCite responded with %s (%s)",
                                response.status_code, response.text)
            return data
        except requests.exceptions.ConnectionError:
            self.log.error ("Failed to reserve a DOI due to a connection error.")

        return None

    def api_private_collection_reserve_doi (self, request, collection_id):
        """Implements /v2/account/collections/<id>/reserve_doi."""

        account_uuid = self.default_authenticated_error_handling (request, "POST",
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        collection = self.__collection_by_id_or_uri (collection_id,
                                                     is_published = False,
                                                     account_uuid = account_uuid)
        if collection is None:
            return self.error_403 (request, (f"account:{account_uuid} attempted to reserve "
                                             f"DOI for collection:{collection_id}."))

        data = self.__datacite_reserve_doi (self.__standard_doi (collection_id))
        if data is None:
            return self.error_500 ()

        reserved_doi = data["data"]["id"]
        if self.db.update_collection (collection["uuid"],
                                      account_uuid,
                                      doi = reserved_doi):
            return self.response (json.dumps({ "doi": reserved_doi }))

        return self.error_500 ((f"Updating the collection {collection_id} for "
                                f"reserving DOI {reserved_doi} failed."))

    def __reserve_and_save_doi (self, account_uuid, item, version=None,
                                item_type="dataset"):
        """
        Returns the reserved DOI on success or False otherwise.
        version = None/<integer> reserves DOI for dataset/container.
        Trying to reserve an already reserved DOI just returns the DOI.
        """

        if item is None or account_uuid is None:
            return False

        container_uuid = item["container_uuid"]
        doi = self.__standard_doi (container_uuid, version,
                                   value_or_none (item, "container_doi"))
        if doi.split("/")[0] != config.datacite_prefix:
            self.log.error ("Doi %s of %s has wrong prefix", doi, container_uuid)
            return False

        data = self.__datacite_reserve_doi (doi)
        if value_or_none(data, 'errors'): # doi has already been reserved
            return doi
        if data is None:
            return False

        try:
            doi_type = "doi" if version else "container_doi"
            more_parm = {doi_type: doi,
                         "is_first_online": not "timeline_first_online" in item}
            if item_type == "dataset":
                if self.db.update_dataset (
                        item["uuid"],
                        account_uuid,
                        time_coverage               = value_or_none (item, "time_coverage"),
                        publisher                   = value_or_none (item, "publisher"),
                        mimetype                    = value_or_none (item, "format"),
                        contributors                = value_or_none (item, "contributors"),
                        geolocation                 = value_or_none (item, "geolocation"),
                        longitude                   = value_or_none (item, "longitude"),
                        latitude                    = value_or_none (item, "latitude"),
                        data_link                   = value_or_none (item, "data_link"),
                        same_as                     = value_or_none (item, "same_as"),
                        organizations               = value_or_none (item, "organizations"),
                        resource_title              = value_or_none (item, "resource_title"),
                        resource_doi                = value_or_none (item, "resource_doi"),
                        embargo_until_date          = value_or_none (item, "embargo_until_date"),
                        agreed_to_deposit_agreement = value_or (item, "agreed_to_deposit_agreement", False),
                        agreed_to_publish           = value_or (item, "agreed_to_publish", False),
                        is_metadata_record          = value_or (item, "is_metadata_record", False),
                        is_embargoed                = value_or (item, "is_embargoed", False),
                        is_restricted               = value_or (item, "is_restricted", False),
                        categories                  = None,
                        **more_parm ):
                    return doi
            else:
                if self.db.update_collection (item["uuid"], account_uuid, **more_parm):
                    return doi
        except KeyError:
            pass

        self.log.error ("Updating the %s %s for reserving DOI %s failed.",
                        item_type, item["container_uuid"], doi)

        return False

    def api_private_dataset_reserve_doi (self, request, dataset_id):
        """Implements /v2/account/articles/<id>/reserve_doi."""

        account_uuid = self.default_authenticated_error_handling (request, "POST",
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        dataset = self.__dataset_by_id_or_uri (dataset_id,
                                               is_published = False,
                                               account_uuid = account_uuid)

        if dataset is None:
            return self.error_403 (request, (f"account:{account_uuid} attempted to "
                                             f"reserve DOI for dataset:{dataset_id}."))

        _, error_response = self.__needs_collaborative_permissions (
            account_uuid, request, "dataset", dataset, "metadata_edit")
        if error_response is not None:
            return error_response

        reserved_doi = self.__reserve_and_save_doi (account_uuid, dataset)
        if reserved_doi:
            return self.response (json.dumps({ "doi": reserved_doi }))

        return self.error_500()

    def __update_item_doi (self, item_id, version=None, item_type="dataset", from_draft=True):
        """Procedure to modify metadata of an existing doi."""

        parameters = self.__metadata_export_parameters (item_id, version, item_type=item_type, from_draft=from_draft)
        xml = str(xml_formatter.datacite (parameters, indent=False), encoding='utf-8')
        xml = '<?xml version="1.0" encoding="UTF-8"?>' + xml.split('?>', 1)[1] #Datacite is very choosy about this
        doi = parameters["doi"]
        encoded_bytes = base64.b64encode(xml.encode("utf-8"))
        headers = {
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/vnd.api+json"
        }
        json_data = {
            "data": {
                "attributes": {
                    "event": "publish", #does no harm when already published
                    "url": landing_page_url(item_id, version, item_type=item_type, base_url=config.base_url),
                    "xml": str(encoded_bytes, "utf-8")
                }
            }
        }

        try:
            response = requests.put(f"{config.datacite_url}/dois/{doi}",
                                    headers = headers,
                                    auth    = (config.datacite_id,
                                               config.datacite_password),
                                    timeout = 60,
                                    json    = json_data)

            if response.status_code == 201:
                return True
            if response.status_code == 200:
                self.log.warning ("Doi %s already active, updated", doi)
                return True

            self.log.error ("DataCite responded with %s (%s)",
                            response.status_code, response.text)
        except requests.exceptions.ConnectionError:
            self.log.error ("Failed to update a DOI due to a connection error.")

        return False

    def api_private_datasets_search (self, request):
        """Implements /v2/account/articles/search."""
        account_uuid = self.default_authenticated_error_handling (request, "POST",
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

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
                search_for      = validator.string_value (parameters, "search_for", 0, 512, strip_html=False),
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

            return self.default_list_response (records, formatter.format_dataset_record,
                                               base_url = config.base_url)

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    ## ------------------------------------------------------------------------
    ## COLLECTIONS
    ## ------------------------------------------------------------------------

    def __default_collection_api_parameters (self, request):
        errors = []
        record = {
            "order":           validator.string_value  (self.get_parameter (request, "order"), None, maximum_length=32, error_list=errors),
            "order_direction": validator.order_direction (self.get_parameter (request, "order_direction"), None, error_list=errors),
            "institution":     validator.integer_value (self.get_parameter (request, "institution"), None, error_list=errors),
            "published_since": validator.string_value  (self.get_parameter (request, "published_since"), None, maximum_length=32, error_list=errors),
            "modified_since":  validator.string_value  (self.get_parameter (request, "modified_since"), None, maximum_length=32, error_list=errors),
            "group":           validator.integer_value (self.get_parameter (request, "group"), None, error_list=errors),
            "resource_doi":    validator.string_value  (self.get_parameter (request, "resource_doi"), None, maximum_length=255, error_list=errors),
            "doi":             validator.string_value  (self.get_parameter (request, "doi"), None, maximum_length=255, error_list=errors),
            "handle":          validator.string_value  (self.get_parameter (request, "handle"), None, maximum_length=255, error_list=errors),
            "is_latest":       True
        }

        offset, limit = self.__paging_offset_and_limit (request, error_list=errors)
        record["limit"] = limit
        record["offset"] = offset
        validator.order_direction (record, "order_direction", error_list=errors)
        return errors, record

    def api_collections (self, request):
        """Implements /v2/collections."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        errors, record = self.__default_collection_api_parameters (request)
        if errors:
            return self.error_400_list (request, errors)

        records = self.db.collections (**record)
        return self.default_list_response (records, formatter.format_collection_record,
                                           base_url = config.base_url)

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

        return self.default_list_response (records, formatter.format_collection_record,
                                           base_url = config.base_url)

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

        return self.default_list_response (versions, formatter.format_collection_version_record,
                                           base_url = config.base_url)

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
        """Implements /v2/account/collections."""

        account_uuid = self.default_authenticated_error_handling (request,
                                                                  ["GET", "POST"],
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        if request.method in ("GET", "HEAD"):
            errors, record = self.__default_collection_api_parameters (request)
            if errors:
                return self.error_400_list (request, errors)

            record["account_uuid"] = account_uuid
            record["is_latest"]    = None
            record["is_published"] = None
            records = self.db.collections (**record)
            return self.default_list_response (records, formatter.format_collection_record,
                                               base_url = config.base_url)

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
                    description             = validator.string_value  (record, "description",      0, 10000,      False, strip_html=False),
                    datasets                = validator.array_value   (record, "articles",                        False),
                    authors                 = validator.array_value   (record, "authors",                         False),
                    categories              = validator.array_value   (record, "categories",                      False),
                    categories_by_source_id = validator.array_value   (record, "categories_by_source_id",         False),
                    tags                    = validator.array_value   (record, "tags",                            False),
                    references              = validator.array_value   (record, "references",                      False),
                    custom_fields           = validator.object_value  (record, "custom_fields",                   False),
                    custom_fields_list      = validator.array_value   (record, "custom_fields_list",              False),
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
                    publisher_publication   = validator.string_value (timeline, "publisherPublication",           False),
                    submission              = validator.string_value (timeline, "submission",                     False),
                    posted                  = validator.string_value (timeline, "posted",                         False),
                    revision                = validator.string_value (timeline, "revision",                       False))

                if collection_id is None:
                    return self.error_500 ()

                return self.response(json.dumps({
                    "location": f"{config.base_url}/v2/account/collections/{collection_id}",
                    "warnings": []
                }))
            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

        return self.error_500 ()

    def api_private_collection_details (self, request, collection_id):
        """Implements /v2/account/collections/<id>."""

        account_uuid = self.default_authenticated_error_handling (request,
                                                                  ["GET", "PUT", "DELETE"],
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        if request.method in ("GET", "HEAD"):
            try:
                collection    = self.__collection_by_id_or_uri (collection_id,
                                                                account_uuid = account_uuid,
                                                                is_published = False)
                if collection is None:
                    return self.error_403 (request, (f"account:{account_uuid} attempted "
                                                     f"to view collection:{collection_id}."))

                collection["doi"] = self.__standard_doi (collection["container_uuid"],
                                                         version = None,
                                                         container_doi = value_or_none (collection, "container_doi"))
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
                collection = self.__collection_by_id_or_uri (collection_id,
                                                             account_uuid = account_uuid,
                                                             is_published = False)
                if collection is None:
                    return self.error_404 (request)

                result = self.db.update_collection (collection["uuid"], account_uuid,
                    title           = validator.string_value  (record, "title",          3, 1000),
                    description     = validator.string_value  (record, "description",    0, 10000, strip_html=False),
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
                    organizations   = validator.string_value  (record, "organizations",  0, 2048),
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

        account_uuid = self.default_authenticated_error_handling (request, "POST",
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        record = request.get_json()
        errors = []
        parameters = {
            "resource_doi"    : validator.string_value (record, "resource_doi", 0, 255, error_list=errors),
            "resource_id"     : validator.integer_value (record, "resource_id", error_list=errors),
            "doi"             : validator.string_value (record, "doi", 0, 255, error_list=errors),
            "handle"          : validator.string_value (record, "handle", 0, 255, error_list=errors),
            "order"           : validator.string_value (record, "order", 0, 255, error_list=errors),
            "search_for"      : validator.string_value (record, "search_for", maximum_length=1024, strip_html=False, error_list=errors),
            "order_direction" : validator.order_direction (record, "order_direction", error_list=errors),
            "institution"     : validator.integer_value (record, "institution", error_list=errors),
            "published_since" : validator.string_value (record, "published_since", 0, 255, error_list=errors),
            "modified_since"  : validator.string_value (record, "modified_since", 0, 255, error_list=errors),
            "group"           : validator.integer_value (record, "group", error_list=errors),
            "account_uuid"    : account_uuid,
            "is_published"    : None,
            "is_latest"       : None
        }
        offset, limit = self.__paging_offset_and_limit (record, error_list=errors)
        if errors:
            return self.error_400_list (request, errors)

        parameters["offset"] = offset
        parameters["limit"]  = limit
        records = self.db.collections(**parameters)
        return self.default_list_response (records, formatter.format_collection_record,
                                           base_url = config.base_url)

    def api_private_collection_authors (self, request, collection_id):
        """Implements /v2/account/collections/<id>/authors."""
        return self.__api_private_item_authors (request, "collection", collection_id,
                                                self.__collection_by_id_or_uri)

    def api_private_collection_categories (self, request, collection_id):
        """Implements /v2/account/collections/<id>/categories."""
        return self.__api_private_item_categories (request, "collection", collection_id,
                                                   self.__collection_by_id_or_uri)

    def api_private_delete_collection_category (self, request, collection_id, category_id):
        """Implements /v2/account/collections/<id>/categories/<cid>."""
        return self.__api_private_delete_item_category (request, "collection", collection_id,
                                                        category_id, self.__collection_by_id_or_uri)

    def api_private_collection_datasets (self, request, collection_id):
        """Implements /v2/account/collections/<id>/articles."""

        account_uuid = self.default_authenticated_error_handling (request,
                                                                  ["GET", "POST", "PUT"],
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        if request.method in ("GET", "HEAD"):
            try:
                collection = self.__collection_by_id_or_uri (collection_id,
                                                             is_published = False,
                                                             account_uuid = account_uuid)

                if collection is None:
                    return self.error_404 (request)

                offset, limit = self.__paging_offset_and_limit (request)
                datasets = self.db.datasets (collection_uri = collection["uri"],
                                             is_latest      = True,
                                             limit          = limit,
                                             offset         = offset)

                return self.default_list_response (datasets, formatter.format_dataset_record,
                                                   base_url = config.base_url)
            except (IndexError, KeyError):
                pass
            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

            return self.error_500 ()

        if request.method in ('PUT', 'POST'):
            try:
                parameters = request.get_json()
                collection = self.__collection_by_id_or_uri (collection_id, is_published=False, account_uuid=account_uuid)

                if collection is None:
                    # Attempt to automatically create draft for published collection.
                    collection = self.__collection_by_id_or_uri (collection_id,
                                                                 is_published = True,
                                                                 account_uuid = account_uuid)
                    if collection is None:
                        return self.error_404 (request)

                    container_uuid = collection["container_uuid"]
                    draft_uuid = self.db.create_draft_from_published_collection (container_uuid)
                    if draft_uuid is None:
                        return self.error_404 (request)

                    collection = self.__collection_by_id_or_uri (container_uuid,
                                                                 is_published = False,
                                                                 account_uuid = account_uuid)

                if collection is None:
                    return self.error_404 (request)

                existing_datasets = []
                if request.method == "POST":
                    existing_datasets = self.db.datasets(collection_uri=collection["uri"],
                                                         is_latest=True,
                                                         limit=10000)
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

                if self.db.update_item_list (collection["uuid"], account_uuid,
                                             datasets, "datasets"):
                    self.db.cache.invalidate_by_prefix ("datasets")
                    return self.respond_205()

            except (IndexError, TypeError):
                return self.error_500 ()
            except KeyError:
                return self.error_400 (request, "Expected an array for 'articles'.", "NoArticlesField")
            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

            return self.error_500()

        return self.error_500 ()

    def api_collection_datasets (self, request, collection_id):
        """Implements /v2/collections/<id>/articles."""
        handler = self.default_error_handling (request, "GET", "application/json")
        if handler is not None:
            return handler

        try:
            collection = self.__collection_by_id_or_uri (collection_id, is_latest=True)
            if collection is None:
                return self.error_404 (request)

            offset, limit = self.__paging_offset_and_limit (request)
            datasets      = self.db.datasets (collection_uri = collection["uri"],
                                              limit          = limit,
                                              offset         = offset,
                                              is_latest      = True)
            return self.default_list_response (datasets, formatter.format_dataset_record,
                                               base_url = config.base_url)
        except (IndexError, KeyError):
            pass
        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

        return self.error_500 ()

    def api_private_authors_search (self, request):
        """Implements /v2/account/authors/search."""

        account_uuid = self.default_authenticated_error_handling (request, "POST",
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

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
        handler = self.default_authenticated_error_handling (request, "GET", "application/json",
                                                             self.db.may_administer)
        if isinstance (handler, Response):
            return handler

        try:
            author = None
            if parses_to_int (author_id):
                author = self.db.authors(author_id=int(author_id))[0]
            else:
                if not validator.is_valid_uuid (author_id):
                    return self.error_404 (request)
                author = self.db.authors(author_uuid = author_id)[0]

            if author is None:
                return self.error_404 (request)

            return self.response (json.dumps (formatter.format_author_details_record (author)))
        except IndexError:
            pass

        return self.error_403 (request)

    def api_private_funding_search (self, request):
        """Implements /v2/account/funding/search."""
        account_uuid = self.default_authenticated_error_handling (request, "POST",
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

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

        errors = []
        record = {
            "categories":   validator.string_value  (self.get_parameter (request, "categories"), None, maximum_length=512, error_list=errors),
            "doi":          validator.string_value  (self.get_parameter (request, "doi"), None, maximum_length=255, error_list=errors),
            #"group":        validator.integer_value (self.get_parameter (request, "group"), None, error_list=errors),
            "groups":       validator.string_value  (self.get_parameter (request, "group_ids"), None, maximum_length=512, error_list=errors),
            "handle":       validator.string_value  (self.get_parameter (request, "handle"), None, maximum_length=255, error_list=errors),
            "institution":  validator.integer_value (self.get_parameter (request, "institution"), None, error_list=errors),
            "item_type":    validator.integer_value (self.get_parameter (request, "item_type"), None, error_list=errors),
            "limit":        validator.integer_value (self.get_parameter (request, "limit"), None, error_list=errors),
            "modified_since": validator.string_value (self.get_parameter (request, "modified_since"), None, maximum_length=32, error_list=errors),
            "offset":       validator.integer_value (self.get_parameter (request, "offset"), None, error_list=errors),
            "order":        validator.string_value  (self.get_parameter (request, "order"), None, maximum_length=32, error_list=errors),
            "order_direction": validator.order_direction (self.get_parameter (request, "order_direction"), None, error_list=errors),
            "published_since": validator.string_value (self.get_parameter (request, "published_since"), None, maximum_length=32, error_list=errors),
            "resource_doi": validator.string_value  (self.get_parameter (request, "resource_doi"), None, maximum_length=255, error_list=errors),
            "return_count": validator.boolean_value (self.get_parameter (request, "return_count"), None, error_list=errors),
        }

        record["categories"] = split_string (record["categories"], delimiter=",")
        if record["categories"] is not None:
            for index, _ in enumerate(record["categories"]):
                record["categories"][index] = validator.integer_value (record["categories"], index, error_list=errors)

        record["groups"]  = split_string (record["groups"], delimiter=",")
        if record["groups"] is not None:
            for index, _ in enumerate(record["groups"]):
                record["groups"][index] = validator.integer_value (record["groups"], index, error_list=errors)

        if errors:
            return self.error_400_list (request, errors)

        records = self.db.datasets (**record)
        if record["return_count"]:
            return self.response (json.dumps(records[0]))

        return self.default_list_response (records, formatter.format_dataset_record,
                                           base_url = config.base_url)

    def api_v3_dataset_authors (self, request, container_uuid, author_uuid=None):
        """Implements /v3/datasets/<uuid>/authors[/<author_uuid>]."""

        if not validator.is_valid_uuid (container_uuid):
            return self.error_404 (request)

        if author_uuid is not None and not validator.is_valid_uuid (container_uuid):
            return self.error_404 (request)

        account_uuid = self.default_authenticated_error_handling (request, "GET",
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        order = validator.string_value (request.args, "order", 0, 32)
        if order is None:
            order = "order_index"

        order_direction = validator.order_direction (request.args, "order_direction")
        if order_direction is None:
            order_direction = "asc"

        try:
            dataset = self.db.datasets (container_uuid = container_uuid,
                                        account_uuid   = account_uuid,
                                        is_published   = False,
                                        is_latest      = False,
                                        limit          = 1)[0]

            _, error_response = self.__needs_collaborative_permissions (
                account_uuid, request, "dataset", dataset, "metadata_read")
            if error_response is not None:
                return error_response

            authors = self.db.authors (
                item_uri     = dataset["uri"],
                account_uuid = account_uuid,
                author_uuid  = author_uuid,
                is_published = False,
                item_type    = "dataset",
                limit        = validator.integer_value (request.args, "limit"),
                order        = order,
                order_direction = order_direction)

            if author_uuid is not None:
                return self.response (json.dumps(formatter.format_author_record_v3 (authors[0])))

            return self.default_list_response (authors, formatter.format_author_record_v3)
        except (IndexError, KeyError, TypeError) as error:
            self.log.error ("Unable to retrieve authors: %s", error)

        return self.error_500 ()

    def api_v3_author_details (self, request, author_uuid):
        """Implements /v3/authors/<author_uuid>."""

        if not validator.is_valid_uuid (author_uuid):
            return self.error_404 (request)

        account_uuid = self.default_authenticated_error_handling (request,
                                                                  ["GET", "PUT"],
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        if request.method in  ("GET", "HEAD"):
            try:
                author = self.db.authors (author_uuid = author_uuid)[0]
                if author is None:
                    return self.error_404 (request)
                return self.response (json.dumps(formatter.format_author_record_v3 (author)))
            except IndexError:
                return self.error_404 (request)

        if request.method == "PUT":
            record = request.get_json()
            try:
                parameters = {
                    "first_name": validator.string_value (record, "first_name", 0, 255),
                    "last_name":  validator.string_value (record, "last_name", 0, 255),
                    "email":      validator.string_value (record, "email", 0, 255),
                    "orcid":      validator.string_value (record, "orcid", 0, 255)
                }

                if not self.db.update_author (author_uuid, account_uuid, **parameters):
                    return self.error_500 ()

                return self.respond_204 ()

            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

        return self.error_405 (["GET", "PUT"])

    def __reorder_authors_for_item (self, request, container_uuid):
        """Generalization for api_v3_[datasets|collections]_authors_reorder."""

        if not validator.is_valid_uuid (container_uuid):
            return self.error_404 (request)

        account_uuid = self.default_authenticated_error_handling (request, "POST",
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        parameters  = request.get_json()
        errors      = []
        direction   = validator.options_value (parameters, "direction", ["up", "down"],
                                               required=True, error_list=errors)
        author_uuid = validator.string_value (parameters, "author", required=True,
                                              error_list=errors)
        if not validator.is_valid_uuid (author_uuid):
            errors.append({ "field_name": "author", "message": "Author should be a valid UUID."})

        if errors:
            return self.error_400_list (request, errors)

        if self.db.reorder_authors (account_uuid, container_uuid, author_uuid, direction):
            return self.respond_205()

        return self.error_500()

    def api_v3_datasets_authors_reorder (self, request, container_uuid):
        """Implements /v3/datasets/<uuid>/reorder-authors."""
        return self.__reorder_authors_for_item (request, container_uuid)

    def api_v3_collections_authors_reorder (self, request, container_uuid):
        """Implements /v3/datasets/<uuid>/reorder-authors."""
        return self.__reorder_authors_for_item (request, container_uuid)

    def api_v3_datasets_codemeta (self, request):
        """Implements /v3/datasets/codemeta."""

        try:
            errors          = []
            offset, limit   = self.__paging_offset_and_limit (request, error_list=errors)
            modified_since  = validator.string_value (request.args, "modified_since", 0, 32, False, error_list=errors)
            order           = validator.string_value (request.args, "order", 0, 255, False, error_list=errors)
            order_direction = validator.order_direction (request.args, "order_direction", False, error_list=errors)
            if errors:
                return self.error_400_list (request, errors)

            datasets = self.db.datasets (is_published = True,
                                         is_latest    = True,
                                         is_software  = True,
                                         is_embargoed = False,
                                         is_restricted = False,
                                         modified_since = modified_since,
                                         order        = order,
                                         order_direction = order_direction,
                                         limit        = limit,
                                         offset       = offset)

            output = []
            for dataset in datasets:
                output.append (formatter.format_codemeta_record (
                    dataset,
                    git_url = self.__git_repository_url_for_dataset (dataset),
                    tags = self.db.tags(item_uri=dataset["uri"], limit=None),
                    authors = self.db.authors (item_uri=dataset["uri"],
                                               is_published = True,
                                               item_type = "dataset",
                                               limit = 10000),
                    base_url = config.base_url))
            return self.response (json.dumps(output))
        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    def api_v3_datasets_search (self, request):
        """Implements /v3/datasets/search."""
        handler = self.default_error_handling (request, "POST", "application/json")
        if handler is not None:
            return handler

        parameters = request.get_json()
        try:
            record = {
                "categories":      value_or_none (parameters, "categories"),
                "doi":             validator.string_value   (parameters, "doi",        maximum_length=255),
                "groups":          value_or_none (parameters, "groups"),
                "handle":          validator.string_value   (parameters, "handle",     maximum_length=255),
                "institution":     validator.integer_value  (parameters, "institution"),
                "is_latest":       validator.boolean_value  (parameters, "is_latest"),
                "item_type":       validator.integer_value  (parameters, "item_type"),
                "licenses":        value_or_none (parameters, "licenses"),
                "modified_since":  validator.string_value   (parameters, "modified_since", maximum_length=32),
                "order":           validator.string_value   (parameters, "order", 0, 32),
                "order_direction": validator.order_direction (parameters, "order_direction"),
                "organizations":   validator.string_value (parameters, "organizations", maximum_length=255),
                "published_since": validator.string_value   (parameters, "published_since", maximum_length=32),
                "resource_doi":    validator.string_value   (parameters, "resource_doi", maximum_length=255),
                "search_for":      validator.string_value   (parameters, "search_for", maximum_length=1024, strip_html=False),
                "search_format":   value_or_none (parameters, "search_format")
            }

            offset, limit = self.__paging_offset_and_limit (parameters)
            record["offset"] = offset
            record["limit"]  = limit
            search_operator  = value_or_none (parameters, "search_operator")
            search_scope     = value_or_none (parameters, "search_scope")

            if record["groups"] is not None:
                validator.array_value    (record, "groups")
                for index, _ in enumerate(record["groups"]):
                    record["groups"][index] = validator.integer_value (record["groups"], index)

            if record["search_format"] is not None:
                record["search_format"] = validator.search_filters({"format": record["search_format"]})

            if search_operator is not None:
                search_operator = validator.search_filters({"operator": search_operator})

            if search_scope is not None:
                search_scope = validator.search_filters({"scope": search_scope})

            if record["search_for"] is not None:
                record["search_for_raw"] = html_to_plaintext (record["search_for"])
                search_tokens = re.findall(r'[^" ]+|"[^"]+"|\([^)]+\)', record["search_for"])
                search_tokens = [s.strip('"') for s in search_tokens]
                record["search_for"] = { "operator": search_operator,
                                         "search_for": search_tokens,
                                         "scope": search_scope}

            if record["licenses"] is not None:
                validator.array_value    (record, "licenses")
                for index, _ in enumerate(record["licenses"]):
                    record["licenses"][index] = validator.string_value (record["licenses"], index, maximum_length=255)

            if record["categories"] is not None:
                validator.array_value    (record, "categories")
                for index, _ in enumerate(record["categories"]):
                    record["categories"][index] = validator.integer_value (record["categories"], index)

            records = self.db.datasets (**record)
            return self.default_list_response (records, formatter.format_dataset_record,
                                               base_url = config.base_url)

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    def __api_v3_datasets_parameters (self, request, item_type):
        record = {
            "dataset_id": validator.integer_value (self.get_parameter (request, "id"), None),
            "limit":      validator.integer_value (self.get_parameter (request, "limit"), None),
            "offset":     validator.integer_value (self.get_parameter (request, "offset"), None),
            "order":      validator.string_value  (self.get_parameter (request, "order"), None, maximum_length=32),
            "order_direction": validator.order_direction (self.get_parameter (request, "order_direction"), None),
            "categories": validator.string_value  (self.get_parameter (request, "categories"), None, maximum_length=512),
            "group_ids":  validator.string_value  (self.get_parameter (request, "group_ids"), None, maximum_length=512),
        }

        if item_type not in {"downloads", "views", "shares", "cites"}:
            raise validator.InvalidValue(
                field_name = "item_type",
                message = ("The last URL parameter must be one of "
                           "'downloads', 'views', 'shares' or 'cites'."),
                code    = "InvalidURLParameterValue")

        record["categories"] = split_string (record["categories"], delimiter=",")
        if record["categories"] is not None:
            for index, _ in enumerate(record["categories"]):
                record["categories"][index] = validator.integer_value (record["categories"], index)

        record["group_ids"]  = split_string (record["group_ids"], delimiter=",")
        if record["group_ids"] is not None:
            for index, _ in enumerate(record["group_ids"]):
                record["group_ids"][index] = validator.integer_value (record["group_ids"], index)

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

        offset, limit = self.__paging_offset_and_limit (request)
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

    def __git_repository_default_branch_guess (self, git_repository):
        """Guess the default branch name for a Git repository."""

        branch_name = None
        # Get a previously set default.
        head_reference = git_repository.references.get("HEAD")
        try:
            head_reference = head_reference.resolve()
        except pygit2.GitError as error:  # pylint: disable=no-member
            self.log.error ("Failed to resolve git repository HEAD for '%s': %s",
                            git_repository.path, error)
            head_reference = None
        except KeyError as error:
            self.log.error ("HEAD points to non-existing branch for '%s': %s",
                            git_repository.path, error)
            head_reference = None

        if head_reference is not None:
            try:
                name = head_reference.name
                if name.startswith ("refs/heads/"):
                    branch_name = name[11:]
            except AttributeError:
                pass

        # Guess and set a new default.
        if branch_name is None:
            branches = list(git_repository.branches.local)
            if branches:
                branch_name = branches[0]
                if "master" in branches:
                    branch_name = "master"
                elif "main" in branches:
                    branch_name = "main"
            self.__git_set_default_branch (git_repository, branch_name)

        return branch_name

    def __git_repository_by_dataset_id (self, account_uuid, dataset_id, action="read"):
        """Deduplication for api_v3_datasets_git_[branches|files]."""

        dataset = self.__dataset_by_id_or_uri (dataset_id,
                                               account_uuid = account_uuid,
                                               is_published = False)

        if dataset is None:
            self.log.error ("No Git repository for dataset %s.", dataset_id)
            return None

        _, error_response = self.__needs_collaborative_permissions (
            account_uuid, None, "dataset", dataset, f"data_{action}")
        if error_response is not None:
            return None

        # Pre-Djehuty datasets may not have a Git UUID. We therefore
        # assign one when needed.
        if "git_uuid" not in dataset:
            if not self.__add_or_update_git_uuid_for_dataset (dataset, account_uuid):
                self.log.error ("Failed to add 'git_uuid' for dataset.")
                return None

        git_directory = os.path.join (config.storage, f"{dataset['git_uuid']}.git")
        if not os.path.exists (git_directory):
            self.log.error ("No Git repository at '%s'", git_directory)
            return None

        return pygit2.Repository(git_directory)

    def __git_set_default_branch (self, git_repository, branch_name):
        """Sets the default branch for a git repository."""

        if branch_name is None:
            return False

        try:
            git_repository.set_head (f"refs/heads/{branch_name}")
            git_repository.references.compress()
            self.log.info ("Set default branch to '%s' for %s.",
                           branch_name, git_repository.path)
            return True
        # It seems the way pygit2 loads internally trips up pylint.
        except pygit2.GitError as error:  # pylint: disable=no-member
            self.log.error ("Failed to set default branch to '%s' for '%s' due to: '%s'.",
                            branch_name, git_repository.path, error)

        return False

    def api_v3_datasets_git_set_default_branch (self, request, dataset_id):
        """Implements /v3/datasets/<id>.git/set-default-branch."""
        if request.method != "PUT":
            return self.error_405 ("PUT")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        branch_name = None
        try:
            record = request.get_json()
            branch_name = validator.string_value (record, "branch", 0, 255, True)
        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

        git_repository = self.__git_repository_by_dataset_id (account_uuid, dataset_id, "edit")
        if git_repository is None:
            return self.error_404 (request)

        if self.__git_set_default_branch (git_repository, branch_name):
            return self.respond_204 ()

        return self.error_500 ()

    def api_v3_dataset_git_branches (self, request, dataset_id):
        """Implements /v3/datasets/<id>.git/branches."""
        if request.method != "GET":
            return self.error_405 ("GET")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        git_repository = self.__git_repository_by_dataset_id (account_uuid, dataset_id, "read")
        if git_repository is None:
            return self.error_404 (request)

        branches = list(git_repository.branches.local)
        default_branch = self.__git_repository_default_branch_guess (git_repository)
        return self.response (json.dumps ({
            "default-branch": default_branch,
            "branches":       branches
        }))

    def api_v3_dataset_git_files (self, request, dataset_id):
        """Implements /v3/datasets/<id>.git/files."""
        if request.method != "GET":
            return self.error_405 ("GET")

        account_uuid = self.account_uuid_from_request (request)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        git_repository = self.__git_repository_by_dataset_id (account_uuid, dataset_id, "read")
        if git_repository is None:
            return self.error_404 (request)

        branch_name    = self.__git_repository_default_branch_guess (git_repository)
        files = []
        if branch_name:
            try:
                files = git_repository.revparse_single(branch_name).tree
                files = [e.name for e in files]
            except pygit2.GitError as error:  # pylint: disable=no-member
                return self.error_500 (("Failed to retrieve Git files for branch "
                                        f"'{branch_name}' in '{git_repository.path}' "
                                        f"due to: '{error}'."))

        return self.response (json.dumps(files))


    def __git_files_for_zipfly (self, filesystem_path, tree, path=""):
        file_paths = []
        for entry in tree:
            # Walk the directory tree
            if isinstance (entry, pygit2.Tree):  # pylint: disable=no-member
                file_paths += self.__git_files_for_zipfly (filesystem_path, list(entry),
                                                           f"{path}{entry.name}/")
                continue

            # Submodules are represented as commits.
            if isinstance (entry, pygit2.Commit):  # pylint: disable=no-member
                continue

            relative_path = f"{path}{entry.name}"
            # The path separator is under our own control, don't use os.path.join here.
            absolute_path = f"{filesystem_path}/{relative_path}"
            record = { "fs": absolute_path, "n": relative_path }
            file_paths.append (record)

        return file_paths

    def api_v3_dataset_git_zip (self, request, git_uuid):
        """Implements /v3/datasets/<git_uuid>.git/zip."""

        git_repository, branch = self.__git_statistics_error_handling (request, git_uuid)
        if isinstance (git_repository, Response):
            return git_repository

        if branch is None:
            self.log.audit ("NoGitBranch error occurred for %s.", git_uuid)
            return self.error_400 (request, "No default branch found.", "NoGitBranch")

        with tempfile.TemporaryDirectory(dir = self.db.cache.storage,
                                         prefix = "git-zip-",
                                         delete = False) as folder:
            git_directory  = os.path.join (config.storage, f"{git_uuid}.git")
            git_cloned     = pygit2.clone_repository (git_directory, folder)

            if not isinstance (git_cloned, pygit2.Repository):
                return self.error_500 (f"Unable to clone {git_directory}.")

            tree = git_repository.revparse_single(branch).tree # pylint: disable=no-member
            files  = self.__git_files_for_zipfly (folder, tree)
            writer = None
            try:
                zipfly_object = zipfly.ZipFly(paths = files)
                writer = zipfly_object.generator()
            except TypeError:
                return self.error_500 (f"Could not ZIP files for git repository {git_uuid}.")

            response = self.response (writer, mimetype="application/zip")
            response.headers["Content-disposition"] = f"attachment; filename={git_uuid}.zip"

            # Removes the temporary cloned repository. This should only be
            # done after the request is complete.
            response.call_on_close (lambda: shutil.rmtree (folder))
            return response

        return self.error_404 (request)

    def api_v3_dataset_decline (self, request, dataset_id):
        """Implements /v3/datasets/<id>/decline."""
        account_uuid = self.default_authenticated_error_handling (request, "POST", "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        reviewer_token = self.token_from_cookie (request, self.impersonator_cookie_key)
        may_review_all = self.db.may_review (reviewer_token)
        may_review_institution = self.db.may_review_institution (reviewer_token)
        if not may_review_all and not may_review_institution:
            return self.error_403 (request)

        reviewer_account = self.db.account_by_session_token (reviewer_token)
        if may_review_institution:
            submitter_token = self.token_from_request (request)
            submitter_account = self.db.account_by_session_token (submitter_token)
            if value_or (reviewer_account, "domain", "A") != value_or (submitter_account, "domain", "not-A"):
                return self.error_403 (request)

        dataset = self.__dataset_by_id_or_uri (dataset_id,
                                               account_uuid = account_uuid,
                                               is_published = False)
        if dataset is None:
            return self.error_403 (request)

        container_uuid = dataset["container_uuid"]
        if self.db.decline_dataset (container_uuid, account_uuid):
            try:
                # E-mail the dataset owner.
                account = self.db.account_by_uuid (dataset["account_uuid"])
                subject = f"Declined: {dataset['title']}"
                parameters = {
                    "base_url": config.base_url,
                    "support_email": config.support_email_address,
                    "title": dataset["title"]
                }
                self.__send_templated_email ([account["email"]], subject,
                                             "dataset_declined", **parameters)

                self.__send_email_to_reviewers (subject, "declined_dataset_notification",
                                                dataset=dataset, account_email = account["email"],
                                                **parameters)
            except (TypeError, IndexError, KeyError):
                self.log.error ("Unable to send decline e-mail for dataset: %s.", dataset["uuid"])

            return self.respond_201 ({
                "location": f"{config.base_url}/review/overview"
            })

        return self.error_500 ()

    def api_v3_dataset_publish (self, request, dataset_id):
        """Implements /v3/datasets/<id>/publish."""

        account_uuid = self.default_authenticated_error_handling (request, "POST",
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        reviewer_token = self.token_from_cookie (request, self.impersonator_cookie_key)
        submitter_token = self.token_from_request (request)
        may_review_all = self.db.may_review (reviewer_token)
        may_review_institution = self.db.may_review_institution (reviewer_token)
        if not may_review_all and not may_review_institution:
            # When using the API, the impersonator cookie isn't set,
            # so we fall back to using the regular token.
            may_review_all = self.db.may_review (submitter_token)
            may_review_institution = self.db.may_review_institution (submitter_token)
            if not may_review_all and not may_review_institution:
                return self.error_403 (request)

        reviewer_account = self.db.account_by_session_token (reviewer_token)
        if may_review_institution:
            submitter_account = self.db.account_by_session_token (submitter_token)
            if value_or (reviewer_account, "domain", "A") != value_or (submitter_account, "domain", "not-A"):
                return self.error_403 (request)

        dataset = self.__dataset_by_id_or_uri (dataset_id,
                                               account_uuid = account_uuid,
                                               is_published = False)
        if dataset is None:
            return self.error_403 (request)

        if not self.db.update_review (dataset["review_uri"],
                                      author_account_uuid = dataset["account_uuid"],
                                      assigned_to = reviewer_account["uuid"],
                                      status      = "assigned"):
            self.log.error ("Unable to assign reviewer before publishing for %s.", dataset_id)

        container_uuid = dataset["container_uuid"]
        container = self.db.container(container_uuid)
        new_version = value_or(container, 'latest_published_version_number', 0) + 1
        if config.in_production and not config.in_preproduction:
            for version in (None, new_version):
                reserved_doi = self.__reserve_and_save_doi (account_uuid,
                                                            dataset,
                                                            version=version)
                if not reserved_doi:
                    return self.error_500 ((f"Reserving DOI {reserved_doi} for "
                                            f"{container_uuid} failed."))

                if not self.__update_item_doi (container_uuid,
                                               item_type="dataset",
                                               version=version):
                    return self.error_500 ((f"Updating DOI {reserved_doi} for "
                                            f"publication of {container_uuid} failed."))

        if self.db.publish_dataset (container_uuid, account_uuid):
            try:
                account = self.db.account_by_uuid (dataset["account_uuid"])

                # Retrieve the dataset again to get the DOIs.
                dataset = self.db.datasets (dataset_uuid=dataset["uuid"], use_cache=False)[0]

                # Cache the Git statistics API endpoints.
                git_url = self.__git_repository_url_for_dataset (dataset)
                git_uuid = value_or_none (dataset, "git_uuid")
                if git_url is not None and git_uuid is not None:
                    response = self.api_v3_dataset_git_languages (request, git_uuid)
                    self.log.info ("Caching Git repository '%s' languages status: %s",
                                   dataset["git_uuid"], response.status_code)
                    response = self.api_v3_dataset_git_contributors (request, git_uuid)
                    self.log.info ("Caching Git repository '%s' contributors status: %s",
                                   dataset["git_uuid"], response.status_code)

                # Send e-mails.
                subject = f"Approved: {dataset['title']}"
                parameters = {
                    "base_url": config.base_url,
                    "support_email": config.support_email_address,
                    "title": dataset["title"],
                    "container_uuid": dataset["container_uuid"],
                    "versioned_doi": value_or_none (dataset, "doi"),
                    "container_doi": dataset["container_doi"]
                }
                self.__send_templated_email ([account["email"]], subject,
                                             "dataset_approved", **parameters)

                self.__send_email_to_reviewers (subject, "published_dataset_notification",
                                                dataset=dataset, account_email = account["email"],
                                                **parameters)

            except (TypeError, IndexError, KeyError) as error:
                self.log.error ("Unable to send approval e-mail for dataset %s: %s.",
                                dataset["uuid"], error)

            return self.respond_201 ({
                "location": f"{config.base_url}/review/published/{dataset_id}"
            })

        return self.error_500 ()

    def api_v3_collection_publish (self, request, collection_id):
        """Implements /v3/collections/<id>/publish."""

        account_uuid = self.default_authenticated_error_handling (request, "POST",
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

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
        validator.string_value  (collection, "resource_doi",   0, 255,   False, errors)
        validator.string_value  (collection, "resource_title", 0, 255,   False, errors)

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
                                         is_published = False,
                                         limit        = None)

        if not categories:
            errors.append({
                "field_name": "categories",
                "message": "Please specify at least one category."})

        if errors:
            return self.error_400_list (request, errors)

        ## Register/update dois
        container_uuid = collection["container_uuid"]
        container = self.db.container(container_uuid, "collection")
        new_version = value_or(container, 'latest_published_version_number', 0) + 1
        if config.in_production and not config.in_preproduction:
            for version in (None, new_version):
                reserved_doi = self.__reserve_and_save_doi (account_uuid, collection,
                                                            version=version,
                                                            item_type="collection")
                if not reserved_doi:
                    return self.error_500 ((f"Reserving DOI {reserved_doi} for "
                                            f"{container_uuid} failed."))

                if not self.__update_item_doi (container_uuid, version=version,
                                               item_type="collection"):
                    return self.error_500 ((f"Updating DOI {reserved_doi} for "
                                            f"publication of {container_uuid} failed."))

        if self.db.publish_collection (collection["container_uuid"], account_uuid):
            return self.respond_201 ({
                "location": f"{config.base_url}/published/{collection_id}"
            })

        return self.error_500 ()

    def api_v3_dataset_submit (self, request, dataset_id):
        """Implements /v3/datasets/<id>/submit-for-review."""

        account_uuid = self.default_authenticated_error_handling (request, "PUT",
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        self.locks.lock (locks.LockTypes.SUBMIT_DATASET)
        dataset = self.__dataset_by_id_or_uri (dataset_id,
                                               account_uuid = account_uuid,
                                               is_published = False,
                                               is_under_review = False)

        if dataset is None:
            self.locks.unlock (locks.LockTypes.SUBMIT_DATASET)
            return self.error_404 (request)

        if value_or (dataset, "is_shared_with_me", False):
            return self.error_403 (request, (f"collaborator account:{account_uuid} "
                                             f"attempted to sumbit dataset:{dataset_id} "
                                             "for review."))

        record = request.get_json()
        try:
            dataset_type = validator.string_value (record, "defined_type", 0, 16)
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

            if is_restricted or is_closed:
                record["embargo_type"] = "file"

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
                                             is_published = False,
                                             limit        = None)

            if not categories:
                errors.append({
                    "field_name": "categories",
                    "message": "Please specify at least one category."})

            license_id = validator.integer_value (record, "license_id", 0, pow(2, 63), True, errors)
            license_url = self.db.license_url_by_id (license_id)
            parameters = {
                "dataset_uuid":       dataset["uuid"],
                "account_uuid":       account_uuid,
                "title":              validator.string_value  (record, "title",          3, 1000,  True, errors),
                "description":        validator.string_value  (record, "description",    0, 10000, True, errors, strip_html=False),
                "resource_doi":       validator.string_value  (record, "resource_doi",   0, 255,   False, errors),
                "resource_title":     validator.string_value  (record, "resource_title", 0, 255,   False, errors),
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
                "mimetype":           validator.string_value  (record, "format",         0, 512,   False, errors),
                "data_link":          validator.string_value  (record, "data_link",      0, 255,   False, errors),
                "derived_from":       validator.string_value  (record, "derived_from",   0, 255,   False, errors),
                "same_as":            validator.string_value  (record, "same_as",        0, 255,   False, errors),
                "organizations":      validator.string_value  (record, "organizations",  0, 2048,   False, errors),
                "is_embargoed":       is_embargoed,
                "is_restricted":      is_restricted,
                "is_metadata_record": validator.boolean_value (record, "is_metadata_record", when_none=False),
                "metadata_reason":    validator.string_value  (record, "metadata_reason",  0, 512, strip_html=False),
                "embargo_until_date": validator.date_value    (record, "embargo_until_date", is_temporary_embargo, errors),
                "embargo_type":       validator.options_value (record, "embargo_type", validator.embargo_types, is_temporary_embargo, errors),
                "embargo_title":      validator.string_value  (record, "embargo_title", 0, 1000, is_embargoed, errors),
                "embargo_reason":     validator.string_value  (record, "embargo_reason", 0, 10000, is_embargoed, errors, strip_html=False),
                "eula":               validator.string_value  (record, "eula", 0, 50000, is_restricted, errors, strip_html=False),
                "defined_type_name":  dataset_type,
                "defined_type":       defined_type,
                "agreed_to_deposit_agreement": agreed_to_deposit_agreement,
                "agreed_to_publish":  agreed_to_publish,
                "categories":         validator.array_value   (record, "categories", True, errors)
            }

            if not parameters["is_metadata_record"]:
                files = self.db.dataset_files (account_uuid = account_uuid,
                                               dataset_uri  = dataset["uri"],
                                               limit        = 1)
                if not files and parameters["defined_type_name"] != "software":
                    errors.append({
                        "field_name": "files",
                        "message": "Upload at least one file, or choose metadata-only record."})

            if errors:
                self.locks.unlock (locks.LockTypes.SUBMIT_DATASET)
                return self.error_400_list (request, errors)

            account = self.db.account_by_uuid (dataset["account_uuid"])
            if not account:
                self.locks.unlock (locks.LockTypes.SUBMIT_DATASET)
                return self.error_500()

            result = self.db.update_dataset (**parameters)
            if not result:
                self.locks.unlock (locks.LockTypes.SUBMIT_DATASET)
                return self.error_500()

            if self.db.insert_review (dataset["uri"]) is not None:
                subject = f"Request for review: {dataset['container_uuid']}"
                self.__send_email_to_reviewers (subject, "submitted_for_review_notification",
                                                account_email=value_or_none(account, "email"),
                                                dataset=dataset,
                                                account=account)

                # When in pre-production state, don't send e-mails to depositors.
                if config.in_production and not config.in_preproduction and "email" in account:
                    self.__send_templated_email (
                        [account["email"]],
                        f"Submission of {dataset['title']}.",
                        "dataset_submitted",
                        dataset = dataset,
                        account = account,
                        support_email = config.support_email_address,
                        site_name = config.site_name)

                self.locks.unlock (locks.LockTypes.SUBMIT_DATASET)
                return self.respond_204 ()

        except validator.ValidationException as error:
            self.locks.unlock (locks.LockTypes.SUBMIT_DATASET)
            return self.error_400 (request, error.message, error.code)
        except (IndexError, KeyError):
            pass

        self.locks.unlock (locks.LockTypes.SUBMIT_DATASET)
        return self.error_500 ()

    def __image_mimetype (self, file_path):
        """Returns the mimetype and file extension for FILE_PATH."""
        mimetype = None
        try:
            with Image.open (file_path) as image:
                mimetype = image.get_format_mimetype()
        except (FileNotFoundError, UnidentifiedImageError):
            pass
        return mimetype

    def api_v3_profile_picture_for_account (self, request, account_uuid):
        """Implements /v3/profile/picture/<account_uuid>."""

        if not validator.is_valid_uuid (account_uuid):
            return self.error_404 (request)

        if request.method != "GET":
            return self.error_405 ("GET")

        try:
            account   = self.db.account_by_uuid (account_uuid)
            file_path = account["profile_image"]
            mimetype  = self.__image_mimetype (file_path)
            if mimetype is not None:
                return send_file (file_path, request.environ, mimetype)
            return self.error_403 (request)

        except (KeyError, FileNotFoundError):
            return self.error_404 (request)

    def api_v3_profile_picture (self, request):
        """Implements /v3/profile/picture."""

        token   = self.token_from_cookie (request)
        account = self.db.account_by_session_token (token)
        if account is None:
            return self.error_authorization_failed (request)

        if request.method in ("GET", "HEAD"):
            try:
                file_path = account["profile_image"]
                mimetype = self.__image_mimetype (file_path)
                if mimetype is not None:
                    return send_file (file_path, request.environ, mimetype)
                return self.error_403 (request)

            except (KeyError, FileNotFoundError) as error:
                self.log.error ("Failed to send profile image due to: %s", error)
                return self.error_404 (request)

        if request.method == "DELETE":
            try:
                if "profile_image" in account:
                    os.remove (account["profile_image"])
                if self.db.delete_account_property (account["uuid"], "profile_image"):
                    self.log.info ("Removed profile image for account %s", account["uuid"])
                else:
                    self.log.error ("Failed to remove profile image for %s", account["uuid"])
            except (KeyError, FileNotFoundError) as error:
                self.log.error ("Failed to remove profile image for %s due to: %s",
                                account["uuid"], error)

            return self.respond_204 ()

        if request.method == "POST":
            if not self.accepts_json(request):
                return self.error_406 ("application/json")

            handler = self.default_error_handling (request, "POST", "application/json")
            if handler is not None:
                return handler

            try:
                file_data       = request.files['file']
                _, extension = os.path.splitext (file_data.filename)
                output_filename = os.path.join (config.profile_images_storage, account['uuid'])

                if not (extension.lower() == ".jpg" or extension.lower() == ".png"):
                    return self.error_400 (request, "Only JPG and PNG images are supported.",
                                           "InvalidImageFormat")

                file_data.save (output_filename)
                file_data.close ()
                if os.name != 'nt':
                    os.chmod (output_filename, 0o600)

                image = Image.open (output_filename)
                width, height = image.size
                if width > 800 or height > 800:
                    self.log.warning ("Account %s uploaded an image of %d by %d pixels.",
                                      account["uuid"], width, height)
                    image.close ()
                    os.remove (output_filename)
                    return self.error_400 (request, "The maximum image dimensions are 800 by 800 pixels.", "ImageTooLarge")

                if self.db.update_account (account["uuid"], profile_image=output_filename):
                    self.log.info ("Updated profile image for account %s", account["uuid"])
                    return self.response (json.dumps({ "location": f"{config.base_url}/v3/profile/picture" }))

            except OSError:
                self.log.error ("Writing %s to disk failed.", output_filename)
                return self.error_400 (request, "Cannot determine the format of the uploaded image.", "InvalidImageFormat")
            except (IndexError, KeyError) as error:
                self.log.error ("Uploading profile image failed with error: %s", error)
                return self.error_400 (request, "Uploading the profile image failed.", "UploadFailed")

        return self.error_405 (["GET", "POST", "DELETE"])

    def __register_file_handle (self, handle, download_url):
        """Procedure to register a file handle."""

        if config.handle_url is None:
            return False

        handle_data = { "values": [
            { "index": config.handle_index,
              "type": "URL",
              "data": {
                  "format": "string",
                  "value": download_url
              }
             }]}
        http_headers = {
            "Accept":        "application/json",
            "Content-Type":  "application/json",
            "Authorization": 'Handle clientCert="true"',
        }

        try:
            response = requests.put (f"{config.handle_url}/{handle}",
                                     headers = http_headers,
                                     cert    = (config.handle_certificate_path,
                                                config.handle_private_key_path),
                                     timeout = 60,
                                     json    = handle_data)

            if response.status_code == 201:
                self.log.info ("Handle %s created.", handle)
                return True

            self.log.error ("Handle registration failed with %s (%s)",
                            response.status_code, response.text)
        except requests.exceptions.ConnectionError as error:
            self.log.error ("Failed to create handle %s due to a connection error.", handle)
            self.log.error ("Error: %s", error)

        return False

    def api_v3_dataset_upload_file (self, request, dataset_id):
        """Implements /v3/datasets/<id>/upload."""
        handler = self.default_error_handling (request, "POST", "application/json")
        if handler is not None:
            return handler

        ## Impersonation requires reading the request's content, which means that
        ## the body has to be read entirely, negating the ability to stream the
        ## requests's body.
        account_uuid = self.account_uuid_from_request (request, allow_impersonation=False)
        if account_uuid is None:
            return self.error_authorization_failed(request)

        account = self.db.account_by_uuid (account_uuid)
        if account is None or "quota" not in account:
            return self.error_403 (request, (f"account:{account_uuid} attempted to "
                                             "upload a file but has no assigned quota."))

        storage_used      = self.db.account_storage_used (account_uuid)
        storage_available = account["quota"] - storage_used
        if storage_available < 1:
            return self.error_413 (request)

        # If strict_check is set to 1, the file is not accepted if
        # (1) the file is empty. Or (2) the file is already uploaded.
        strict_check = validator.integer_value (request.args, "strict_check", 0, 1)
        supplied_md5 = None

        if strict_check:
            try:
                supplied_md5 = validator.string_value (request.args, "md5",
                                             minimum_length=32,
                                             maximum_length=32,
                                             required=True)
            except validator.ValidationException as error:
                return self.error_400 (request, error.message, error.code)

            # If the supplied_md5 is d41d8cd98f00b204e9800998ecf8427e,
            # it means the content of the file is empty.
            if supplied_md5 == "d41d8cd98f00b204e9800998ecf8427e":
                return self.error_400 (request, "Empty file is not allowed.", "EmptyFile")

        try:
            dataset   = self.__dataset_by_id_or_uri (dataset_id,
                                                     account_uuid=account_uuid,
                                                     is_published=False)
            if dataset is None:
                return self.error_403 (request, (f"account:{account_uuid} attempted to "
                                                 f"upload a file to dataset:{dataset_id}."))

            _, error_response = self.__needs_collaborative_permissions (
                account_uuid, request, "dataset", dataset, "data_edit")
            if error_response is not None:
                return error_response

            if strict_check:
                files = self.db.dataset_files (
                    dataset_uri = dataset["uri"],
                    account_uuid = account_uuid
                )

                for file in files:
                    if "computed_md5" not in file:
                        continue
                    if file["computed_md5"] == supplied_md5:
                        return self.error_409 ()

            content_type = value_or (request.headers, "Content-Type", "")
            if not content_type.startswith ("multipart/form-data"):
                return self.error_415 (["multipart/form-data"])

            boundary = None
            try:
                boundary = content_type.split ("boundary=")[1]
                boundary = boundary.split(";")[0]
            except IndexError:
                self.log.error ("File upload failed due to missing boundary.")
                return self.error_400 (
                    request,
                    "Missing boundary for multipart/form-data.",
                    "MissingBoundary")

            bytes_to_read = request.content_length
            if bytes_to_read is None:
                self.log.error ("File upload failed due to missing Content-Length.")
                return self.error_400 (
                    request,
                    "Missing Content-Length header.",
                    "MissingContentLength")

            # Note that the bytes_to_read contain some overhead of the
            # multipart headings (~220 bytes per chunk).
            if storage_available < bytes_to_read:
                self.log.error ("File upload failed because user's quota limit: quota(%d), used(%d), available(%s), filesize(%d)", account["quota"], storage_used, storage_available, bytes_to_read)
                return self.error_413 (request)

            input_stream = request.stream

            # Read the boundary, plus '--', plus CR/LF.
            read_ahead_bytes = len(boundary) + 4
            boundary_scan  = input_stream.read (read_ahead_bytes)
            expected_begin = f"--{boundary}\r\n".encode("utf-8")
            expected_end   = f"\r\n--{boundary}--\r\n".encode("utf-8")
            if not boundary_scan == expected_begin:
                self.log.error ("File upload failed due to unexpected read while parsing.")
                self.log.error ("Scanned:  '%s'", boundary_scan)
                self.log.error ("Expected: '%s'", expected_begin)
                return self.error_400 (request,
                                       "Expected stream to start with boundary.",
                                       "MalformedRequest")

            # Read the multi-part headers
            line = None
            header_line_count = 0
            part_headers = ""
            while line != b"\r\n" and header_line_count < 10:
                line = input_stream.readline (4096)
                part_headers += line.decode("utf-8")
                header_line_count += 1

            if "Content-Disposition: form-data" not in part_headers:
                self.log.error ("File upload failed due to missing Content-Disposition.")
                return self.error_400 (request,
                                       "Expected Content-Disposition: form-data",
                                       "MalformedRequest")

            filename = None
            try:
                # Extract filename.
                filename = part_headers.split("filename=")[1].split(";")[0].split("\r\n")[0]
                # Remove quotes from the filename.
                if filename[0] == "\"" and filename[-1] == "\"":
                    filename = filename[1:-1]
            except IndexError:
                pass

            headers_len        = len(part_headers.encode('utf-8'))
            computed_file_size = request.content_length - read_ahead_bytes - headers_len - len(expected_end)
            bytes_to_read      = bytes_to_read - read_ahead_bytes - headers_len
            content_to_read    = bytes_to_read - len(expected_end)

            try:
                self.locks.lock (locks.LockTypes.FILE_LIST)
                file_uuid = self.db.insert_file (
                    name          = filename,
                    size          = computed_file_size,
                    is_link_only  = 0,
                    upload_url    = f"/article/{dataset_id}/upload",
                    upload_token  = self.token_from_request (request),
                    dataset_uri   = dataset["uri"],
                account_uuid  = account_uuid)
            except RuntimeError as error:
                self.locks.unlock (locks.LockTypes.FILE_LIST)
                self.error_500 (("Failed to create file metadata for "
                                 f"{dataset_id}: {error}."))

            self.locks.unlock (locks.LockTypes.FILE_LIST)
            output_filename = os.path.join (config.storage, f"{dataset_id}_{file_uuid}")

            computed_md5 = None
            md5 = hashlib.new ("md5", usedforsecurity=False)
            file_size = 0
            destination_fd = os.open (output_filename, os.O_WRONLY | os.O_CREAT, 0o600)
            is_incomplete = None
            try:
                with open (destination_fd, "wb") as output_stream:
                    file_size = 0
                    while content_to_read > 4096:
                        chunk = input_stream.read (4096)
                        content_to_read -= 4096
                        file_size += output_stream.write (chunk)
                        md5.update (chunk)

                    if content_to_read > 0:
                        chunk = input_stream.read (content_to_read)
                        file_size += output_stream.write (chunk)
                        md5.update (chunk)
                        content_to_read = 0
                    else:
                        md5.update (bytes(0))

                    # Make the file read-only from here on.
                    if os.name != 'nt':
                        os.fchmod (destination_fd, 0o400)  # pylint: disable=no-member
            except BadRequest:
                is_incomplete = 1
                self.log.error ("Failed to write %s to disk: possible that bad internet connection on user's side or page refreshed/closed during upload.", output_filename)

            if computed_file_size != file_size:
                is_incomplete = 1
                self.log.error ("Computed file size (%d) and actual file size (%d) for uploaded file mismatch.",
                                computed_file_size, file_size)

            bytes_to_read -= file_size
            if bytes_to_read != len(expected_end):
                is_incomplete = 1
                self.log.error ("Expected different length after file contents: '%d' != '%d'.",
                                bytes_to_read, len(expected_end))

            if is_incomplete != 1:
                ending = input_stream.read (bytes_to_read)
                if ending != expected_end:
                    is_incomplete = 1
                    self.log.error ("Expected different end after file contents: '%s' != '%s'.",
                                    ending, expected_end)

            computed_md5 = md5.hexdigest()

            if strict_check and computed_md5 != supplied_md5:
                self.log.error ("MD5 checksum mismatch for %s: computed_md5(%s) != supplied_md5(%s)",
                                output_filename, computed_md5, supplied_md5)

                try:
                    file_metadata = self.__file_by_id_or_uri (file_uuid,
                                                         account_uuid = account_uuid,
                                                         dataset_uri = dataset["uri"])

                    if self.db.delete_item_from_list (dataset["uri"], "files",
                                                      uuid_to_uri (file_metadata["uuid"], "file")):
                        self.db.cache.invalidate_by_prefix (f"{account_uuid}_storage")
                        self.db.cache.invalidate_by_prefix (f"{dataset['uuid']}_dataset_storage")
                    else:
                        self.log.error ("Failed to delete file %s from dataset %s.",
                                        file_uuid, dataset_id)
                except (IndexError, KeyError, StopIteration):
                    pass

                os.remove (output_filename)
                return self.error_400 (request,
                                       "MD5 checksum mismatch.",
                                       "MD5Mismatch")

            download_url = f"{config.base_url}/file/{dataset_id}/{file_uuid}"

            # Set an upper limit on thumbnailable images.
            is_image = False
            if file_size < 10000001:
                is_image = self.__image_mimetype (output_filename) is not None

            handle = None
            if not is_incomplete:
                handle = f"{config.handle_prefix}/{file_uuid}"
                if not self.__register_file_handle (handle, download_url):
                    handle = None

            self.db.update_file (account_uuid, file_uuid, dataset["uuid"],
                                 computed_md5  = computed_md5,
                                 download_url  = download_url,
                                 filesystem_location = output_filename,
                                 file_size     = file_size,
                                 is_image      = is_image,
                                 is_incomplete = is_incomplete,
                                 handle        = handle)

            response_data = { "location": f"{config.base_url}/v3/file/{file_uuid}" }
            if is_incomplete:
                response_data["is_incomplete"] = is_incomplete

            return self.response (json.dumps(response_data))

        except OSError as error:
            return self.error_500 (f"Writing {output_filename} to disk failed: {error}")
        except (IndexError, KeyError):
            pass

        return self.error_500 ()

    def api_v3_dataset_image_files (self, request, dataset_id):
        """Implements /v3/datasets/<dataset_id>/image-files."""
        account_uuid = self.default_authenticated_error_handling (request, "GET", "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        try:
            dataset = self.__dataset_by_id_or_uri (dataset_id,
                                                   account_uuid=account_uuid,
                                                   is_published=False)
            if dataset is None:
                return self.error_403 (request, (f"account:{account_uuid} attempted to view "
                                                 f"image files for dataset:{dataset_id}."))

            files = self.db.dataset_files (
                dataset_uri  = dataset["uri"],
                account_uuid = account_uuid,
                limit        = validator.integer_value (request.args, "limit"),
                order        = validator.integer_value (request.args, "order"),
                order_direction = validator.order_direction (request.args, "order_direction"),
                is_image     = True)

            return self.default_list_response (files, formatter.format_file_for_dataset_record,
                                                base_url = config.base_url)

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)
        except KeyError:
            pass

        return self.error_500 ()

    def api_v3_datasets_update_thumbnail (self, request, dataset_id):
        """Implements /v3/datasets/<dataset_id>/update-thumbnail."""
        account_uuid = self.default_authenticated_error_handling (request, "PUT", "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        dataset = self.__dataset_by_id_or_uri (dataset_id,
                                               account_uuid=account_uuid,
                                               is_published=False)
        if dataset is None:
            return self.error_403 (request, (f"account:{account_uuid} attempted to update "
                                             f"the thumbnail of dataset:{dataset_id}."))

        try:
            parameters = request.get_json()
            file_uuid  = validator.string_value (parameters, "uuid", 0, 36, False)

            if file_uuid == "":
                if not self.db.dataset_update_thumb (dataset["uuid"], account_uuid,
                                                     file_uuid, None):
                    return self.error_500()
                return self.respond_205()

            if not validator.is_valid_uuid (file_uuid):
                return self.error_403 (request)
        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

        metadata = self.__file_by_id_or_uri (file_uuid, account_uuid = account_uuid)
        if metadata is None:
            return self.error_404 (request)

        if value_or (metadata, "size", 0) >= 10000000:
            self.log.error ("Tried to create a thumbnail for a large image.")
            return self.error_400 (request,
                message = "Cannot create thumbnails for images larger than 10MB.",
                code = "ImageTooLarge")

        input_filename = self.__filesystem_location (metadata)
        if input_filename is None:
            return self.error_404 (request)

        extension = self.__generate_thumbnail (input_filename, dataset["uuid"])
        if extension is None:
            return self.error_500 ()

        if not self.db.dataset_update_thumb (dataset["uuid"], account_uuid,
                                             file_uuid, extension):
            return self.error_500()

        return self.respond_205()

    def api_v3_file (self, request, file_id):
        """Implements /v3/file/<id>."""

        account_uuid = self.default_authenticated_error_handling (request, "GET",
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        metadata = self.__file_by_id_or_uri (file_id, account_uuid = account_uuid)
        if metadata is None:
            return self.error_404 (request)

        _, error_response = self.__needs_collaborative_permissions (
            account_uuid, request, "file", metadata, "data_read")
        if error_response is not None:
            return error_response

        try:
            metadata["base_url"] = config.base_url
            return self.response (json.dumps (formatter.format_file_details_record (metadata)))
        except KeyError:
            return self.error_500()

    def __api_v3_item_references (self, request, item):
        """Implements getting/setting references for datasets and collections."""

        account_uuid = self.default_authenticated_error_handling (request,
                                                                  ["GET", "POST", "DELETE"],
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        try:
            references     = self.db.references (item_uri     = item["uri"],
                                                 account_uuid = account_uuid)

            if request.method in ("GET", "HEAD"):
                return self.default_list_response (references, formatter.format_reference_record)

            references     = list(map(lambda reference: reference["url"], references))

            if request.method == 'DELETE':
                url = validator.string_value (request.args, "url", 0, 1024, True)
                references.remove (next (filter (lambda item: item == url, references)))
                if not self.db.update_item_list (item["uuid"], account_uuid,
                                                 references, "references"):
                    return self.error_500 ("Deleting a reference failed.")

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

            if not self.db.update_item_list (item["uuid"],
                                             account_uuid,
                                             references,
                                             "references"):
                return self.error_500 ("Updating references failed.")

            return self.respond_205()

        except IndexError:
            return self.error_500 ()
        except KeyError as error:
            self.log.error ("KeyError: %s", error)
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

        _, error_response = self.__needs_collaborative_permissions (
            account_uuid, request, "dataset", dataset, "metadata_read")
        if error_response is not None:
            return error_response

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

    def __api_v3_item_tags (self, request, item_type, item_id, item_by_id_procedure):
        """Implements handling tags for both datasets and collections."""

        account_uuid = self.default_authenticated_error_handling (request,
                                                                  ["GET", "POST", "DELETE"],
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        try:
            item  = item_by_id_procedure (item_id,
                                          account_uuid=account_uuid,
                                          is_published=False)

            _, error_response = self.__needs_collaborative_permissions (
                account_uuid, request, item_type, item, "metadata_read")
            if error_response is not None:
                return error_response

            tags = self.db.tags (
                item_uri        = item["uri"],
                account_uuid    = account_uuid,
                limit           = validator.integer_value (request.args, "limit"),
                order           = validator.integer_value (request.args, "order"),
                order_direction = validator.order_direction (request.args, "order_direction"))

            if request.method in ("GET", "HEAD"):
                return self.default_list_response (tags, formatter.format_tag_record)

            tags     = list(map(lambda tag: tag["tag"], tags))

            if request.method == 'DELETE':
                tag_encoded = validator.string_value (request.args, "tag", 0, 1024, True)
                tag         = unquote(tag_encoded)
                try:
                    tags.remove (next (filter (lambda item: item == tag, tags)))
                    if self.db.update_item_list (item["uuid"], account_uuid, tags, "tags"):
                        return self.respond_204()
                except StopIteration:
                    pass

                return self.error_500 (f"Deleting tag '{tag}' failed for <{item['uri']}>.")


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

            if not self.db.update_item_list (item["uuid"], account_uuid, tags, "tags"):
                return self.error_500 ("Updating tags failed.")

            return self.respond_205()

        except IndexError:
            return self.error_500 ()
        except KeyError as error:
            self.log.error ("KeyError: %s", error)
            return self.error_400 (request, "Expected a 'tags' field.", "NoTagsField")
        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    def api_v3_collection_tags (self, request, collection_id):
        """Implements /v3/collections/<id>/tags."""
        return self.__api_v3_item_tags (request, "collection", collection_id, self.__collection_by_id_or_uri)

    def api_v3_dataset_tags (self, request, dataset_id):
        """Implements /v3/datasets/<id>/tags."""
        return self.__api_v3_item_tags (request, "dataset", dataset_id, self.__dataset_by_id_or_uri)

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
                is_featured     = validator.boolean_value (request.args, "is_featured"),
                limit           = validator.integer_value (request.args, "limit"),
                offset          = validator.integer_value (request.args, "offset"),
                order           = validator.integer_value (request.args, "order"),
                order_direction = validator.order_direction (request.args, "order_direction"))

            return self.default_list_response (records, formatter.format_group_record)

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    def api_v3_admin_files_integrity_statistics (self, request):
        """Implements /v3/admin/files-integrity-statistics."""

        handler = self.default_authenticated_error_handling (request, "GET", "application/json",
                                                             self.db.may_review_integrity)
        if isinstance (handler, Response):
            return handler

        files = self.db.repository_file_statistics (extended_properties=True)
        number_of_files = 0
        number_of_inaccessible_files = 0
        number_of_incomplete_metadata = 0
        number_of_bytes = 0
        number_of_links = 0
        incomplete_metadata = []
        missing_files = []

        for entry in files:
            if value_or (entry, "is_link_only", False):
                number_of_links += 1
                continue

            number_of_files += 1
            number_of_bytes += int(float(entry["bytes"]))

            filesystem_location = self.__filesystem_location (entry)
            if not filesystem_location:
                number_of_incomplete_metadata += 1
                incomplete_metadata.append (value_or (entry, "uuid", "unknown"))
                continue

            if not os.path.isfile (filesystem_location):
                number_of_inaccessible_files += 1
                missing_files.append (filesystem_location)

        output = {
            "number_of_links":              number_of_links,
            "number_of_files":              number_of_files,
            "number_of_bytes":              number_of_bytes,
            "number_of_accessible_files":   number_of_files - number_of_inaccessible_files,
            "number_of_inaccessible_files": number_of_inaccessible_files,
            "number_of_incomplete_metadata": number_of_incomplete_metadata,
            "percentage_accessible":        (1.0 - (number_of_inaccessible_files / number_of_files)) * 100,
            "percentage_inaccessible":      number_of_inaccessible_files / number_of_files * 100,
            "inaccessible_files":           missing_files,
            "incomplete_metadata":          incomplete_metadata,
        }

        return self.response (json.dumps(output))

    def __git_create_repository (self, git_uuid):
        git_directory = os.path.join(config.storage, f"{git_uuid}.git")
        if not os.path.exists (git_directory):
            initial_repository = pygit2.init_repository (git_directory, True)
            if initial_repository:
                try:
                    with open (os.path.join(git_directory, "config"), "a",
                               encoding = "utf-8") as git_config:
                        git_config.write ("\n[http]\n  receivepack = true\n")
                except FileNotFoundError:
                    self.log.error ("%s/.git/config does not exist.", git_directory)
                    return False
                except OSError:
                    self.log.error ("Could not open %s/.git/config", git_directory)
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

            ## Git's http-backend checks for whether the REMOTE_USER matches
            ## the local user.  We match it to the user of the running process.
            "REMOTE_USER": getpass.getuser(),

            ## Passthrough some HTTP information.
            "GIT_PROTOCOL":        git_protocol,
            "CONTENT_TYPE":        content_type,
            "REQUEST_METHOD":      request.method,
            "QUERY_STRING":        request.query_string,

            ## Rewrite as if the request matches the filesystem layout.
            ## It assumes the first twelve characters are: "/v3/datasets".
            "PATH_TRANSLATED":     f"{config.storage}{request.path[12:]}",
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
            self.log.error ("Proxying to Git failed with exit code %d", error.returncode)
            self.log.error ("The command was:\n---\n%s\n---", error.cmd)
            return self.error_500()

    def api_v3_private_dataset_git_instructions (self, request, git_uuid):
        """Implements an instruction page for /v3/datasets/<id>.git."""
        handler = self.default_error_handling (request, "GET", "text/html")
        if handler is not None:
            return handler

        if not validator.is_valid_uuid (git_uuid):
            return self.error_404 (request)

        try:
            # Only consider published datasets to not reveal whether a UUID
            # is reserved for a Git repository.
            dataset = self.db.datasets (git_uuid     = git_uuid,
                                        is_published = True,
                                        is_latest    = None)[0]
            git_repository_url = self.__git_repository_url_for_dataset (dataset)
            return self.__render_template (request, "git_instructions.html",
                                           git_repository_url = git_repository_url)
        except IndexError:
            pass

        return self.error_404 (request)

    def api_v3_private_dataset_git_refs (self, request, git_uuid):
        """Implements /v3/datasets/<id>.git/<suffix>."""

        service = validator.string_value (request.args, "service", 0, 16)
        self.__git_create_repository (git_uuid)

        ## Used for clone and pull.
        if service == "git-upload-pack":
            return self.api_v3_private_dataset_git_upload_pack (request, git_uuid)

        ## Used for push.
        if service == "git-receive-pack":
            return self.api_v3_private_dataset_git_receive_pack (request, git_uuid)

        return self.error_500 (f"Unsupported Git service command: {service}.")

    def api_v3_private_dataset_git_receive_pack (self, request, git_uuid):
        """Implements /v3/datasets/<id>.git/git-receive-pack."""
        try:
            if not validator.is_valid_uuid (git_uuid):
                return self.error_403 (request, ("Someone attempted to update a git "
                                                 "repository with an invalid UUID."))

            dataset = self.db.datasets (git_uuid = git_uuid, is_published=False)[0]
            if dataset is not None:
                return self.__git_passthrough (request)
        except IndexError:
            pass

        return self.error_403 (request, (f"Someone attempted to update the git "
                                         f"repository git:{git_uuid}."))

    def api_v3_private_dataset_git_upload_pack (self, request, git_uuid):
        """Implements /v3/datasets/<id>.git/git-upload-pack."""
        try:
            if not validator.is_valid_uuid (git_uuid):
                return self.error_403 (request, ("Someone attempted to pull a git "
                                                 "repository with an invalid UUID."))
            dataset = self.db.datasets (git_uuid     = git_uuid,
                                        is_published = None,
                                        is_latest    = None)[0]
            if dataset is not None:
                self.__log_event (request, dataset["container_uuid"], "dataset", "gitDownload")
                return self.__git_passthrough (request)
        except IndexError:
            pass

        return self.error_403 (request, (f"Someone attempted to pull the git "
                                         f"repository git:{git_uuid}."))

    def __git_contributors (self, git_uuid, git_repository):
        """Returns a list of contributors including their commit statistics."""
        history = git_repository.walk (git_repository.head.target,
                                       pygit2.enums.SortMode.REVERSE)

        cache_key = f"{git_uuid}_{git_repository.head.target}"
        cache_prefix = "git_contributors"
        cached_value = self.db.cache.cached_value (cache_prefix, cache_key)
        if cached_value:
            return cached_value

        commits = list(history)
        if not commits:
            return None

        # Accounting for the initial commit.
        contributors = {}
        previous_commit = commits[0]
        stats = self.__git_files_by_type (previous_commit.tree)
        total_lines = 0
        for extension in stats:
            for entry in stats[extension]:
                total_lines += value_or (entry, "lines", 0)

        week = datetime.fromtimestamp(previous_commit.commit_time).isocalendar()
        week = int(datetime.fromisocalendar(week[0], week[1], 1).timestamp())

        contributors[previous_commit.author.email] = {
            "total": 1,
            "additions": total_lines,
            "deletions": 0,
            "weeks": { week: { "w": week, "a": total_lines, "d": 0, "c": 1 } },
            "author": {
                "name": previous_commit.author.name,
                "email": previous_commit.author.email
            }
        }

        # Walk the repository's history.
        for commit in commits[1:]:
            stats = git_repository.diff(previous_commit, commit).stats
            week = datetime.fromtimestamp(commit.commit_time).isocalendar()
            week = int(datetime.fromisocalendar(week[0], week[1], 1).timestamp())
            if commit.author.email not in contributors:
                contributors[commit.author.email] = {
                    "total": 0,
                    "additions": 0,
                    "deletions": 0,
                    "weeks": { week: { "w": week, "c": 0, "a": 0, "d": 0 } },
                    "author": {
                        "name": commit.author.name,
                        "email": commit.author.email
                    }
                }
            record = contributors[commit.author.email]
            if "weeks" in record and week in record["weeks"]:
                record["weeks"][week]["c"] += 1
                record["weeks"][week]["a"] += stats.insertions
                record["weeks"][week]["d"] += stats.deletions
                record["total"] += 1
                record["additions"] += stats.insertions
                record["deletions"] += stats.deletions
            else:
                record["weeks"][week] = {
                    "w": week,
                    "c": 1,
                    "a": stats.insertions,
                    "d": stats.deletions
                }
                record["total"] += 1
                record["additions"] += stats.insertions
                record["deletions"] += stats.deletions

            previous_commit = commit

        # Flatten the structure
        contributors = list(contributors.values())
        for contributor in contributors:
            contributor["weeks"] = list(contributor["weeks"].values())

        self.db.cache.cache_value (cache_prefix, cache_key, contributors)
        return contributors

    def __git_files_by_type (self, tree, path="", output=None):
        """
        Returns a dictionary with the file extension as key and the list of
        file statistics as value for the git repository TREE.
        """
        if output is None:
            output = {}

        for entry in tree:
            # Walk the directory tree
            if isinstance (entry, pygit2.Tree):  # pylint: disable=no-member
                self.__git_files_by_type (list(entry), f"{path}{entry.name}/", output)
                continue

            # Submodules are represented as commits.
            if isinstance (entry, pygit2.Commit):  # pylint: disable=no-member
                continue

            record = { "filename": f"{path}{entry.name}", "size": entry.size }

            # Skip over binary files and large files.
            if entry.is_binary or entry.size > 5000000:
                extension = "binary" if entry.is_binary else "large-text-file"
                if extension in output:
                    output[extension].append(record)
                else:
                    output[extension] = [record]
                continue

            # Add line-count information
            record["lines"] = entry.data.count(b'\n')

            # We count newlines, but that would miss out on the last
            # line without a newline.
            if entry.data != b'' and entry.data[-1:] != b'\n':
                record["lines"] += 1

            _, extension = os.path.splitext (entry.name)
            extension = "no-extension" if extension == "" else extension.lstrip(".").lower()
            language = value_or_none (filetypes_by_extension, extension)
            if language is None:
                language = "Other"
            if language in output:
                output[language].append(record)
            else:
                output[language] = [record]

        return output

    def __git_statistics_error_handling (self, request, git_uuid):

        if not validator.is_valid_uuid (git_uuid):
            return self.error_400 (request, "Invalid UUID.", "InvalidGitUUIError"), None

        if not self.db.datasets (git_uuid=git_uuid, is_published=None, is_latest=None):
            self.log.error ("No dataset associated with Git repository '%s'.", git_uuid)
            return self.error_404 (request), None

        git_directory = os.path.join (config.storage, f"{git_uuid}.git")
        if not os.path.exists (git_directory):
            self.log.error ("No Git repository at '%s'", git_directory)
            return self.error_404 (request), None

        git_repository = pygit2.Repository (git_directory)
        if git_repository is None:
            self.log.error ("Could not open Git repository for '%s'.", git_uuid)
            return self.error_404 (request), None

        default_branch = self.__git_repository_default_branch_guess (git_repository)
        if not default_branch:
            self.log.error ("Expected default branch to be set for '%s'.", git_uuid)
            return self.error_404 (request), None

        return git_repository, default_branch

    def api_v3_dataset_git_languages (self, request, git_uuid):
        """Implements /v3/datasets/<id>/languages."""

        git_repository, branch = self.__git_statistics_error_handling (request, git_uuid)
        if isinstance (git_repository, Response):
            return git_repository

        cache_key = f"{git_uuid}_{git_repository.head.target}"
        cache_prefix = "git_languages"
        cached_value = self.db.cache.cached_value (cache_prefix, cache_key)
        if cached_value:
            return self.response (cached_value)

        tree = git_repository.revparse_single(branch).tree # pylint: disable=no-member
        statistics = self.__git_files_by_type (tree)

        # Drop the binary count from the statistics, because we only
        # generate a summary with line counts below.
        statistics.pop("binary", None)

        summary = {}
        for _, extension in enumerate (statistics):
            num_bytes_for_extension = 0
            for entry in statistics[extension]:
                num_lines = value_or (entry, "lines", 0)
                num_bytes = value_or (entry, "size", 0)
                # Remove minified sources by the heuristic that the average
                # line length must be smaller than 300 bytes long.  This seems
                # to come close to how Github reports the statistics.
                if num_lines > 0 and num_bytes / num_lines < 300:
                    num_bytes_for_extension += num_bytes

            summary[extension] = num_bytes_for_extension

        sorted_summary = dict(sorted(summary.items(),
                                     key=lambda item: item[1],
                                     reverse=True))
        self.db.cache.cache_value (cache_prefix, cache_key, json.dumps (sorted_summary))
        return self.response (json.dumps (sorted_summary))

    def api_v3_dataset_git_contributors (self, request, git_uuid):
        """Implements /v3/datasets/<id>/contributors."""

        git_repository, _ = self.__git_statistics_error_handling (request, git_uuid)
        if isinstance (git_repository, Response):
            return git_repository

        contributors = self.__git_contributors (git_uuid, git_repository)
        if contributors is None:
            return self.error_404 (request)

        return self.response (json.dumps(contributors))

    def api_v3_profile (self, request):
        """Implements /v3/profile."""

        account_uuid = self.default_authenticated_error_handling (request, "PUT",
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

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
                    maximum_file_size     = validator.integer_value (record, "maximum_file_size"),
                    modified_date         = validator.string_value  (record, "modified_date", 0, 32),
                    categories            = categories):
                return self.respond_204 ()

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

        return self.error_500 ()

    def api_v3_profile_categories (self, request):
        """Implements /v3/profile/categories."""

        account_uuid = self.default_authenticated_error_handling (request, "GET",
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        categories = self.db.account_categories (account_uuid)
        return self.default_list_response (categories, formatter.format_category_record)

    def api_v3_profile_quota_request (self, request):
        """Implements /v3/profile/quota-request."""

        account_uuid = self.default_authenticated_error_handling (request, "POST",
                                                                  "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        try:
            parameters = request.get_json()
            quota_gb   = validator.integer_value (parameters, "new-quota", required=True)
            reason     = validator.string_value (parameters, "reason", 0, 10000, required=True, strip_html=False)

            if quota_gb < 1:
                return self.error_400 (request,
                    "Requested quota must be at least 1 gigabyte.",
                    "QuotaRequestSizeTooSmall")

            new_quota = quota_gb * 1000000000
            quota_uuid = self.db.insert_quota_request (account_uuid, new_quota, reason)
            if quota_uuid is None:
                return self.error_500 ()

            account    = self.db.account_by_uuid (account_uuid)
            self.__send_email_to_quota_reviewers (
                f"Quota request for {account_uuid}",
                "quota_request",
                email     = account['email'],
                new_quota = quota_gb,
                reason    = reason)

            return self.respond_204 ()
        except (validator.ValidationException, KeyError):
            pass

        return self.error_500 ()

    def api_v3_tags_search (self, request):
        """Implements /v3/tags/search."""

        handler = self.default_error_handling (request, "POST", "application/json")
        if handler is not None:
            return handler

        try:
            parameters = request.get_json()
            search = validator.string_value (parameters, "search_for", 0, 32, required=True, strip_html=False)
            tags = self.db.previously_used_tags (search)
            tags = list(map (lambda item: item["tag"], tags))
            return self.response (json.dumps (tags))
        except (validator.ValidationException, KeyError):
            pass

        return self.error_500 ()

    def api_v3_explore_types (self, request):
        """Implements /v3/explore/types."""

        handler = self.default_authenticated_error_handling (request, "GET", "application/json",
                                                             self.db.may_administer)
        if isinstance (handler, Response):
            return handler

        types = self.db.types ()
        types = list(map (lambda item: item["type"], types))
        return self.response (json.dumps(types))

    def api_v3_explore_properties (self, request):
        """Implements /v3/explore/properties."""

        handler = self.default_authenticated_error_handling (request, "GET", "application/json",
                                                             self.db.may_administer)
        if isinstance (handler, Response):
            return handler

        try:
            parameters = {}
            parameters["uri"] = self.get_parameter (request, "uri")
            uri        = validator.string_value (parameters, "uri", 0, 255)
            uri        = unquote(uri)
            properties = self.db.properties_for_type (uri)
            properties = list(map (lambda item: item["predicate"], properties))

            return self.response (json.dumps(properties))

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    def api_v3_explore_property_types (self, request):
        """Implements /v3/explore/property_value_types."""

        handler = self.default_authenticated_error_handling (request, "GET", "application/json",
                                                             self.db.may_administer)
        if isinstance (handler, Response):
            return handler

        try:
            parameters = {}
            parameters["type"]     = self.get_parameter (request, "type")
            parameters["property"] = self.get_parameter (request, "property")

            rdf_type     = validator.string_value (parameters, "type", 0, 255)
            rdf_type     = unquote(rdf_type)
            rdf_property = validator.string_value (parameters, "property", 0, 255)
            rdf_property = unquote(rdf_property)
            types        = self.db.types_for_property (rdf_type, rdf_property)
            types        = list(map (lambda item: item["type"], types))

            return self.response (json.dumps(types))

        except validator.ValidationException as error:
            return self.error_400 (request, error.message, error.code)

    def api_v3_explore_clear_cache (self, request):
        """Implements /v3/explore/clear-cache."""

        handler = self.default_authenticated_error_handling (request, "GET", "application/json",
                                                             self.db.may_administer)
        if isinstance (handler, Response):
            return handler

        self.log.info ("Invalidating explorer caches.")
        self.db.cache.invalidate_by_prefix ("explorer_properties")
        self.db.cache.invalidate_by_prefix ("explorer_types")
        self.db.cache.invalidate_by_prefix ("explorer_property_types")

        return self.respond_204 ()

    def __api_v3_admin_clear_cache (self, request, key):
        handler = self.default_authenticated_error_handling (request, "GET", "application/json",
                                                             self.db.may_administer)
        if isinstance (handler, Response):
            return handler

        self.log.info ("Invalidating %s caches.", key)
        self.db.cache.invalidate_by_prefix (key)
        return self.respond_204 ()

    def api_v3_admin_accounts_clear_cache (self, request):
        """Implements /v3/admin/accounts/clear-cache."""
        return self.__api_v3_admin_clear_cache (request, "accounts")

    def api_v3_admin_reviews_clear_cache (self, request):
        """Implements /v3/admin/reviews/clear-cache."""
        return self.__api_v3_admin_clear_cache (request, "reviews")

    def api_v3_datasets_assign_reviewer (self, request, dataset_uuid, reviewer_uuid):
        """Implements /v3/datasets/<id>/assign-reviewer/<rid>."""

        account_uuid = self.default_authenticated_error_handling (request, "PUT", "application/json")
        if isinstance (account_uuid, Response):
            return account_uuid

        if not validator.is_valid_uuid (reviewer_uuid):
            return self.error_403 (request)

        account_token = self.token_from_cookie (request, self.cookie_key)
        may_review_all = self.db.may_review (account_token)
        may_review_institution = self.db.may_review_institution (account_token)
        if not may_review_all and not may_review_institution:
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

    def api_v3_repair_md5s (self, request, container_uuid):
        """Attempts to repair the MD5 checksums for DATASET_ID."""
        token = self.token_from_cookie (request)
        if not self.db.may_administer (token):
            return self.error_403 (request)

        account_uuid = None
        try:
            dataset = self.db.datasets (container_uuid = container_uuid, is_published=False)[0]
            account_uuid = dataset["account_uuid"]
        except (IndexError, KeyError) as error:
            return self.error_500 (f"Cannot find dataset or account UUID: {error}")

        files = self.db.missing_checksummed_files_for_container (container_uuid)
        for row in files:
            file_uuid = row["file_uuid"]
            computed_md5 = None
            md5 = hashlib.new ("md5", usedforsecurity=False)
            filename = os.path.join (config.storage, f"{container_uuid}_{file_uuid}")
            with open(filename, "rb") as stream:
                for chunk in iter(lambda: stream.read(4096), b""): # pylint: disable=cell-var-from-loop
                    md5.update(chunk)
                computed_md5 = md5.hexdigest()

                self.log.info ("Generated %s for %s", computed_md5, file_uuid)
                self.db.update_file (account_uuid, file_uuid, dataset["uuid"],
                                     computed_md5 = computed_md5,
                                     filesystem_location = filename)

        return self.respond_201 ({ "message": "The MD5 sums have been regenerated."})

    def api_v3_doi_badge (self, request, dataset_id, version=None):
        """Implements /v3/datasets/<id>/doi-badge-v<version>.svg."""
        try:
            dataset = self.__dataset_by_id_or_uri (dataset_id, version=version)
            doi = dataset["container_doi"] if version is None else dataset["doi"]
            return self.__render_svg_template ("badge.svg", doi=doi, version=version,
                                               color=config.colors["primary-color"])
        except KeyError:
            pass

        return self.error_404 (request)

    def api_v3_redirect_from_ssi (self, request, container_uuid, token):
        """Implements /v3/redirect-from-ssi/<container_uuid>/<token>."""

        if request.method != "GET":
            return self.error_405 ("GET")

        if not validator.is_valid_uuid (container_uuid):
            return self.error_403 (request)

        response = redirect (f"/my/datasets/{container_uuid}/edit", code=302)
        response.set_cookie (key=self.cookie_key, value=token, secure=config.in_production)
        return response

    def api_v3_receive_from_ssi (self, request):
        """Implements /v3/receive-from-ssi."""
        if config.ssi_psk is None:
            return self.error_404 (request)

        if request.method != "PUT":
            return self.error_405 ("PUT")

        if not self.accepts_json (request):
            return self.error_406 ("application/json")

        record = request.get_json()
        if value_or_none (record, "psk") != config.ssi_psk:
            return self.error_403 (request)

        errors = []
        title       = validator.string_value (record, "title", 0, 255, True, errors)
        email       = validator.string_value (record, "email", 0, 255, True, errors)

        if errors:
            return self.error_400_list (request, errors)

        # Gather account information.
        account = self.db.account_by_email (email)
        account_uuid = None
        if account is None:
            # Create an account.
            account_uuid = self.db.insert_account (email=email)
            if not account_uuid:
                return self.error_500 (f"Failed to create account for SSI user {email}.")
            self.log.access ("Account %s created via SSI.", account_uuid) #  pylint: disable=no-member
        else:
            account_uuid = account["uuid"]

        token, _, session_uuid = self.db.insert_session (account_uuid, name="Login via SSI")
        if session_uuid is None:
            return self.error_500 (f"Failed to create a session for account {account_uuid}.")
        self.log.access ("Created session %s for account %s.", session_uuid, account_uuid) #  pylint: disable=no-member

        container_uuid, _ = self.db.insert_dataset (
            title = title,
            account_uuid = account_uuid)
        if container_uuid is None:
            return self.error_500 (f"Failed to create dataset for account {account_uuid}.")

        response = redirect (f"{config.base_url}/v3/redirect-from-ssi/{container_uuid}/{token}", code=302)
        return response

    ## ------------------------------------------------------------------------
    ## EXPORTS
    ## ------------------------------------------------------------------------

    def __metadata_export_parameters (self, item_id, version=None, item_type="dataset", from_draft=False):
        """Collect parameters for various export formats."""

        container_uuid = item_id
        if parses_to_int (item_id):
            container_uuid = self.db.container_uuid_by_id(item_id)
        elif not validator.is_valid_uuid (item_id):
            return None

        is_dataset = item_type == "dataset"
        items_function = self.db.collections
        if is_dataset:
            items_function = self.db.datasets
        container = self.db.container(container_uuid, item_type=item_type, use_cache=bool(version))
        current_version = version
        if not version:
            current_version = value_or(container, 'latest_published_version_number', 0)
            if from_draft:
                current_version += 1

        item = None
        published_date = None
        if from_draft:
            try:
                item = items_function (container_uuid=container_uuid,
                                       is_published=False)[0]
                item['version'] = current_version
            except IndexError:
                self.log.warning ("No draft for %s.", item_id)
            published_date = date.today().isoformat()
        else:
            try:
                item = items_function (container_uuid=container_uuid,
                                       version=current_version,
                                       is_published=True)[0]
                if item is not None and "published_date" in item:
                    published_date = item['published_date'][:10]
            except IndexError:
                self.log.warning ("Nothing found for %s %s version %s.",
                                  item_type, item_id, current_version)

        if item is None:
            return None

        item_uuid = item['uuid']
        item_uri = f'{item_type}:{item_uuid}'
        lat = self_or_value_or_none(item, 'latitude')
        lon = self_or_value_or_none(item, 'longitude')
        lat_valid, lon_valid = decimal_coords(lat, lon)
        coordinates = {'lat_valid': lat_valid, 'lon_valid': lon_valid}

        ## In the curious case when item['doi'] is an empty string, it might
        ## as well be unset.  In such cases we can fall back to the predicted
        ## DOI generated by __standard_doi().
        doi = value_or_none (item, 'doi')
        if not bool(doi):
            doi = self.__standard_doi (container_uuid, version,
                                       value_or_none (container, "doi"))
            self.log.info ("Using predicted DOI (%s) for %s.", doi, item_uri)

        parameters = {
            'item'          : item,
            'container_doi' : value_or_none (container, "doi"),
            'doi'           : doi,
            'authors'       : self.db.authors(item_uri=item_uri, item_type=item_type),
            'categories'    : self.db.categories(item_uri=item_uri, limit=None),
            'tags'          : [tag['tag'] for tag in self.db.tags(item_uri=item_uri)],
            'published_year': published_date[:4] if published_date is not None else None,
            'published_date': published_date,
            'organizations' : self.parse_organizations(value_or(item, 'organizations', '')),
            'contributors'  : self.parse_contributors (value_or(item, 'contributors' , '')),
            'references'    : self.db.references(item_uri=item_uri, limit=None),
            'coordinates'   : coordinates
            }
        if is_dataset:
            parameters['fundings'] = self.db.fundings(item_uri=item_uri)
        return parameters

    def ui_export_citation (self, request, citation_format, item_type, item_id, version=None):
        """Implements /export/<citation_format>/<item_type>s/<id>[/<version>]."""

        if item_type not in ["dataset", "collection"]:
            return self.error_404 (request)

        if citation_format in ["datacite", "refworks", "nlm", "dc"]:
            if not self.accepts_xml (request):
                return self.error_406 ("application/xml")

        if citation_format in ["bibtex", "refman", "endnote", "cff"]:
            if not self.accepts_plain_text (request):
                return self.error_406 ("text/plain")

        parameters = self.__metadata_export_parameters (item_id, version, item_type=item_type)
        if parameters is None:
            return self.error_404 (request)

        if "authors" in parameters:
            for author in parameters["authors"]:
                if "full_name" not in author:
                    author["full_name"] = ""
                    self.log.warning ("full_name is missing for author %s.", author["uuid"])
                if not ("first_name" in author or "last_name" in author):
                    parts = split_author_name (author["full_name"])
                    author["first_name"] = parts[0]
                    author["last_name"]  = parts[1]

        version_string = f"_v{version}" if version else ""
        procedure = getattr (self, f"export_{citation_format}")
        return procedure (request, parameters, item_id, version_string)

    def export_datacite (self, request, parameters, item_id, version_string):
        """export metadata in datacite format"""
        xml_string = xml_formatter.datacite (parameters, indent=True)
        if xml_string is None:
            return self.error_404 (request)
        output = self.response (xml_string, mimetype="application/xml")
        output.headers["Content-disposition"] = f"attachment; filename={item_id}{version_string}_datacite.xml"
        return output

    def export_refworks (self, request, parameters, item_id, version_string):
        """export metadata in Refworks format"""
        xml_string = xml_formatter.refworks (parameters)
        if xml_string is None:
            return self.error_404 (request)
        output = self.response (xml_string, mimetype="application/xml")
        output.headers["Content-disposition"] = f"attachment; filename={item_id}{version_string}_refworks.xml"
        return output

    def export_nlm (self, request, parameters, item_id, version_string):
        """export metadata in NLM format"""
        xml_string = xml_formatter.nlm (parameters)
        if xml_string is None:
            return self.error_404 (request)
        output = self.response (xml_string, mimetype="application/xml")
        output.headers["Content-disposition"] = f"attachment; filename={item_id}{version_string}_nlm.xml"
        return output

    def export_dc (self, request, parameters, item_id, version_string):
        """export metadata in Dublin Core format"""
        xml_string = xml_formatter.dublincore (parameters)
        if xml_string is None:
            return self.error_404 (request)
        output = self.response (xml_string, mimetype="application/xml")
        output.headers["Content-disposition"] = f"attachment; filename={item_id}{version_string}_dublincore.xml"
        return output

    def export_bibtex (self, request, parameters, item_id, version_string):  # pylint: disable=unused-argument
        """export metadata in bibtex format"""
        parameters["authors_str"] = " and ".join([f"{author['last_name']}, {author['first_name']}"
                                                  for author in parameters["authors"]])
        parameters["tags_str"] = ', '.join(parameters["tags"])
        headers = {"Content-disposition": f"attachment; filename={item_id}{version_string}.bib"}
        return self.__render_export_format (template_name = "bibtex.bib",
                                            mimetype      = "text/plain",
                                            headers       = headers,
                                            **parameters)

    def export_refman (self, request, parameters, item_id, version_string):  # pylint: disable=unused-argument
        """export metadata in .ris format"""

        if parameters["published_date"] is not None:
            parameters['published_date'] = parameters['published_date'].replace('-', '/')

        headers = {"Content-disposition": f"attachment; filename={item_id}{version_string}.ris"}
        return self.__render_export_format (template_name = "refman.ris",
                                            mimetype      = "text/plain",
                                            headers       = headers,
                                            **parameters)

    def export_endnote (self, request, parameters, item_id, version_string):  # pylint: disable=unused-argument
        """export metadata in .enw format"""

        parameters["reference_type"] = "Generic"
        if parameters["item"]["defined_type_name"] == "software":
            parameters["reference_type"] = "Computer Program"

        headers = {"Content-disposition": f"attachment; filename={item_id}{version_string}.enw"}
        return self.__render_export_format (template_name = "endnote.enw",
                                            mimetype      = "text/plain",
                                            headers       = headers,
                                            **parameters)

    def export_cff (self, request, parameters, item_id, version_string):  # pylint: disable=unused-argument
        """export metadata in citation file format"""

        headers = {"Content-disposition": f"attachment; filename={item_id}{version_string}.cff"}
        return self.__render_export_format (template_name = "citation.cff",
                                            mimetype       = "text/plain",
                                            headers        = headers,
                                            **parameters)

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

    def parse_search_terms (self, search_for):
        """Procedure to parse search terms and operators in a string"""
        if not isinstance(search_for, str):
            return search_for

        search_for = search_for.strip()
        operators_mapping = {"(":"(", ")":")", "AND":"&&", "OR":"||"}
        operators = operators_mapping.keys()

        fields = ["title", "resource_title", "description",
                  "format", "tag", "organizations"]
        re_field = ":(" + "|".join(fields+["search_term"]) + "):"

        search_tokens = re.findall(r'[^" ]+|"[^"]+"|\([^)]+\)', search_for)
        search_tokens = [s.strip('"') for s in search_tokens]
        has_operators = any((operator in search_for) for operator in operators)
        has_fieldsearch = re.search(re_field, search_for) is not None

        # Concatenate field name and its following token as one token.
        for idx, token in enumerate(search_tokens):
            if token is None:
                continue
            if re.search(re_field, token) is not None:
                matched = re.split(':', token)[1::2][0]
                if matched in fields:
                    try:
                        search_tokens[idx] = f"{token} {search_tokens[idx+1]}"
                        search_tokens[idx+1] = None
                    except IndexError:
                        return search_for

        search_tokens = [x for x in search_tokens if x is not None]

        ## Unpacking this construction to replace AND and OR for &&
        ## and || results in a query where && is stripped out.
        if has_operators:
            is_parenthesized = False
            lparen_count = search_tokens.count("(")
            rparen_count = search_tokens.count(")")
            if lparen_count > 0 and lparen_count == rparen_count:
                is_parenthesized = True
            for idx, element in enumerate(search_tokens):
                if element in operators:
                    if element in ['(', ')'] and not is_parenthesized:
                        continue
                    search_tokens[idx] = {"operator": operators_mapping[element]}
        else:
            # No operators found in the search query. Adding OR operators.
            index = -1
            while len(search_tokens) + index > 0:
                search_tokens.insert(index, {"operator": "||"})
                index = index - 2

        for idx, search_term in enumerate(search_tokens):
            if isinstance(search_term, dict):
                continue

            if re.search(re_field, search_term) is not None:
                field_name = re.split(':', search_term)[1::2][0]
                value = list(filter(None, [s.strip() for s in re.split(':', search_term)[0::2]]))[0]

                if field_name in fields:
                    search_tokens[idx] = {field_name: value}
                elif field_name == "search_term":
                    search_dict = {}
                    for field_name in fields:
                        search_dict[field_name] = value
                    search_tokens[idx] = search_dict

                field_name = None

            elif has_fieldsearch is False:
                search_dict = {}
                for field in fields:
                    search_dict[field] = search_term
                search_tokens[idx] = search_dict

        return search_tokens

    ## ------------------------------------------------------------------------
    ## IIIF
    ## ------------------------------------------------------------------------

    def iiif_v3_image_context_redirect (self, request, file_uuid):
        """Implements /iiif/v3/<uuid>."""

        if not config.enable_iiif:
            return self.error_404 (request)

        if not validator.is_valid_uuid (file_uuid):
            return self.error_400 (request, "Invalid file UUID.", "InvalidFileUUID")

        metadata = self.db.dataset_files (file_uuid = file_uuid)
        if not metadata:
            return self.error_404 (request)

        return redirect (f"{config.base_url}/iiif/v3/{file_uuid}/info.json", code=303)

    def iiif_v3_image_context (self, request, file_uuid):
        """Implements /iiif/v3/<uuid>/info.json."""

        if not config.enable_iiif:
            return self.error_404 (request)

        if not validator.is_valid_uuid (file_uuid):
            return self.error_400 (request, "Invalid file UUID.", "InvalidFileUUID")

        metadata = self.db.dataset_files (file_uuid = file_uuid)
        if not metadata:
            return self.error_404 (request)

        try:
            image_info = metadata[0]
            input_filename = self.__filesystem_location (image_info)
            image  = pyvips.Image.new_from_file (input_filename)
            output = {
                "@context":  "http://iiif.io/api/image/3/context.json",
                "id":        f"{config.base_url}/iiif/v3/{file_uuid}",
                "type":      "ImageService3",
                "protocol":  "http://iiif.io/api/image",
                "profile":   "level1",
                "width":     image.width,
                "height":    image.height,
                "maxWidth":  image.width,                # Optional
                "maxHeight": image.height,               # Optional
                "maxArea":   image.width * image.height, # Optional
                "extraFormats": ["jpg", "png", "tif", "webp"],
                "extraFeatures": ["cors", "mirroring", "regionByPx",
                                  "regionSquare", "rotationArbitrary",
                                  "rotationBy90s"],
                "sizes": [{ "width": image.width, "height": image.height }]
            }
            del image
            response = self.response (json.dumps (output),
                                      mimetype=('application/ld+json;profile='
                                                '"http://iiif.io/api/image/3/'
                                                'context.json"'))
            response.headers["Access-Control-Allow-Origin"] = "*"
            return response
        except IndexError:
            self.log.error ("Unable to read metadata.")
        except (KeyError, FileNotFoundError, UnidentifiedImageError):
            self.log.error ("Unable to open image file %s.", file_uuid)
        except pyvips.error.Error as error:
            if "is not a known file format" in str(error):
                supported_formats   = ["jpg", "png", "tif", "webp"]
                filename = metadata[0]["name"]
                return self.error_400 (request,
                                       (f"'{filename}' is not a supported "
                                        "image. The following formats are "
                                        f"supported: {supported_formats}."),
                                       "InvalidImageFormat")
            self.log.error ("Pyvips reported: %s", error)

        return self.error_500 ()

    def iiif_v3_image (self, request, file_uuid, region, size, rotation, quality, image_format):
        """Implements /iiif/v3/<uuid>/<region>/<size>/<rotation>/<quality>.<format>."""

        if not config.enable_iiif:
            return self.error_404 (request)

        if not validator.is_valid_uuid (file_uuid):
            return self.error_400 (request, "Invalid file UUID.", "InvalidFileUUID")

        validation_errors = []
        parameters = {
            "region": region,
            "size": size,
            "rotation": rotation,
            "quality": quality,
            "image_format": image_format
        }
        supported_qualities = ["color", "gray", "bitonal", "default"]
        supported_formats   = ["jpg", "png", "tif", "webp"]
        quality = validator.options_value (parameters, "quality", supported_qualities,
                                           required=True, error_list=validation_errors)

        image_format = validator.options_value (parameters, "image_format", supported_formats,
                                                required=True, error_list=validation_errors)

        metadata = self.db.dataset_files (file_uuid = file_uuid)
        if not metadata:
            return self.error_404 (request)

        metadata = metadata[0]
        input_filename = self.__filesystem_location (metadata)
        original  = pyvips.Image.new_from_file (input_filename)

        # Region
        output_region = { "x": 0, "y": 0, "w": original.width, "h": original.height }
        if region == "square":
            shortest = min (original.width, original.height)
            output_region["w"] = shortest
            output_region["h"] = shortest

        elif region.startswith("pct:"):
            # To-do: implement percentage-wise translation.
            validation_errors.append ({
                "field_name": "region",
                "message": "Percentage-wise regions are not implemented."
            })

        # Attempt to parse the x,y,w,h format
        if validator.index_exists (region, 255):
            validation_errors.append ({
                "field_name": "region",
                "message": "The region is too long"
            })
        elif region not in ("full", "square"):
            deconstructed = region.split (",")
            if len(deconstructed) != 4:
                validation_errors.append ({
                    "field_name": "region",
                    "message": "The region format should be 'x,y,w,h'."
                })
            else:
                output_region = { "x": deconstructed[0], "y": deconstructed[1],
                                  "w": deconstructed[2], "h": deconstructed[3] }

        # Size
        output_size = { "w": original.width, "h": original.height }
        if size != "max" and "," not in size:
            validation_errors.append ({
                "field_name": "size",
                "message": f"Unexpected value '{size}' for size."
            })

        if "," in size:
            sizes = size.split(",")
            if len (sizes) != 2:
                validation_errors.append ({
                    "field_name": "size",
                    "message": "Expected a 'width,height' specification."
                })

            elif sizes[0].startswith("^"):
                validation_errors.append ({
                    "field_name": "size",
                    "message": "Image scaling is not supported."
                })
            elif value_or (sizes, 0, "") == "" and parses_to_int (sizes[1]):
                scale_factor = float(sizes[1]) / original.height
                output_size = { "w": original.width * scale_factor, "h": int(sizes[1]) }
            elif parses_to_int (sizes[0]) and value_or (sizes, 1, "") == "":
                scale_factor = float(sizes[0]) / original.width
                output_size = { "w": int(sizes[0]), "h": original.height * scale_factor }
            elif parses_to_int (sizes[0]) and parses_to_int (sizes[1]):
                output_size = { "w": int(sizes[0]), "h": int(sizes[1]) }

        # Rotation
        mirror      = (isinstance (rotation, str) and rotation[0] == "!")
        try:
            rotation    = int(rotation) if not mirror else int(rotation[1:])
            if rotation < 0 or rotation > 360:
                validation_errors.append ({
                    "field_name": "rotation",
                    "message": "Rotation must be a value between 0 and 360."
                })
        except ValueError:
            return self.error_400 (request, "Rotation must be an integer.",
                                   "InvalidRotationValue")

        # Error reporting
        if validation_errors:
            return self.error_400_list (request, validation_errors)

        # Serve from cache
        # ---------------------------------------------------------------------
        cache_key = self.db.cache.make_key ((f"{file_uuid}_{region}_{size}_"
                                             f"{mirror}_{rotation}_"
                                             f"{quality}_{image_format}"))
        file_path = os.path.join (config.iiif_cache_storage, cache_key)
        try:
            response = send_file (file_path, request.environ, f"image/{image_format}",
                                  as_attachment=False, download_name=None)
            response.headers["Access-Control-Allow-Origin"] = "*"
            return response
        except OSError:
            pass

        # Transform the input image to the output image
        # ---------------------------------------------------------------------
        output = None
        try:
            output = pyvips.Image.new_temp_file(format=f".{image_format}")
            original.write(output)

            output = output.crop (output_region["x"], output_region["y"],
                                  output_region["w"], output_region["h"])
            output = output.thumbnail_image (output_size["w"],
                                             height = output_size["h"],
                                             size = "force")
            if mirror:
                output = output.fliphor()
            if rotation not in (0, 360):
                output = output.similarity (angle=rotation)
            if quality == "gray":
                output = output.colourspace (pyvips.enums.Interpretation.B_W)

            # The commonly used mimetype for TIFF is image/tiff.
            if image_format == "tif":
                image_format = "tiff"

            target = pyvips.Target.new_to_file (file_path)
            output.write_to_target (target, f".{image_format}")
            response = send_file (file_path, request.environ, f"image/{image_format}",
                              as_attachment=False, download_name=None)
            response.headers["Access-Control-Allow-Origin"] = "*"
            return response
        except FileNotFoundError:
            self.log.error ("File download failed due to missing file: '%s'.", file_path)
        except pyvips.error.Error as error:
            if "is not a known file format" in str(error):
                return self.error_400 (request,
                                       (f"'{image_format}' is not a supported "
                                        "image format. The following are "
                                        f"supported: {supported_formats}."),
                                       "InvalidImageFormat")
            self.log.error ("Pyvips reported: %s", error)

        return self.error_500 ()
