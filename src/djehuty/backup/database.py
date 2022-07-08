"""This module provides an interface to store data fetched by the 'figshare' module."""

import os
import xml.etree.ElementTree as ET
import ast
import logging
from datetime import datetime
from threading import Lock
from secrets import token_urlsafe
import json
from rdflib import Graph, Literal, RDF, RDFS, XSD, URIRef
import requests
from djehuty.utils.convenience import value_or, value_or_none
from djehuty.utils import rdf

class DatabaseInterface:
    """
    A class that serializes the output produced by the 'figshare'
    module as RDF.
    """

    def __init__(self):
        self.store            = Graph()
        self.lock_for_inserts = Lock()
        self.container_uris_lock = Lock()
        self.container_uris   = {}
        script_path = os.path.dirname(os.path.abspath(__file__))
        with open(f'{script_path}/resources/dois.json', 'r',
                  encoding = 'utf-8') as dois_file:
            self.extra_dois = json.load(dois_file)
        with open(f'{script_path}/resources/contributors_organizations.json',
                  'r', encoding = 'utf-8') as contributors_file:
            extra = json.load(contributors_file)
        self.extra_contributors_organizations = {
            item_type: { pid: dict(versions) for pid, versions in extra[item_type] }
            for item_type in extra
        }

    def __get_from_url (self, url: str, headers, parameters):
        """Procedure to perform a GET request to a Figshare-compatible endpoint."""
        response = requests.get(url,
                                headers = headers,
                                params  = parameters)
        if response.status_code == 200:
            return response.text

        logging.error("%s returned %d.", url, response.status_code)
        logging.error("Error message:\n---\n%s\n---", response.text)
        return False

    def __get_file_size_for_catalog (self, url, recurse=None):
        """Returns the file size for an OPeNDAP catalog."""

        if recurse is None:
            noRecurse = ('/IDRA/', '/darelux/', '/zandmotor/meteohydro/xband/catalog', '/CF_Drinking_water/')
            recurse = not True in [noRecurseFragment in url for noRecurseFragment in noRecurse]

        total_filesize = 0
        metadata_url   = url.replace(".html", ".xml")
        metadata       = False

        try:
            metadata   = self.__get_from_url (metadata_url, {}, {})
        except requests.exceptions.ConnectionError:
            logging.error("Failed to connect to %s.", metadata_url)

        if not metadata:
            logging.error("Couldn't get file metadata for %s.", url)
            return total_filesize

        namespaces  = { "c": "http://www.unidata.ucar.edu/namespaces/thredds/InvCatalog/v1.0" }
        xml_root    = ET.fromstring(metadata)
        references  = xml_root.findall(".//c:catalogRef", namespaces)

        ## Recursively handle directories.
        if not recurse:
            logging.debug("Catalog %s is not recursed, subcatalogs are linked to other datasets.", url)
        elif not references:
            logging.debug("Catalog %s does not contain subcatalogs.", url)
        else:
            for reference in references:
                suffix = reference.attrib["{http://www.w3.org/1999/xlink}href"]
                suburl = metadata_url.replace("catalog.xml", suffix)
                total_filesize += self.__get_file_size_for_catalog (suburl, recurse=True)

        ## Handle regular files.
        files          = xml_root.findall(".//c:dataSize", namespaces)
        if not files:
            if total_filesize == 0:
                logging.debug ("There are no files in %s.", url)
            return total_filesize

        for file in files:
            units = file.attrib["units"]
            size  = ast.literal_eval(file.text)
            if units == "Tbytes":
                size = size * 1000000000000
            elif units == "Gbytes":
                size = size * 1000000000
            elif units == "Mbytes":
                size = size * 1000000
            elif units == "Kbytes":
                size = size * 1000

            total_filesize += size

        return total_filesize

    def record_uri (self, record_type, identifier_name, identifier):
        """
        Returns the URI for a record identified with IDENTIFIER_NAME and by
        IDENTIFIER or None if no such URI can be found.
        """
        if identifier is None:
            return None

        if isinstance(identifier, str):
            identifier = f"\"{identifier}\"^^<{str(XSD.string)}>"

        try:
            query    = (
                "SELECT ?uri WHERE { "
                f"?uri <{str(RDF.type)}> <{str(rdf.SG[record_type])}> ; "
                f"<{str(rdf.COL[identifier_name])}> {identifier} . }}"
            )

            results = self.store.query (query)
            return results.bindings[0]["uri"]
        except KeyError:
            pass
        except IndexError:
            pass

        return None

    def serialize (self):
        """Output the triplets in the graph  to stdout."""
        body = self.store.serialize(format="turtle")
        if isinstance(body, bytes):
            body = body.decode('utf-8')

        print(body)

    def insert_account (self, record):
        """Procedure to add an account record to GRAPH."""

        uri = rdf.unique_node ("account")
        self.lock_for_inserts.acquire()
        self.store.add ((uri, RDF.type, rdf.SG["Account"]))

        institution_user_id = value_or (record, "institution_user_id", None)
        domain              = None
        if institution_user_id is not None:
            domain = institution_user_id.partition("@")[2]

        rdf.add (self.store, uri, rdf.COL["id"],                    value_or (record, "id", None),           XSD.integer)
        rdf.add (self.store, uri, rdf.COL["active"],                value_or (record, "active", False),      XSD.boolean)
        rdf.add (self.store, uri, rdf.COL["domain"],                domain,                                  XSD.string)
        rdf.add (self.store, uri, rdf.COL["email"],                 value_or (record, "email", None),        XSD.string)
        rdf.add (self.store, uri, rdf.COL["first_name"],            value_or (record, "first_name", None),   XSD.string)
        rdf.add (self.store, uri, rdf.COL["last_name"],             value_or (record, "last_name", None),    XSD.string)
        rdf.add (self.store, uri, rdf.COL["institution_user_id"],   institution_user_id,                     XSD.string)
        rdf.add (self.store, uri, rdf.COL["institution_id"],        value_or (record, "institution_id", None))
        rdf.add (self.store, uri, rdf.COL["group_id"],              value_or (record, "group_id", None))
        rdf.add (self.store, uri, rdf.COL["pending_quota_request"], value_or (record, "pending_quota_request", None))
        rdf.add (self.store, uri, rdf.COL["used_quota_public"],     value_or (record, "used_quota_public", None))
        rdf.add (self.store, uri, rdf.COL["used_quota_private"],    value_or (record, "used_quota_private", None))
        rdf.add (self.store, uri, rdf.COL["used_quota"],            value_or (record, "used_quota", None))
        rdf.add (self.store, uri, rdf.COL["maximum_file_size"],     value_or (record, "maximum_file_size", None))
        rdf.add (self.store, uri, rdf.COL["quota"],                 value_or (record, "quota", None))
        rdf.add (self.store, uri, rdf.COL["modified_date"],         value_or_none (record, "modified_date"), XSD.dateTime)
        rdf.add (self.store, uri, rdf.COL["created_date"],          value_or_none (record, "created_date"),  XSD.dateTime)

        self.lock_for_inserts.release()
        return True

    def insert_institution (self, record):
        """Procedure to insert an institution record."""

        try:
            institution_id = record["institution_id"]
            uri            = rdf.ROW[f"institution_{institution_id}"]

            self.store.add ((uri, RDF.type,        rdf.SG["Institution"]))
            self.store.add ((uri, rdf.COL["id"],   Literal(institution_id, datatype=XSD.integer)))
            self.store.add ((uri, rdf.COL["name"], Literal(record["name"], datatype=XSD.string)))

            return True

        except KeyError:
            pass

        logging.error ("Failed to insert Institution record: %s", record)
        return False

    def insert_author (self, record):
        """Procedure to insert an author record."""

        author_id = value_or_none (record, "id")
        if author_id is None:
            logging.error ("Invalid author record: %s", record)
            return None
        uri = self.record_uri ("Author", "id", author_id)
        if uri is not None:
            return uri

        uri       = rdf.unique_node ("author")
        is_active = "is_active" in record and record["is_active"]
        is_public = "is_public" in record and record["is_public"]

        self.store.add ((uri, RDF.type, rdf.SG["Author"]))

        rdf.add (self.store, uri, rdf.COL["id"],             author_id,                                 XSD.integer)
        rdf.add (self.store, uri, rdf.COL["institution_id"], value_or (record, "institution_id", None), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["group_id"],       value_or (record, "group_id",       None), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["first_name"],     value_or (record, "first_name",     None), XSD.string)
        rdf.add (self.store, uri, rdf.COL["last_name"],      value_or (record, "last_name",      None), XSD.string)
        rdf.add (self.store, uri, rdf.COL["full_name"],      value_or (record, "full_name",      None), XSD.string)
        rdf.add (self.store, uri, rdf.COL["job_title"],      value_or (record, "job_title",      None), XSD.string)
        rdf.add (self.store, uri, rdf.COL["url_name"],       value_or (record, "url_name",       None), XSD.string)
        rdf.add (self.store, uri, rdf.COL["orcid_id"],       value_or (record, "orcid_id",       None), XSD.string)
        rdf.add (self.store, uri, rdf.COL["is_active"],      is_active,                                 XSD.boolean)
        rdf.add (self.store, uri, rdf.COL["is_public"],      is_public,                                 XSD.boolean)

        return uri

    def insert_timeline (self, uri, record):
        """Procedure to insert a timeline record."""

        if not record:
            return False

        rdf.add (self.store, uri, rdf.COL["revision_date"],     value_or_none (record, "revision"),             XSD.dateTime)
        rdf.add (self.store, uri, rdf.COL["publisher_publication_date"], value_or_none (record, "publisherPublication"), XSD.dateTime)
        rdf.add (self.store, uri, rdf.COL["publisher_acceptance_date"], value_or_none (record, "publisherAcceptance"), XSD.dateTime)
        rdf.add (self.store, uri, rdf.COL["posted_date"],       value_or_none (record, "posted"),               XSD.dateTime)
        rdf.add (self.store, uri, rdf.COL["submission_date"],   value_or_none (record, "submission"),           XSD.dateTime)

        return True

    def insert_category (self, record):
        """Procedure to insert a category record."""

        category_id = value_or_none (record, "id")
        uri = self.record_uri ("Category", "id", category_id)
        if uri is not None:
            return uri

        uri = rdf.unique_node ("category")
        self.store.add ((uri, RDF.type,      rdf.SG["Category"]))
        self.store.add ((uri, rdf.COL["id"], Literal(category_id)))

        rdf.add (self.store, uri, rdf.COL["title"],       value_or (record, "title", None),       XSD.string)
        rdf.add (self.store, uri, rdf.COL["parent_id"],   value_or (record, "parent_id", None),   XSD.integer)
        rdf.add (self.store, uri, rdf.COL["source_id"],   value_or (record, "source_id", None),   XSD.integer)
        rdf.add (self.store, uri, rdf.COL["taxonomy_id"], value_or (record, "taxonomy_id", None), XSD.integer)

        return uri

    def insert_record_list (self, uri, records, name, insert_procedure):
        """
        Adds an RDF list with indexes for RECORDS to the graph using
        INSERT_PROCEDURE.  The INSERT_PROCEDURE must take  a single item
        from RECORDS, and it must return the URI used as subject to describe
        the record.
        """
        if records:
            blank_node = rdf.blank_node ()
            self.store.add ((uri, rdf.COL[name], blank_node))

            previous_blank_node = None
            for index, item in enumerate(records):
                record_uri = insert_procedure (item)
                self.store.add ((blank_node, rdf.COL["index"], Literal (index, datatype=XSD.integer)))
                self.store.add ((blank_node, RDF.first,        record_uri))

                if previous_blank_node is not None:
                    self.store.add ((previous_blank_node, RDF.rest, blank_node))
                    self.store.add ((previous_blank_node, RDF.type, RDF.List))

                previous_blank_node = blank_node
                blank_node = rdf.blank_node ()

            del blank_node
            self.store.add ((previous_blank_node, RDF.rest, RDF.nil))
            self.store.add ((previous_blank_node, RDF.type, RDF.List))

    def insert_category_list (self, uri, categories):
        """Adds an RDF list with indexes for CATEGORIES to GRAPH."""
        self.insert_record_list (uri, categories, "categories", self.insert_category)

    def insert_author_list (self, uri, authors):
        """Adds an RDF list with indexes for AUTHORS to GRAPH."""
        self.insert_record_list (uri, authors, "authors", self.insert_author)

    def insert_file_list (self, uri, files):
        """Adds an RDF list with indexes for FILES to GRAPH."""
        self.insert_record_list (uri, files, "files", self.insert_file)

    def insert_funding_list (self, uri, records):
        """Adds an RDF list with indexes for FUNDINGS to GRAPH."""
        self.insert_record_list (uri, records, "funding_list", self.insert_funding)

    def insert_private_links_list (self, uri, records):
        """Adds an RDF list with indexes for PRIVATE_LINKS to GRAPH."""
        self.insert_record_list (uri, records, "private_links", self.insert_private_link)

    def insert_embargo_list (self, uri, records):
        """Adds an RDF list with indexes for EMBARGOS to GRAPH."""
        self.insert_record_list (uri, records, "embargos", self.insert_embargo)

    def insert_item_list (self, uri, items, items_name):
        """Adds an RDF list with indexes for ITEMS to GRAPH."""

        if items:
            blank_node = rdf.blank_node ()
            self.store.add ((uri, rdf.COL[items_name], blank_node))

            previous_blank_node = None
            for index, item in enumerate(items):
                self.store.add ((blank_node, rdf.COL["index"], Literal (index, datatype=XSD.integer)))
                if isinstance (item, URIRef):
                    self.store.add ((blank_node, RDF.first,        item))
                else:
                    self.store.add ((blank_node, RDF.first,        Literal (item,  datatype=XSD.string)))

                if previous_blank_node is not None:
                    self.store.add ((previous_blank_node, RDF.rest, blank_node))
                    self.store.add ((previous_blank_node, RDF.type, RDF.List))

                previous_blank_node = blank_node
                blank_node = rdf.blank_node ()

            del blank_node
            self.store.add ((previous_blank_node, RDF.rest, RDF.nil))
            self.store.add ((previous_blank_node, RDF.type, RDF.List))

    def insert_custom_field_value (self, uri, name, value, field_type):
        """Insert a single NAME-VALUE pair for URI into GRAPH."""

        # Custom fields can be either text or URLs.
        # URLs should be converted to URIRefs, while all other
        # cases should be considered text strings.
        if field_type != "url":
            field_type = XSD.string

        if isinstance (value, list):
            for item in value:
                if isinstance (item, str) and item == "":
                    continue
                rdf.add (self.store, uri, rdf.COL[name], item, field_type)

        elif not (isinstance (value, str) and value == ""):
            rdf.add (self.store, uri, rdf.COL[name], value, field_type)

    def insert_custom_field (self, uri, field):
        """Procedure to insert a custom_field record."""

        name        = field["name"].lower().replace(" ", "_")

        ## Exceptions to the custom field names.
        if name == "licence_remarks":
            name = "license_remarks"
        if name == "geolocation_latitude":
            name = "latitude"
        if name == "geolocation_longitude":
            name = "longitude"

        settings    = {}
        validations = {}
        if "settings" in field:
            settings = field["settings"]
            if "validations" in settings:
                validations = settings["validations"]

        default_value = None
        if "default_value" in settings:
            default_value = settings["default_value"]

        ## Avoid inserting the custom field's properties multiple times.
        subjects = self.store.subjects ((None, RDF.type, rdf.SG["CustomField"]),
                                        (None, rdf.COL["name"], Literal(name, datatype=XSD.string)))
        field_uri = next (subjects, None)
        if field_uri is None:
            field_uri = rdf.ROW[f"custom_field_{name}"]
            self.store.add ((field_uri,     RDF.type,                rdf.SG["CustomField"]))
            rdf.add (self.store, field_uri, rdf.COL["predicate"],    rdf.COL[name], datatype="url")
            rdf.add (self.store, field_uri, rdf.COL["name"],         name,                                        XSD.string)
            rdf.add (self.store, field_uri, rdf.COL["original_name"], field["name"],                              XSD.string)
            rdf.add (self.store, field_uri, rdf.COL["max_length"],   value_or_none (validations, "max_length"))
            rdf.add (self.store, field_uri, rdf.COL["min_length"],   value_or_none (validations, "min_length"))
            rdf.add (self.store, field_uri, rdf.COL["is_mandatory"], value_or_none (validations, "is_mandatory"), XSD.boolean)
            rdf.add (self.store, field_uri, rdf.COL["placeholder"],  value_or_none (validations, "placeholder"),  XSD.string)
            rdf.add (self.store, field_uri, rdf.COL["is_multiple"],  value_or_none (validations, "is_multiple"),  XSD.boolean)

        if isinstance(field["value"], list):
            for value in field["value"]:
                value      = value_or (field, "value", default_value)
                field_type = value_or_none (field, "field_type")
                self.insert_custom_field_value (uri, name, value, field_type)

                ## Drop-down lists have predefined items to choose from.
                ## We must add those predefined items once to the RDF store.
                if field_type == "dropdown" and value_or (settings, "options", False):
                    options_uri = self.record_uri ("CustomFieldOption", "name", name)
                    if options_uri is None:
                        options_uri = rdf.ROW[f"custom_field_options_{name}"]
                        options     = value_or_none (settings, "options")
                        rdf.add (self.store, options_uri, rdf.COL["name"], name, XSD.string)
                        self.insert_item_list (options_uri, options, "values")
        else:
            value      = value_or (field, "value", default_value)
            field_type = value_or_none (field, "field_type")
            self.insert_custom_field_value (uri, name, value, field_type)

    def fix_doi (self, record, item_id, version, item_type):
        '''Fix doi if needed'''
        extra_dois = [extra['doi'] for extra in self.extra_dois[item_type] if extra['id']==item_id and extra['version']==version]
        if extra_dois:
            record['doi'] = extra_dois[0]

    def handle_custom_fields (self, record, uri, item_id, version, item_type):
        '''Handle custom fields and fix contributors/organizations if needed'''
        #TODO: add "Data Link Size" field for opendap catalogs in "Data Link" field (use self.__get_file_size_for_catalog)
        for field in value_or (record, "custom_fields", []):
            if field['name'] == 'Contributors':
                try:
                    #replace contributors by organizations and (optional) contributors
                    extra = self.extra_contributors_organizations[item_type][item_id][version]
                    contributors  = extra['contributors']
                    if contributors:
                        field['value'] = contributors
                        self.insert_custom_field (uri, field)
                    field = {'name': 'Organizations', 'value': extra['organizations']}
                except KeyError:
                    pass

            self.insert_custom_field (uri, field)

    def insert_collection (self, record, account_id):
        """Procedure to insert a collection record."""

        collection_id  = record["id"]
        uri            = rdf.unique_node ("collection")

        is_public          = bool (value_or (record, "public", False))
        is_latest          = bool (value_or (record, "is_latest", False))
        is_editable        = bool (value_or (record, "is_editable", False))

        version = value_or_none(record, "version")
        self.fix_doi (record, collection_id, version, 'collection')

        self.lock_for_inserts.acquire()
        self.store.add ((uri, RDF.type,                 rdf.SG["Collection"]))
        self.store.add ((uri, rdf.COL["collection_id"], Literal(collection_id, datatype=XSD.integer)))

        rdf.add (self.store, uri, rdf.COL["url"],                 value_or_none (record, "url"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["title"],               value_or_none (record, "title"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["published_date"],      value_or_none (record, "published_date"), XSD.dateTime)
        rdf.add (self.store, uri, rdf.COL["created_date"],        value_or_none (record, "created_date"), XSD.dateTime)
        rdf.add (self.store, uri, rdf.COL["modified_date"],       value_or_none (record, "modified_date"), XSD.dateTime)
        rdf.add (self.store, uri, rdf.COL["doi"],                 value_or_none (record, "doi"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["citation"],            value_or_none (record, "citation"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["group_id"],            value_or_none (record, "group_id"), XSD.integer)
        ## group_resource_id is always empty/NULL.
        #rdf.add (self.store, uri, rdf.COL["group_resource_id"],   value_or_none (record, "group_resource_id"), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["institution_id"],      value_or_none (record, "institution_id"), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["description"],         value_or_none (record, "description"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["version"],             value_or_none (record, "version"), XSD.integer)
        ## resource_id is always empty/NULL.
        #rdf.add (self.store, uri, rdf.COL["resource_id"],         value_or_none (record, "resource_id"), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["resource_doi"],        value_or_none (record, "resource_doi"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["resource_title"],      value_or_none (record, "resource_title"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["resource_version"],    value_or_none (record, "resource_version"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["resource_link"],       value_or_none (record, "resource_link"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["handle"],              value_or_none (record, "handle"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["is_public"],           is_public, XSD.boolean)
        rdf.add (self.store, uri, rdf.COL["is_latest"],           is_latest, XSD.boolean)
        rdf.add (self.store, uri, rdf.COL["is_editable"],         is_editable, XSD.boolean)

        self.insert_timeline (uri, value_or_none (record, "timeline"))
        self.insert_author_list (uri, value_or (record, "authors", []))
        self.insert_category_list (uri, value_or (record, "categories", []))
        self.insert_funding_list (uri, value_or (record, "funding_list", []))
        self.insert_private_links_list (uri, value_or (record, "private_links", []))
        self.insert_item_list (uri, value_or (record, "tags", []), "tags")
        self.insert_item_list (uri, value_or (record, "references", []), "references")

        self.handle_custom_fields (record, uri, collection_id, version, 'collections')

        articles = value_or (record, "articles", [])
        if articles:
            for index, article_id in enumerate (articles):
                article_uri = self.record_uri ("ArticleContainer", "article_id", article_id)
                if article_uri is None:
                    logging.error ("Could not find article container for %d", article_id)
                    continue

                articles[index] = URIRef (article_uri)

            self.insert_item_list (uri, articles, "articles")
        else:
            logging.warning ("Collection %d seems to be empty.", collection_id)

        ## Assign the collection to the container
        container = self.container_uri (collection_id, "collection", account_id)
        rdf.add (self.store, uri, rdf.COL["container"], container, datatype="uri")

        if "statistics" in record:
            stats = record["statistics"]
            self.insert_totals_statistics (stats["totals"], container)
        elif is_public and is_latest:
            logging.warning ("No statistics available for collection %d.", collection_id)

        if is_editable:
            self.store.add ((container, rdf.COL["draft"], uri))
        else:
            new_blank_node = rdf.blank_node ()
            self.store.add ((new_blank_node, RDF.type, RDF.List))
            self.store.add ((new_blank_node, RDF.first, uri))
            self.store.add ((new_blank_node, RDF.rest, RDF.nil))

            blank_node = self.last_list_node (container, "published_versions")
            if blank_node is None:
                self.store.add    ((container, rdf.COL["published_versions"], new_blank_node))
            else:
                self.store.remove ((blank_node, RDF.rest, RDF.nil))
                self.store.add    ((blank_node, RDF.rest, new_blank_node))

        if is_latest:
            self.store.add ((container, rdf.COL["latest_published_version"], uri))
            timeline = value_or_none (record, "timeline")
            rdf.add (self.store, container, rdf.COL["first_online_date"],
                     value_or_none (timeline, "firstOnline"), XSD.dateTime)

        self.lock_for_inserts.release()
        return True

    def insert_funding (self, record):
        """Procedure to insert a funding record."""

        funding_id = value_or_none (record, "id")
        uri = self.record_uri ("Funding", "id", funding_id)
        if uri is not None:
            return uri

        is_user_defined = value_or (record, "is_user_defined", False)

        uri = rdf.unique_node ("funding")
        self.store.add ((uri, RDF.type, rdf.SG["Funding"]))
        rdf.add (self.store, uri, rdf.COL["id"],              funding_id, XSD.integer)
        rdf.add (self.store, uri, rdf.COL["title"],           value_or_none (record, "title"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["grant_code"],      value_or_none (record, "grant_code"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["funder_name"],     value_or_none (record, "funder_name"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["url"],             value_or_none (record, "url"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["is_user_defined"], is_user_defined, XSD.boolean)

        return uri

    def insert_private_link (self, record):
        """Procedure to insert a private link to an article or a collection."""

        is_active = value_or (record, "is_active", False)
        suffix    = token_urlsafe (64)
        uri       = rdf.unique_node ("private_link")

        self.store.add ((uri, RDF.type, rdf.SG["PrivateLink"]))
        rdf.add (self.store, uri, rdf.COL["id"],           value_or_none (record, "id"), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["suffix"],       suffix, XSD.string)
        rdf.add (self.store, uri, rdf.COL["expires_date"], value_or_none (record, "expires_date"), XSD.dateTime)
        rdf.add (self.store, uri, rdf.COL["is_active"],    is_active, XSD.boolean)

        return uri

    def insert_embargo (self, record):
        """Procedure to insert an embargo record."""

        uri = rdf.unique_node ("embargo")
        self.store.add ((uri, RDF.type, rdf.SG["Embargo"]))
        rdf.add (self.store, uri, rdf.COL["id"],      value_or_none (record, "id"), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["type"],    value_or_none (record, "type"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["ip_name"], value_or_none (record, "ip_name"), XSD.string)

        return uri

    def insert_license (self, uri, record):
        """Procedure to insert a license record."""

        if not (record and value_or (record, "url", False)):
            return False

        license_uri  = URIRef (record["url"])

        ## Insert the license if it isn't in the graph.
        if (license_uri, RDF.type, rdf.SG["License"]) not in self.store:
            license_name = value_or_none (record,"name")
            license_id   = value_or_none (record,"value")
            self.store.add ((license_uri, RDF.type, rdf.SG["License"]))
            self.store.add ((license_uri, rdf.COL["name"],
                             Literal(license_name, datatype=XSD.string)))
            self.store.add ((license_uri, rdf.COL["id"],
                             Literal(license_id, datatype=XSD.integer)))

        ## Insert the link between URI and the license.
        self.store.add ((uri, rdf.COL["license"], license_uri))

        return True

    def insert_totals_statistics (self, record, uri):
        """Procedure to insert simplified totals for an article or collection."""

        if record is None:
            return None

        now = datetime.strftime (datetime.now(), "%Y-%m-%dT%H:%M:%SZ")
        rdf.add (self.store, uri, rdf.COL["total_views"],     value_or_none (record, "views"), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["total_downloads"], value_or_none (record, "downloads"), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["total_shares"],    value_or_none (record, "shares"), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["total_cites"],     value_or_none (record, "cites"), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["totals_created_at"], now, XSD.dateTime)

        return True

    def insert_file (self, record):
        """Procedure to insert a file record."""

        file_id = value_or_none (record, "id")
        uri = self.record_uri ("File", "id", file_id)
        if uri is not None:
            return uri

        if record["download_url"].startswith("https://opendap.tudelft.nl/thredds"):
            record["download_url"] = record["download_url"].replace("opendap.tudelft.nl",
                                                                    "opendap.4tu.nl")

        if (record["download_url"].startswith("https://opendap.4tu.nl/thredds") and
            record["size"] == 0):
            record["size"] = self.__get_file_size_for_catalog (record["download_url"])

        is_link_only = bool (value_or (record, "is_link_only", False))

        uri = rdf.unique_node ("file")
        self.store.add ((uri, RDF.type, rdf.SG["File"]))

        rdf.add (self.store, uri, rdf.COL["id"],            file_id, XSD.integer)
        rdf.add (self.store, uri, rdf.COL["name"],          value_or_none (record, "name"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["size"],          value_or_none (record, "size"), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["download_url"],  value_or_none (record, "download_url"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["supplied_md5"],  value_or_none (record, "supplied_md5"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["computed_md5"],  value_or_none (record, "computed_md5"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["viewer_type"],   value_or_none (record, "viewer_type"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["preview_state"], value_or_none (record, "preview_state"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["status"],        value_or_none (record, "status"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["upload_url"],    value_or_none (record, "upload_url"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["upload_token"],  value_or_none (record, "upload_token"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["is_link_only"],  is_link_only, XSD.boolean)

        return uri

    def last_list_node (self, parent_uri, predicate_name):
        """Returns the URI of the last blank node for PARENT_URI or None."""

        try:
            predicate = str(rdf.COL[predicate_name])
            query     = (
                "SELECT ?uri WHERE { "
                f"<{str(parent_uri)}> <{predicate}>/<{str(RDF.rest)}>* ?uri . "
                f"?uri <{str(RDF.rest)}> <{str(RDF.nil)}> . }}"
            )

            results  = self.store.query (query)
            return results.bindings[0]["uri"]

        except KeyError:
            pass
        except IndexError:
            pass

        return None

    def container_uri (self, item_id, item_type, account_id):
        """Returns the URI of the article container belonging to article_id."""

        prefix     = item_type.capitalize()
        item_class = f"{prefix}Container"
        key        = f"{item_type}:{item_id}"
        uri = None
        with self.container_uris_lock:
            try:
                uri = self.container_uris[key]
            except KeyError:
                uri = self.record_uri (item_class, f"{item_type}_id", item_id)
                self.container_uris[key] = uri

        if uri is None:
            uri = rdf.unique_node ("container")
            self.store.add ((uri, RDF.type,                   rdf.SG[item_class]))
            self.store.add ((uri, rdf.COL[f"{item_type}_id"], Literal(item_id, datatype=XSD.integer)))
            self.store.add ((uri, rdf.COL["account_id"],      Literal(account_id, datatype=XSD.integer)))

            with self.container_uris_lock:
                self.container_uris[key] = uri

        return uri

    def insert_article (self, record):
        """Procedure to insert an article record."""

        article_id = value_or_none (record, "id")
        if article_id is None:
            return False
        version = value_or_none(record, "version")
        self.fix_doi (record, article_id, version, 'article')

        account_id = value_or_none (record, "account_id")
        uri        = rdf.unique_node ("article")

        is_embargoed       = bool (value_or (record, "is_embargoed", False))
        is_public          = bool (value_or (record, "is_public", False))
        is_latest          = bool (value_or (record, "is_latest", False))
        is_editable        = bool (value_or (record, "is_editable", False))
        is_confidential    = bool (value_or (record, "is_confidential", False))
        is_metadata_record = bool (value_or (record, "is_metadata_record", False))
        has_linked_file    = bool (value_or (record, "has_linked_file", False))

        self.lock_for_inserts.acquire()

        self.store.add ((uri, RDF.type,              rdf.SG["Article"]))
        self.store.add ((uri, rdf.COL["article_id"], Literal(article_id, datatype=XSD.integer)))

        self.insert_timeline (uri, value_or_none (record, "timeline"))
        self.insert_license (uri, value_or_none (record, "license"))

        rdf.add (self.store, uri, rdf.COL["title"],               value_or_none (record, "title"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["doi"],                 value_or_none (record, "doi"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["handle"],              value_or_none (record, "handle"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["group_id"],            value_or_none (record, "group_id"), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["url"],                 value_or_none (record, "url"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["url_public_html"],     value_or_none (record, "url_public_html"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["url_public_api"],      value_or_none (record, "url_public_api"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["url_private_html"],    value_or_none (record, "url_private_html"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["url_private_api"],     value_or_none (record, "url_private_api"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["published_date"],      value_or_none (record, "published_date"), XSD.dateTime)
        rdf.add (self.store, uri, rdf.COL["created_date"],        value_or_none (record, "created_date"), XSD.dateTime)
        rdf.add (self.store, uri, rdf.COL["modified_date"],       value_or_none (record, "modified_date"), XSD.dateTime)
        rdf.add (self.store, uri, rdf.COL["thumb"],               value_or_none (record, "thumb"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["defined_type"],        value_or_none (record, "defined_type"), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["defined_type_name"],   value_or_none (record, "defined_type_name"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["citation"],            value_or_none (record, "citation"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["metadata_reason"],     value_or_none (record, "metadata_reason"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["confidential_reason"], value_or_none (record, "confidential_reason"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["funding"],             value_or_none (record, "funding"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["size"],                value_or_none (record, "size"), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["status"],              value_or_none (record, "status"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["version"],             value_or_none (record, "version"), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["description"],         value_or_none (record, "description"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["figshare_url"],        value_or_none (record, "figshare_url"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["resource_doi"],        value_or_none (record, "resource_doi"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["resource_title"],      value_or_none (record, "resource_title"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["has_linked_file"],     has_linked_file, XSD.boolean)
        rdf.add (self.store, uri, rdf.COL["is_embargoed"],        is_embargoed, XSD.boolean)
        rdf.add (self.store, uri, rdf.COL["is_metadata_record"],  is_metadata_record, XSD.boolean)
        rdf.add (self.store, uri, rdf.COL["is_confidential"],     is_confidential, XSD.boolean)
        rdf.add (self.store, uri, rdf.COL["is_public"],           is_public, XSD.boolean)
        rdf.add (self.store, uri, rdf.COL["is_latest"],           is_latest, XSD.boolean)
        rdf.add (self.store, uri, rdf.COL["is_editable"],         is_editable, XSD.boolean)

        self.insert_item_list (uri, value_or (record, "references", []), "references")
        self.insert_item_list (uri, value_or (record, "tags", []), "tags")
        self.insert_category_list (uri, value_or (record, "categories", []))
        self.insert_author_list (uri, value_or (record, "authors", []))
        self.insert_file_list (uri, value_or (record, "files", []))
        self.insert_funding_list (uri, value_or (record, "funding_list", []))
        self.insert_private_links_list (uri, value_or (record, "private_links", []))
        self.insert_embargo_list (uri, value_or (record, "embargo_options", []))

        self.handle_custom_fields (record, uri, article_id, version, 'articles')

        ## Assign the article to the container
        container = self.container_uri (article_id, "article", account_id)
        rdf.add (self.store, uri, rdf.COL["container"], container, datatype="uri")

        if "statistics" in record:
            stats = record["statistics"]
            self.insert_totals_statistics (stats["totals"], container)
        elif is_public and is_editable:
            logging.warning ("No statistics available for article %d.", article_id)

        if is_editable:
            self.store.add ((container, rdf.COL["draft"], uri))
        else:
            new_blank_node = rdf.blank_node ()
            self.store.add ((new_blank_node, RDF.type, RDF.List))
            self.store.add ((new_blank_node, RDF.first, uri))
            self.store.add ((new_blank_node, RDF.rest, RDF.nil))

            blank_node = self.last_list_node (container, "published_versions")
            if blank_node is None:
                self.store.add    ((container, rdf.COL["published_versions"], new_blank_node))
            else:
                self.store.remove ((blank_node, RDF.rest, RDF.nil))
                self.store.add    ((blank_node, RDF.rest, new_blank_node))

        if is_latest:
            self.store.add ((container, rdf.COL["latest_published_version"], uri))
            timeline = value_or_none (record, "timeline")
            rdf.add (self.store, container, rdf.COL["first_online_date"],
                     value_or_none (timeline, "firstOnline"), XSD.dateTime)

        self.lock_for_inserts.release()
        return True

    def insert_institution_group (self, record):
        """Procedure to insert a institution group record."""

        uri        = rdf.unique_node ("institution_group")
        self.store.add ((uri, RDF.type, rdf.SG["InstitutionGroup"]))

        rdf.add (self.store, uri, rdf.COL["id"],                   value_or_none (record, "id"), datatype=XSD.integer)
        rdf.add (self.store, uri, rdf.COL["parent_id"],            value_or_none (record, "parent_id"), datatype=XSD.integer)
        ## resource_id is always empty.
        #rdf.add (self.store, uri, rdf.COL["resource_id"],          value_or_none (record, "resource_id"), datatype=XSD.string)
        rdf.add (self.store, uri, rdf.COL["name"],                 value_or_none (record, "name"), datatype=XSD.string)
        rdf.add (self.store, uri, rdf.COL["association_criteria"], value_or_none (record, "association_criteria"), datatype=XSD.string)

        return True

    def insert_root_categories (self):
        """Procedure to insert root categories."""

        categories = [
            { "id": 13431, "title": "Mathematical Sciences", "parent_id": 0, "source_id": 85 },
            { "id": 13603, "title": "Physical Sciences", "parent_id": 0, "source_id": 85 },
            { "id": 13594, "title": "Chemical Sciences", "parent_id": 0, "source_id": 85 },
            { "id": 13551, "title": "Earth Sciences", "parent_id": 0, "source_id": 85 },
            { "id": 13410, "title": "Environmental Sciences", "parent_id": 0, "source_id": 85 },
            { "id": 13578, "title": "Biological Sciences", "parent_id": 0, "source_id": 85 },
            { "id": 13376, "title": "Agricultural and Veterinary Sciences", "parent_id": 0, "source_id": 85 },
            { "id": 13611, "title": "Information and Computing Sciences", "parent_id": 0, "source_id": 85 },
            { "id": 13630, "title": "Engineering", "parent_id": 0, "source_id": 85 },
            { "id": 13652, "title": "Technology", "parent_id": 0, "source_id": 85 },
            { "id": 13474, "title": "Medical and Health Sciences", "parent_id": 0, "source_id": 85 },
            { "id": 13362, "title": "Built Environment and Design", "parent_id": 0, "source_id": 85 },
            { "id": 13647, "title": "Education", "parent_id": 0, "source_id": 85 },
            { "id": 13566, "title": "Economics", "parent_id": 0, "source_id": 85 },
            { "id": 13500, "title": "Commerce, Management, Tourism and Services", "parent_id": 0, "source_id": 85 },
            { "id": 13464, "title": "Studies in Human Society", "parent_id": 0, "source_id": 85 },
            { "id": 13453, "title": "Psychology and Cognitive Sciences", "parent_id": 0, "source_id": 85 },
            { "id": 13427, "title": "Law and Legal Studies", "parent_id": 0, "source_id": 85 },
            { "id": 13559, "title": "Studies in Creative Arts and Writing", "parent_id": 0, "source_id": 85 },
            { "id": 13517, "title": "Language, Communication and Culture", "parent_id": 0, "source_id": 85 },
            { "id": 13448, "title": "History and Archaeology", "parent_id": 0, "source_id": 85 },
            { "id": 13588, "title": "Philosophy and Religious Studies", "parent_id": 0, "source_id": 85 },
            { "id": 13360, "title": "Defence", "parent_id": 0, "source_id": 85 },
            { "id": 13401, "title": "Plant Production and Plant Primary Products", "parent_id": 0, "source_id": 85 },
            { "id": 13440, "title": "Animal Production and Animal Primary Products", "parent_id": 0, "source_id": 85 },
            { "id": 13421, "title": "Mineral Resources (excl. Energy Resources)", "parent_id": 0, "source_id": 85 },
            { "id": 13620, "title": "Energy", "parent_id": 0, "source_id": 85 },
            { "id": 13524, "title": "Manufacturing", "parent_id": 0, "source_id": 85 },
            { "id": 13509, "title": "Construction", "parent_id": 0, "source_id": 85 },
            { "id": 13661, "title": "Transport", "parent_id": 0, "source_id": 85 },
            { "id": 13544, "title": "Information and Communication Services", "parent_id": 0, "source_id": 85 },
            { "id": 13457, "title": "Commercial Services and Tourism", "parent_id": 0, "source_id": 85 },
            { "id": 13667, "title": "Economic Framework", "parent_id": 0, "source_id": 85 },
            { "id": 13415, "title": "Health", "parent_id": 0, "source_id": 85 },
            { "id": 13571, "title": "Education and Training", "parent_id": 0, "source_id": 85 },
            { "id": 13369, "title": "Law, Politics and Community Services", "parent_id": 0, "source_id": 85 },
            { "id": 13493, "title": "Cultural Understanding", "parent_id": 0, "source_id": 85 },
            { "id": 13385, "title": "Environment", "parent_id": 0, "source_id": 85 },
            { "id": 13438, "title": "Expanding Knowledge", "parent_id": 0, "source_id": 85 }]

        status = list(map(self.insert_category, categories))
        return all (status)

    def insert_static_triplets (self):
        """Procedure to insert triplets to augment the state graph."""
        self.store.add ((rdf.SG["ArticleContainer"],    RDFS.subClassOf, rdf.SG["Container"]))
        self.store.add ((rdf.SG["CollectionContainer"], RDFS.subClassOf, rdf.SG["Container"]))

        return True
