"""This module provides an interface to store data fetched by the 'figshare' module."""

import os
import ast
import logging
from datetime import datetime
from threading import Lock
from secrets import token_urlsafe
import json
import time
import re
from defusedxml import ElementTree
from rdflib import Graph, Literal, RDF, RDFS, XSD, URIRef
import requests
from requests.utils import requote_uri
from djehuty.utils.convenience import value_or, value_or_none
from djehuty.utils.convenience import custom_field_name, opendap_sizes_to_bytes
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
        with open(f'{script_path}/resources/public_collections.json', 'r',
                  encoding = 'utf-8') as coll_file:
            self.public_collection_datasets = json.load(coll_file)

    def __get_from_url (self, url: str, headers, parameters):
        """Procedure to perform a GET request to a Figshare-compatible endpoint."""
        try:
            response = requests.get(url,
                                    headers = headers,
                                    params  = parameters,
                                    timeout = 60)
            if response.status_code == 200:
                return response.text

            logging.error("%s returned %d.", url, response.status_code)
            logging.error("Error message:\n---\n%s\n---", response.text)

        except requests.exceptions.ConnectionError:
            logging.error("Failed to connect to %s.", url)

        return False

    def __get_file_size_for_catalog (self, url, recurse=None):
        """Returns the file size for an OPeNDAP catalog."""

        if not url.startswith('https://opendap.4tu.nl/thredds'):
            logging.debug("Trying to get data size: %s is not an opendap catalog", url)
            return 0

        if recurse is None:
            no_recurse = ('/IDRA/', '/darelux/', '/zandmotor/meteohydro/xband/catalog', '/CF_Drinking_water/')
            recurse = True not in [no_recurse_fragment in url for no_recurse_fragment in no_recurse]

        total_filesize = 0
        metadata_url   = url.replace(".html", ".xml")
        metadata       = self.__get_from_url (metadata_url, {}, {})

        if not metadata:
            logging.error("Couldn't get file metadata for %s.", url)
            return total_filesize

        namespaces  = { "c": "http://www.unidata.ucar.edu/namespaces/thredds/InvCatalog/v1.0" }
        xml_root    = ElementTree.fromstring(metadata)
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

        for single_file in files:
            units = single_file.attrib["units"]
            size  = ast.literal_eval(single_file.text)
            total_filesize += opendap_sizes_to_bytes (size, units)

        return total_filesize

    def __load_resource_file (self, filename):
        script_path = os.path.dirname(os.path.abspath(__file__))
        data        = None
        try:
            with open(f"{script_path}/resources/{filename}", "r",
                      encoding = "utf-8") as data_file:
                data = json.load(data_file)
        except FileNotFoundError:
            logging.error("Could not load resource '%s'.", filename)

        return data

    def get_crossref_events_for_doi (self, dois, from_date, mail_to):
        """Returns a list of events for a list of DOIs."""
        #rate limit is 15 queries per second. I'm going for 10/s
        rate = .1
        #from_date 'yyyy-mm-dd'
        # dois is list of dois
        # events is list of dictionaries (one per event)
        events = []
        for doi in dois:
            query = f"https://api.eventdata.crossref.org/v1/events?mailto={mail_to}&obj-id={doi}&from-occurred-date={from_date}"
            time.sleep(rate)
            req = requests.get(query, timeout = 60)
            data = json.loads(req.content)
            for item in data["message"]["events"]:
                try:
                    event = {}
                    event['object']    = str(item["obj_id"])
                    event['source']    = str(item["source_id"])
                    event['timestamp'] = str(item["timestamp"])
                    event['type']      = str(item["relation_type_id"])
                    events.append(event)
                except KeyError:
                    logging.error("Failed to gather crossref data for %s.", doi)

        return events

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
                f"?uri <{str(RDF.type)}> <{str(rdf.DJHT[record_type])}> ; "
                f"<{str(rdf.DJHT[identifier_name])}> {identifier} . }}"
            )

            results = self.store.query (query)
            return results.bindings[0]["uri"]

        except (KeyError, IndexError):
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
        with self.lock_for_inserts:
            self.store.add ((uri, RDF.type, rdf.DJHT["Account"]))

            institution_user_id = value_or (record, "institution_user_id", None)
            domain              = None
            if institution_user_id is not None:
                domain = institution_user_id.partition("@")[2]

            rdf.add (self.store, uri, rdf.DJHT["id"],                    value_or (record, "id", None),           XSD.integer)
            rdf.add (self.store, uri, rdf.DJHT["active"],                value_or (record, "active", False),      XSD.boolean)
            rdf.add (self.store, uri, rdf.DJHT["domain"],                domain,                                  XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["email"],                 value_or (record, "email", None),        XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["first_name"],            value_or (record, "first_name", None),   XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["last_name"],             value_or (record, "last_name", None),    XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["institution_user_id"],   institution_user_id,                     XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["institution_id"],        value_or (record, "institution_id", None))
            rdf.add (self.store, uri, rdf.DJHT["group_id"],              value_or (record, "group_id", None))
            rdf.add (self.store, uri, rdf.DJHT["pending_quota_request"], value_or (record, "pending_quota_request", None))
            rdf.add (self.store, uri, rdf.DJHT["used_quota_public"],     value_or (record, "used_quota_public", None))
            rdf.add (self.store, uri, rdf.DJHT["used_quota_private"],    value_or (record, "used_quota_private", None))
            rdf.add (self.store, uri, rdf.DJHT["used_quota"],            value_or (record, "used_quota", None))
            rdf.add (self.store, uri, rdf.DJHT["maximum_file_size"],     value_or (record, "maximum_file_size", None))
            rdf.add (self.store, uri, rdf.DJHT["quota"],                 value_or (record, "quota", None))
            rdf.add (self.store, uri, rdf.DJHT["modified_date"],         value_or_none (record, "modified_date"), XSD.dateTime)
            rdf.add (self.store, uri, rdf.DJHT["created_date"],          value_or_none (record, "created_date"),  XSD.dateTime)

        return uri

    def insert_institution (self, record):
        """Procedure to insert an institution record."""

        try:
            institution_id = record["institution_id"]
            uri            = rdf.ROW[f"institution_{institution_id}"]

            self.store.add ((uri, RDF.type,        rdf.DJHT["Institution"]))
            self.store.add ((uri, rdf.DJHT["id"],   Literal(institution_id, datatype=XSD.integer)))
            self.store.add ((uri, rdf.DJHT["name"], Literal(record["name"], datatype=XSD.string)))

            return True

        except KeyError:
            pass

        logging.error ("Failed to insert Institution record: %s", record)
        return False

    def insert_account_author_link (self, account_uri, author_uri):
        """Procedure to insert a link between an account and an author."""
        self.store.add ((author_uri, rdf.DJHT["account"], URIRef(account_uri)))
        return True

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

        self.store.add ((uri, RDF.type, rdf.DJHT["Author"]))

        rdf.add (self.store, uri, rdf.DJHT["id"],             author_id,                                 XSD.integer)
        rdf.add (self.store, uri, rdf.DJHT["institution_id"], value_or (record, "institution_id", None), XSD.integer)
        rdf.add (self.store, uri, rdf.DJHT["group_id"],       value_or (record, "group_id",       None), XSD.integer)
        rdf.add (self.store, uri, rdf.DJHT["first_name"],     value_or (record, "first_name",     None), XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["last_name"],      value_or (record, "last_name",      None), XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["full_name"],      value_or (record, "full_name",      None), XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["job_title"],      value_or (record, "job_title",      None), XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["url_name"],       value_or (record, "url_name",       None), XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["orcid_id"],       value_or (record, "orcid_id",       None), XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["is_active"],      is_active,                                 XSD.boolean)
        rdf.add (self.store, uri, rdf.DJHT["is_public"],      is_public,                                 XSD.boolean)

        return uri

    def insert_timeline (self, uri, record):
        """Procedure to insert a timeline record."""

        if not record:
            return False

        rdf.add (self.store, uri, rdf.DJHT["revision_date"],     value_or_none (record, "revision"),             XSD.dateTime)
        rdf.add (self.store, uri, rdf.DJHT["publisher_publication_date"], value_or_none (record, "publisherPublication"), XSD.dateTime)
        rdf.add (self.store, uri, rdf.DJHT["publisher_acceptance_date"], value_or_none (record, "publisherAcceptance"), XSD.dateTime)
        rdf.add (self.store, uri, rdf.DJHT["posted_date"],       value_or_none (record, "posted"),               XSD.dateTime)
        rdf.add (self.store, uri, rdf.DJHT["submission_date"],   value_or_none (record, "submission"),           XSD.dateTime)

        return True

    def insert_category (self, record):
        """Procedure to insert a category record."""

        category_id = value_or_none (record, "id")
        uri = self.record_uri ("Category", "id", category_id)
        if uri is not None:
            return uri

        uri = rdf.unique_node ("category")
        self.store.add ((uri, RDF.type,      rdf.DJHT["Category"]))
        self.store.add ((uri, rdf.DJHT["id"], Literal(category_id)))

        rdf.add (self.store, uri, rdf.DJHT["title"],       value_or (record, "title", None),       XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["parent_id"],   value_or (record, "parent_id", None),   XSD.integer)
        rdf.add (self.store, uri, rdf.DJHT["source_id"],   value_or (record, "source_id", None),   XSD.integer)
        rdf.add (self.store, uri, rdf.DJHT["taxonomy_id"], value_or (record, "taxonomy_id", None), XSD.integer)
        rdf.add (self.store, uri, rdf.DJHT["classification_code"], value_or (record, "classification_code", None), XSD.string)

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
            self.store.add ((uri, rdf.DJHT[name], blank_node))

            previous_blank_node = None
            for index, item in enumerate(records):
                record_uri = insert_procedure (item)
                self.store.add ((blank_node, rdf.DJHT["index"], Literal (index, datatype=XSD.integer)))
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

    def insert_item_list (self, uri, items, items_name):
        """Adds an RDF list with indexes for ITEMS to GRAPH."""

        if items:
            blank_node = rdf.blank_node ()
            self.store.add ((uri, rdf.DJHT[items_name], blank_node))

            previous_blank_node = None
            for index, item in enumerate(items):
                self.store.add ((blank_node, rdf.DJHT["index"], Literal (index, datatype=XSD.integer)))
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

                # The URLs in the "Data Link" custom field aren't encoded.
                # This could and would lead to invalid RDF serialization.
                # So, we must re-encode the URLs to treat them as RDF URIs.
                if name == "data_link":
                    item = requote_uri (item)

                rdf.add (self.store, uri, rdf.DJHT[name], item, field_type)

        elif not (isinstance (value, str) and value == ""):
            if name == "data_link":
                value = requote_uri (value)
            rdf.add (self.store, uri, rdf.DJHT[name], value, field_type)

    def insert_custom_field (self, uri, field):
        """Procedure to insert a custom_field record."""

        name = custom_field_name (field["name"])

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
        subjects = self.store.subjects ((None, RDF.type, rdf.DJHT["CustomField"]),
                                        (None, rdf.DJHT["name"], Literal(name, datatype=XSD.string)))
        field_uri = next (subjects, None)
        if field_uri is None:
            field_uri = rdf.ROW[f"custom_field_{name}"]
            self.store.add ((field_uri,     RDF.type,                rdf.DJHT["CustomField"]))
            rdf.add (self.store, field_uri, rdf.DJHT["predicate"],    rdf.DJHT[name], datatype="url")
            rdf.add (self.store, field_uri, rdf.DJHT["name"],         name,                                        XSD.string)
            rdf.add (self.store, field_uri, rdf.DJHT["original_name"], field["name"],                              XSD.string)
            rdf.add (self.store, field_uri, rdf.DJHT["max_length"],   value_or_none (validations, "max_length"))
            rdf.add (self.store, field_uri, rdf.DJHT["min_length"],   value_or_none (validations, "min_length"))
            rdf.add (self.store, field_uri, rdf.DJHT["is_mandatory"], value_or_none (validations, "is_mandatory"), XSD.boolean)
            rdf.add (self.store, field_uri, rdf.DJHT["placeholder"],  value_or_none (validations, "placeholder"),  XSD.string)
            rdf.add (self.store, field_uri, rdf.DJHT["is_multiple"],  value_or_none (validations, "is_multiple"),  XSD.boolean)

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
                        rdf.add (self.store, options_uri, rdf.DJHT["name"], name, XSD.string)
                        self.insert_item_list (options_uri, options, "values")
        else:
            value      = value_or (field, "value", default_value)
            field_type = value_or_none (field, "field_type")
            self.insert_custom_field_value (uri, name, value, field_type)

    def fix_doi (self, record, item_id, version, item_type):
        '''Fix doi if needed: handle Fedora/Figshare history and fix Figshare bug'''
        extra_dois = [extra['doi'] for extra in self.extra_dois[item_type] if extra['id']==item_id and extra['version']==version]
        if extra_dois:
            record['doi'] = extra_dois[0]
        elif version and 'doi' in record and re.findall(r'^10\.4121/(c\.)?\d+$', record['doi']):
            record['doi'] += f'.v{version}'

    def add_container_doi (self, record, container):
        '''Add doi to container if latest item in container has Figshare-style doi'''
        try:
            groups = re.match(r'^(10\.4121/(c\.)?\d+)(.v\d+)?$', record['doi']).groups()
            if groups:
                rdf.add (self.store, container, rdf.DJHT["doi"], groups[0], XSD.string)
        except (KeyError, IndexError, AttributeError):
            pass # No DOI in record or unnecessary to add to the container.

    def handle_custom_fields (self, record, uri, item_id, version, item_type):
        '''Handle custom fields and fix special cases'''
        for field in value_or (record, "custom_fields", []):
            #replace contributors by organizations and (optional) contributors
            if field['name'] == 'Contributors':
                try:
                    extra = self.extra_contributors_organizations[item_type][item_id][version]
                    contributors  = extra['contributors']
                    if contributors:
                        field['value'] = contributors
                        self.insert_custom_field (uri, field)
                    field = {'name': 'Organizations', 'value': extra['organizations']}
                except KeyError:
                    pass
            #add "Data Link Size" field for opendap catalogs in "Data Link" field, correct opendap url if needed
            if field['name'] == 'Data Link':
                urls = field['value']
                urls = [url.replace('https://opendap.tudelft.nl/', 'https://opendap.4tu.nl/') for url in urls]
                field['value'] = urls
                data_link_size = sum(self.__get_file_size_for_catalog(url) for url in urls)
                if data_link_size:
                    rdf.add (self.store, uri, rdf.DJHT["data_link_size"], data_link_size, XSD.integer)

            self.insert_custom_field (uri, field)

    def insert_collection (self, record, account_id, account_uri):
        """Procedure to insert a collection record."""

        collection_id  = record["id"]
        uri            = rdf.unique_node ("collection")

        is_public          = bool (value_or (record, "public", False))
        is_latest          = bool (value_or (record, "is_latest", False))
        is_editable        = bool (value_or (record, "is_editable", False))

        version = value_or_none(record, "version")
        self.fix_doi (record, collection_id, version, 'collection')

        with self.lock_for_inserts:
            self.store.add ((uri, RDF.type,                 rdf.DJHT["Collection"]))
            self.store.add ((uri, rdf.DJHT["collection_id"], Literal(collection_id, datatype=XSD.integer)))

            rdf.add (self.store, uri, rdf.DJHT["url"],                 value_or_none (record, "url"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["title"],               value_or_none (record, "title"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["published_date"],      value_or_none (record, "published_date"), XSD.dateTime)
            rdf.add (self.store, uri, rdf.DJHT["created_date"],        value_or_none (record, "created_date"), XSD.dateTime)
            rdf.add (self.store, uri, rdf.DJHT["modified_date"],       value_or_none (record, "modified_date"), XSD.dateTime)
            rdf.add (self.store, uri, rdf.DJHT["doi"],                 value_or_none (record, "doi"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["citation"],            value_or_none (record, "citation"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["group_id"],            value_or_none (record, "group_id"), XSD.integer)
            ## group_resource_id is always empty/NULL.
            #rdf.add (self.store, uri, rdf.DJHT["group_resource_id"],   value_or_none (record, "group_resource_id"), XSD.integer)
            rdf.add (self.store, uri, rdf.DJHT["institution_id"],      value_or_none (record, "institution_id"), XSD.integer)
            rdf.add (self.store, uri, rdf.DJHT["description"],         value_or_none (record, "description"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["version"],             value_or_none (record, "version"), XSD.integer)
            ## resource_id is always empty/NULL.
            #rdf.add (self.store, uri, rdf.DJHT["resource_id"],         value_or_none (record, "resource_id"), XSD.integer)
            rdf.add (self.store, uri, rdf.DJHT["resource_doi"],        value_or_none (record, "resource_doi"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["resource_title"],      value_or_none (record, "resource_title"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["resource_version"],    value_or_none (record, "resource_version"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["resource_link"],       value_or_none (record, "resource_link"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["handle"],              value_or_none (record, "handle"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["is_public"],           is_public, XSD.boolean)
            rdf.add (self.store, uri, rdf.DJHT["is_latest"],           is_latest, XSD.boolean)
            rdf.add (self.store, uri, rdf.DJHT["is_editable"],         is_editable, XSD.boolean)

            self.insert_timeline (uri, value_or_none (record, "timeline"))
            self.insert_author_list (uri, value_or (record, "authors", []))
            self.insert_category_list (uri, value_or (record, "categories", []))
            self.insert_funding_list (uri, value_or (record, "funding_list", []))
            self.insert_private_links_list (uri, value_or (record, "private_links", []))
            tags = [tag for tag in value_or (record, "tags", []) if not tag.startswith('Collection: ')]
            self.insert_item_list (uri, tags, "tags")
            self.insert_item_list (uri, value_or (record, "references", []), "references")

            self.handle_custom_fields (record, uri, collection_id, version, 'collections')

            datasets = value_or (record, "datasets",
                                 value_or (self.public_collection_datasets,
                                           f"{collection_id}_{version}", []))
            if datasets:
                for index, dataset_id in enumerate (datasets):
                    dataset_uri = self.record_uri ("DatasetContainer", "dataset_id", dataset_id)
                    if dataset_uri is None:
                        logging.error ("Could not find dataset container for %d", dataset_id)
                        continue

                    datasets[index] = URIRef (dataset_uri)

                self.insert_item_list (uri, datasets, "datasets")
            else:
                logging.warning ("Collection %d seems to be empty.", collection_id)

            ## Assign the collection to the container
            container = self.container_uri (collection_id, "collection",
                                            account_id, account_uri)
            rdf.add (self.store, uri, rdf.DJHT["container"], container, datatype="uri")

            if "statistics" in record:
                stats = record["statistics"]
                self.insert_totals_statistics (stats["totals"], container)
            elif is_public and is_latest:
                logging.warning ("No statistics available for collection %d.", collection_id)

            if is_editable:
                self.store.add ((container, rdf.DJHT["draft"], uri))
            else:
                new_blank_node = rdf.blank_node ()
                self.store.add ((new_blank_node, RDF.type, RDF.List))
                self.store.add ((new_blank_node, RDF.first, uri))
                self.store.add ((new_blank_node, RDF.rest, RDF.nil))

                blank_node = self.last_list_node (container, "published_versions")
                if blank_node is None:
                    self.store.add    ((container, rdf.DJHT["published_versions"], new_blank_node))
                else:
                    self.store.remove ((blank_node, RDF.rest, RDF.nil))
                    self.store.add    ((blank_node, RDF.rest, new_blank_node))

            if is_latest:
                self.store.add ((container, rdf.DJHT["latest_published_version"], uri))
                self.add_container_doi (record, container)
                timeline = value_or_none (record, "timeline")
                rdf.add (self.store, container, rdf.DJHT["first_online_date"],
                         value_or_none (timeline, "firstOnline"), XSD.dateTime)

        return True

    def insert_funding (self, record):
        """Procedure to insert a funding record."""

        funding_id = value_or_none (record, "id")
        uri = self.record_uri ("Funding", "id", funding_id)
        if uri is not None:
            return uri

        is_user_defined = value_or (record, "is_user_defined", False)

        uri = rdf.unique_node ("funding")
        self.store.add ((uri, RDF.type, rdf.DJHT["Funding"]))
        rdf.add (self.store, uri, rdf.DJHT["id"],              funding_id, XSD.integer)
        rdf.add (self.store, uri, rdf.DJHT["title"],           value_or_none (record, "title"), XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["grant_code"],      value_or_none (record, "grant_code"), XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["funder_name"],     value_or_none (record, "funder_name"), XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["url"],             value_or_none (record, "url"), XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["is_user_defined"], is_user_defined, XSD.boolean)

        return uri

    def insert_private_link (self, record):
        """Procedure to insert a private link to a dataset or a collection."""

        is_active = value_or (record, "is_active", False)
        suffix    = token_urlsafe (64)
        uri       = rdf.unique_node ("private_link")

        self.store.add ((uri, RDF.type, rdf.DJHT["PrivateLink"]))
        rdf.add (self.store, uri, rdf.DJHT["id"],           value_or_none (record, "id"), XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["suffix"],       suffix, XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["expires_date"], value_or_none (record, "expires_date"), XSD.dateTime)
        rdf.add (self.store, uri, rdf.DJHT["is_active"],    is_active, XSD.boolean)

        return uri

    def insert_license (self, uri, record):
        """Procedure to insert a license record."""

        if not (record and value_or (record, "url", False)):
            return False

        license_uri  = URIRef (record["url"])

        ## Insert the license if it isn't in the graph.
        if (license_uri, RDF.type, rdf.DJHT["License"]) not in self.store:
            license_name = value_or_none (record,"name")
            license_type = value_or_none (record,"type")
            license_id   = value_or_none (record,"value")
            license_spdx = value_or_none (record, "spdx")
            self.store.add ((license_uri, RDF.type, rdf.DJHT["License"]))
            self.store.add ((license_uri, rdf.DJHT["name"],
                             Literal(license_name, datatype=XSD.string)))
            self.store.add ((license_uri, rdf.DJHT["id"],
                             Literal(license_id, datatype=XSD.integer)))

            if license_spdx is not None:
                self.store.add ((license_uri, rdf.DJHT["spdx"],
                                 URIRef(license_spdx)))

            license_type_uri = None
            if license_type == "software":
                license_type_uri = rdf.DJHT["SoftwareLicense"]
            if license_type == "hardware":
                license_type_uri = rdf.DJHT["HardwareLicense"]
            elif license_type == "data":
                license_type_uri = rdf.DJHT["DataLicense"]
            elif license_type == "legacy":
                license_type_uri = rdf.DJHT["LegacyLicense"]

            rdf.add (self.store, license_uri, rdf.DJHT["type"], license_type_uri, "url")
            rdf.add (self.store, license_type_uri, RDFS.label,  license_type, XSD.string)

        ## Insert the link between URI and the license.
        if uri is not None:
            self.store.add ((uri, rdf.DJHT["license"], license_uri))

        return True

    def insert_totals_statistics (self, record, uri):
        """Procedure to insert simplified totals for a dataset or collection."""

        if record is None:
            return None

        now = datetime.strftime (datetime.now(), "%Y-%m-%dT%H:%M:%SZ")
        rdf.add (self.store, uri, rdf.DJHT["total_views"],     value_or_none (record, "views"), XSD.integer)
        rdf.add (self.store, uri, rdf.DJHT["total_downloads"], value_or_none (record, "downloads"), XSD.integer)
        rdf.add (self.store, uri, rdf.DJHT["total_shares"],    value_or_none (record, "shares"), XSD.integer)
        rdf.add (self.store, uri, rdf.DJHT["total_cites"],     value_or_none (record, "cites"), XSD.integer)
        rdf.add (self.store, uri, rdf.DJHT["totals_created_at"], now, XSD.dateTime)

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
        self.store.add ((uri, RDF.type, rdf.DJHT["File"]))

        rdf.add (self.store, uri, rdf.DJHT["id"],            file_id, XSD.integer)
        rdf.add (self.store, uri, rdf.DJHT["name"],          value_or_none (record, "name"), XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["size"],          value_or_none (record, "size"), XSD.integer)
        rdf.add (self.store, uri, rdf.DJHT["download_url"],  value_or_none (record, "download_url"), XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["supplied_md5"],  value_or_none (record, "supplied_md5"), XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["computed_md5"],  value_or_none (record, "computed_md5"), XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["viewer_type"],   value_or_none (record, "viewer_type"), XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["preview_state"], value_or_none (record, "preview_state"), XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["status"],        value_or_none (record, "status"), XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["upload_url"],    value_or_none (record, "upload_url"), XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["upload_token"],  value_or_none (record, "upload_token"), XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["is_link_only"],  is_link_only, XSD.boolean)

        return uri

    def last_list_node (self, parent_uri, predicate_name):
        """Returns the URI of the last blank node for PARENT_URI or None."""

        try:
            predicate = str(rdf.DJHT[predicate_name])
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

    def container_uri (self, item_id, item_type, account_id, account_uri):
        """Returns the URI of the dataset container belonging to dataset_id."""

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
            self.store.add ((uri, RDF.type,                   rdf.DJHT[item_class]))
            self.store.add ((uri, rdf.DJHT[f"{item_type}_id"], Literal(item_id, datatype=XSD.integer)))
            self.store.add ((uri, rdf.DJHT["account_id"],      Literal(account_id, datatype=XSD.integer)))
            self.store.add ((uri, rdf.DJHT["account"],         URIRef(account_uri)))

            with self.container_uris_lock:
                self.container_uris[key] = uri

        return uri

    def insert_dataset (self, record):
        """Procedure to insert a dataset record."""

        dataset_id = value_or_none (record, "id")
        if dataset_id is None:
            return False
        version = value_or_none(record, "version")
        self.fix_doi (record, dataset_id, version, 'article')

        account_id = value_or_none (record, "account_id")
        account_uri = value_or_none (record, "account_uri")
        uri        = rdf.unique_node ("dataset")

        is_embargoed       = bool (value_or (record, "is_embargoed", False))
        is_public          = bool (value_or (record, "is_public", False))
        is_latest          = bool (value_or (record, "is_latest", False))
        is_editable        = bool (value_or (record, "is_editable", False))
        is_confidential    = bool (value_or (record, "is_confidential", False))
        is_metadata_record = bool (value_or (record, "is_metadata_record", False))
        has_linked_file    = bool (value_or (record, "has_linked_file", False))

        with self.lock_for_inserts:
            self.store.add ((uri, RDF.type,              rdf.DJHT["Dataset"]))
            self.store.add ((uri, rdf.DJHT["dataset_id"], Literal(dataset_id, datatype=XSD.integer)))

            self.insert_timeline (uri, value_or_none (record, "timeline"))
            self.insert_license (uri, value_or_none (record, "license"))

            rdf.add (self.store, uri, rdf.DJHT["title"],               value_or_none (record, "title"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["doi"],                 value_or_none (record, "doi"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["handle"],              value_or_none (record, "handle"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["group_id"],            value_or_none (record, "group_id"), XSD.integer)
            rdf.add (self.store, uri, rdf.DJHT["url"],                 value_or_none (record, "url"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["url_public_html"],     value_or_none (record, "url_public_html"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["url_public_api"],      value_or_none (record, "url_public_api"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["url_private_html"],    value_or_none (record, "url_private_html"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["url_private_api"],     value_or_none (record, "url_private_api"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["published_date"],      value_or_none (record, "published_date"), XSD.dateTime)
            rdf.add (self.store, uri, rdf.DJHT["created_date"],        value_or_none (record, "created_date"), XSD.dateTime)
            rdf.add (self.store, uri, rdf.DJHT["modified_date"],       value_or_none (record, "modified_date"), XSD.dateTime)
            rdf.add (self.store, uri, rdf.DJHT["thumb"],               value_or_none (record, "thumb"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["defined_type"],        value_or_none (record, "defined_type"), XSD.integer)
            rdf.add (self.store, uri, rdf.DJHT["defined_type_name"],   value_or_none (record, "defined_type_name"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["citation"],            value_or_none (record, "citation"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["metadata_reason"],     value_or_none (record, "metadata_reason"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["confidential_reason"], value_or_none (record, "confidential_reason"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["funding"],             value_or_none (record, "funding"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["size"],                value_or_none (record, "size"), XSD.integer)
            rdf.add (self.store, uri, rdf.DJHT["status"],              value_or_none (record, "status"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["version"],             value_or_none (record, "version"), XSD.integer)
            rdf.add (self.store, uri, rdf.DJHT["description"],         value_or_none (record, "description"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["figshare_url"],        value_or_none (record, "figshare_url"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["resource_doi"],        value_or_none (record, "resource_doi"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["resource_title"],      value_or_none (record, "resource_title"), XSD.string)
            rdf.add (self.store, uri, rdf.DJHT["has_linked_file"],     has_linked_file, XSD.boolean)
            rdf.add (self.store, uri, rdf.DJHT["is_metadata_record"],  is_metadata_record, XSD.boolean)
            rdf.add (self.store, uri, rdf.DJHT["is_confidential"],     is_confidential, XSD.boolean)
            rdf.add (self.store, uri, rdf.DJHT["is_public"],           is_public, XSD.boolean)
            rdf.add (self.store, uri, rdf.DJHT["is_latest"],           is_latest, XSD.boolean)
            rdf.add (self.store, uri, rdf.DJHT["is_editable"],         is_editable, XSD.boolean)

            if is_embargoed:
                rdf.add (self.store, uri, rdf.DJHT["embargo_until_date"], value_or_none (record, "embargo_date"), XSD.date)
                rdf.add (self.store, uri, rdf.DJHT["embargo_type"],    value_or_none (record, "embargo_type"), XSD.string)
                rdf.add (self.store, uri, rdf.DJHT["embargo_title"],   value_or_none (record, "embargo_title"), XSD.string)
                rdf.add (self.store, uri, rdf.DJHT["embargo_reason"],  value_or_none (record, "embargo_reason"), XSD.string)

            self.insert_item_list (uri, value_or (record, "references", []), "references")
            tags = [tag for tag in value_or (record, "tags", []) if not tag.startswith('Collection: ')]
            self.insert_item_list (uri, tags, "tags")
            self.insert_category_list (uri, value_or (record, "categories", []))
            self.insert_author_list (uri, value_or (record, "authors", []))
            self.insert_file_list (uri, value_or (record, "files", []))
            self.insert_funding_list (uri, value_or (record, "funding_list", []))
            self.insert_private_links_list (uri, value_or (record, "private_links", []))

            self.handle_custom_fields (record, uri, dataset_id, version, 'articles')

            ## Assign the dataset to the container
            container = self.container_uri (dataset_id, "dataset", account_id, account_uri)
            rdf.add (self.store, uri, rdf.DJHT["container"], container, datatype="uri")

            if "statistics" in record:
                stats = record["statistics"]
                self.insert_totals_statistics (stats["totals"], container)
            elif is_public and is_editable:
                logging.warning ("No statistics available for dataset %d.", dataset_id)

            if is_editable:
                self.store.add ((container, rdf.DJHT["draft"], uri))
            else:
                new_blank_node = rdf.blank_node ()
                self.store.add ((new_blank_node, RDF.type, RDF.List))
                self.store.add ((new_blank_node, RDF.first, uri))
                self.store.add ((new_blank_node, RDF.rest, RDF.nil))

                blank_node = self.last_list_node (container, "published_versions")
                if blank_node is None:
                    self.store.add    ((container, rdf.DJHT["published_versions"], new_blank_node))
                else:
                    self.store.remove ((blank_node, RDF.rest, RDF.nil))
                    self.store.add    ((blank_node, RDF.rest, new_blank_node))

            ## Insert the review state for the record.
            review = value_or_none (record, "review")
            if review:
                logging.info ("Adding review for dataset %s v%s.", uri, "0" if version is None else version)
                review_uri  = rdf.unique_node ("review")
                status      = value_or (review, "status", "pending")
                assigned_to = value_or_none (review, "assigned_to")
                assigned_to_uri = None
                status_uri  = None
                is_under_review = True
                if assigned_to is None:
                    status_uri = rdf.DJHT["ReviewUnassigned"]
                elif int(assigned_to) == 0:
                    status_uri = rdf.DJHT["ReviewUnassigned"]
                elif isinstance(status, str) and status == "pending":
                    status_uri = rdf.DJHT["ReviewAssigned"]
                    assigned_to_uri = self.record_uri ("Account", "id", assigned_to)
                elif isinstance(status, str):
                    status_uri = rdf.DJHT["Review" + status.capitalize()]
                    assigned_to_uri = self.record_uri ("Account", "id", assigned_to)
                    is_under_review = False
                else:
                    status_uri = rdf.DJHT["ReviewUnassigned"]

                rdf.add (self.store, uri, rdf.DJHT["is_under_review"], is_under_review, XSD.boolean)
                rdf.add (self.store, review_uri, RDF.type, rdf.DJHT["Review"], datatype="uri")
                rdf.add (self.store, review_uri, rdf.DJHT["dataset"], uri, datatype="uri")
                rdf.add (self.store, review_uri, rdf.DJHT["request_date"], value_or_none (review, "created_date"),  XSD.dateTime)
                rdf.add (self.store, review_uri, rdf.DJHT["modified_by_reviewer"], value_or_none (review, "modified_date"), XSD.dateTime)
                rdf.add (self.store, review_uri, rdf.DJHT["assigned_to"], assigned_to_uri, datatype="uri")
                rdf.add (self.store, review_uri, rdf.DJHT["status"], status_uri, datatype="uri")

            if is_latest:
                self.store.add ((container, rdf.DJHT["latest_published_version"], uri))
                self.add_container_doi (record, container)
                timeline = value_or_none (record, "timeline")
                rdf.add (self.store, container, rdf.DJHT["first_online_date"],
                         value_or_none (timeline, "firstOnline"), XSD.dateTime)

        return True

    def insert_institution_group (self, record):
        """Procedure to insert a institution group record."""

        uri        = rdf.unique_node ("institution_group")
        self.store.add ((uri, RDF.type, rdf.DJHT["InstitutionGroup"]))

        rdf.add (self.store, uri, rdf.DJHT["id"],                   value_or_none (record, "id"), datatype=XSD.integer)
        rdf.add (self.store, uri, rdf.DJHT["parent_id"],            value_or_none (record, "parent_id"), datatype=XSD.integer)
        ## resource_id is always empty.
        #rdf.add (self.store, uri, rdf.DJHT["resource_id"],          value_or_none (record, "resource_id"), datatype=XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["name"],                 value_or_none (record, "name"), datatype=XSD.string)
        rdf.add (self.store, uri, rdf.DJHT["association_criteria"], value_or_none (record, "association_criteria"), datatype=XSD.string)

        return True

    def insert_static_triplets (self):
        """Procedure to insert triplets to augment the state graph."""

        self.store.add ((rdf.DJHT["DatasetContainer"],    RDFS.subClassOf, rdf.DJHT["Container"]))
        self.store.add ((rdf.DJHT["CollectionContainer"], RDFS.subClassOf, rdf.DJHT["Container"]))

        ## Review states from Figshare.
        self.store.add ((rdf.DJHT["ReviewApproved"],   RDF.type,   rdf.DJHT["ReviewType"]))
        self.store.add ((rdf.DJHT["ReviewApproved"],   RDFS.label, Literal("approved", datatype=XSD.string)))
        self.store.add ((rdf.DJHT["ReviewRejected"],   RDF.type,   rdf.DJHT["ReviewType"]))
        self.store.add ((rdf.DJHT["ReviewRejected"],   RDFS.label, Literal("rejected", datatype=XSD.string)))
        self.store.add ((rdf.DJHT["ReviewClosed"],     RDF.type,   rdf.DJHT["ReviewType"]))
        self.store.add ((rdf.DJHT["ReviewClosed"],     RDFS.label, Literal("closed", datatype=XSD.string)))

        ## We split "pending" into "assigned" and "unassigned" in Djehuty.
        self.store.add ((rdf.DJHT["ReviewAssigned"],   RDF.type,   rdf.DJHT["ReviewType"]))
        self.store.add ((rdf.DJHT["ReviewAssigned"],   RDFS.label, Literal("assigned", datatype=XSD.string)))
        self.store.add ((rdf.DJHT["ReviewUnassigned"], RDF.type,   rdf.DJHT["ReviewType"]))
        self.store.add ((rdf.DJHT["ReviewUnassigned"], RDFS.label, Literal("unassigned", datatype=XSD.string)))

        ## Log event types.
        self.store.add ((rdf.DJHT["LogEntryCite"],     RDF.type,   rdf.DJHT["LogEntryType"]))
        self.store.add ((rdf.DJHT["LogEntryCite"],     RDFS.label, Literal("cite", datatype=XSD.string)))
        self.store.add ((rdf.DJHT["LogEntryDownload"], RDF.type,   rdf.DJHT["LogEntryType"]))
        self.store.add ((rdf.DJHT["LogEntryDownload"], RDFS.label, Literal("download", datatype=XSD.string)))
        self.store.add ((rdf.DJHT["LogEntryGitDownload"], RDF.type,   rdf.DJHT["LogEntryType"]))
        self.store.add ((rdf.DJHT["LogEntryGitDownload"], RDFS.label, Literal("git_download", datatype=XSD.string)))
        self.store.add ((rdf.DJHT["LogEntryShare"],    RDF.type,   rdf.DJHT["LogEntryType"]))
        self.store.add ((rdf.DJHT["LogEntryShare"],    RDFS.label, Literal("share", datatype=XSD.string)))
        self.store.add ((rdf.DJHT["LogEntryView"],     RDF.type,   rdf.DJHT["LogEntryType"]))
        self.store.add ((rdf.DJHT["LogEntryView"],     RDFS.label, Literal("view", datatype=XSD.string)))
        self.store.add ((rdf.DJHT["LogEntryPrivateView"], RDF.type,   rdf.DJHT["LogEntryType"]))
        self.store.add ((rdf.DJHT["LogEntryPrivateView"], RDFS.label, Literal("private_view", datatype=XSD.string)))

        languages = self.__load_resource_file("languages.json")
        for language in languages:
            uri = rdf.unique_node ("language")
            self.store.add ((uri, RDF.type, rdf.DJHT["Language"]))
            self.store.add ((uri, RDFS.label,
                             Literal(language["name"], datatype=XSD.string)))
            self.store.add ((uri, rdf.DJHT["shortcode"],
                             Literal(language["shortcode"], datatype=XSD.string)))

        licenses = self.__load_resource_file ("licenses.json")
        for license_record in licenses:
            self.insert_license (None, license_record)

        groups = self.__load_resource_file ("groups.json")
        for group in groups:
            self.insert_institution_group (group)

        categories = self.__load_resource_file ("root_categories.json")
        for category in categories:
            self.insert_category(category)

        return True
