"""This module provides an interface to store data fetched by the 'figshare' module."""

import xml.etree.ElementTree as ET
import ast
import logging
from datetime import datetime
from secrets import token_urlsafe
from rdflib import Graph, Literal, RDF, XSD, URIRef
import requests
from djehuty.utils.convenience import value_or, value_or_none
from djehuty.utils import rdf

class DatabaseInterface:
    """
    A class that serializes the output produced by the 'figshare'
    module as RDF.
    """

    def __init__(self):
        self.store = Graph()

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

    def __get_file_size_for_catalog (self, url):
        """Returns the file size for an OPeNDAP catalog."""
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
        if not references:
            logging.debug("Catalog %s does not contain subdirectories.", url)
        else:
            for reference in references:
                suffix = reference.attrib["{http://www.w3.org/1999/xlink}href"]
                suburl = metadata_url.replace("catalog.xml", suffix)
                total_filesize += self.__get_file_size_for_catalog (suburl)

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
        body = self.store.serialize(format="ntriples")
        if isinstance(body, bytes):
            body = body.decode('utf-8')

        print(body)

    def insert_account (self, record):
        """Procedure to add an account record to GRAPH."""

        uri = rdf.unique_node ("account")
        self.store.add ((uri, RDF.type, rdf.SG["Account"]))

        rdf.add (self.store, uri, rdf.COL["id"],                    value_or (record, "id", None),           XSD.integer)
        rdf.add (self.store, uri, rdf.COL["active"],                value_or (record, "active", False),      XSD.boolean)
        rdf.add (self.store, uri, rdf.COL["email"],                 value_or (record, "email", None),        XSD.string)
        rdf.add (self.store, uri, rdf.COL["first_name"],            value_or (record, "first_name", None),   XSD.string)
        rdf.add (self.store, uri, rdf.COL["last_name"],             value_or (record, "last_name", None),    XSD.string)
        rdf.add (self.store, uri, rdf.COL["institution_user_id"],   value_or (record, "institution_user_id", None), XSD.string)
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
        rdf.add (self.store, uri, rdf.COL["first_online_date"], value_or_none (record, "firstOnline"),          XSD.dateTime)
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
            rdf.add (self.store, field_uri, rdf.COL["name"],         name,                                        XSD.string)
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

    def insert_collection (self, record, account_id):
        """Procedure to insert a collection record."""

        collection_id  = record["id"]
        uri            = rdf.unique_node ("collection")

        is_public          = bool (value_or (record, "is_public", False))
        is_latest          = bool (value_or (record, "is_latest", False))
        is_editable        = bool (value_or (record, "is_editable", False))

        self.store.add ((uri, RDF.type,                 rdf.SG["Collection"]))
        self.store.add ((uri, rdf.COL["collection_id"], Literal(collection_id, datatype=XSD.integer)))

        rdf.add (self.store, uri, rdf.COL["url"],                 value_or_none (record, "url"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["title"],               value_or_none (record, "title"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["published_date"],      value_or_none (record, "published_date"), XSD.dateTime)
        rdf.add (self.store, uri, rdf.COL["created_date"],        value_or_none (record, "created_date"), XSD.dateTime)
        rdf.add (self.store, uri, rdf.COL["modified_date"],       value_or_none (record, "modified_date"), XSD.dateTime)
        rdf.add (self.store, uri, rdf.COL["doi"],                 value_or_none (record, "doi"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["citation"],            value_or_none (record, "citation"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["account_id"],          account_id, XSD.integer)
        rdf.add (self.store, uri, rdf.COL["group_id"],            value_or_none (record, "group_id"), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["group_resource_id"],   value_or_none (record, "group_resource_id"), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["institution_id"],      value_or_none (record, "institution_id"), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["description"],         value_or_none (record, "description"), XSD.string)
        rdf.add (self.store, uri, rdf.COL["version"],             value_or_none (record, "version"), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["resource_id"],         value_or_none (record, "resource_id"), XSD.integer)
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

        if "statistics" in record:
            stats     = record["statistics"]
            self.insert_collection_totals (stats["totals"], collection_id)
        elif is_public and is_latest:
            logging.warning ("No statistics available for collection %d.", collection_id)

        for field in value_or (record, "custom_fields", []):
            self.insert_custom_field (uri, field)

        self.insert_item_list (uri, value_or (record, "articles", []), "articles")

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
            self.store.add ((license_uri, RDF.type, rdf.SG["License"]))
            self.store.add ((license_uri, rdf.COL["name"],
                             Literal(license_name, datatype=XSD.string)))

        ## Insert the link between URI and the license.
        self.store.add ((uri, rdf.COL["license"], license_uri))

        return True

    def insert_totals_statistics (self, record, item_id, item_type="article"):
        """Procedure to insert simplified totals for an article or collection."""

        if record is None:
            return None

        prefix = item_type.capitalize()
        uri    = rdf.unique_node ("statistics")
        now    = datetime.strftime (datetime.now(), "%Y-%m-%dT%H:%M:%SZ")

        self.store.add ((uri, RDF.type, rdf.SG[f"{prefix}Totals"]))
        rdf.add (self.store, uri, rdf.COL[f"{item_type}_id"], item_id, XSD.integer)
        rdf.add (self.store, uri, rdf.COL["views"],      value_or_none (record, "views"), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["downloads"],  value_or_none (record, "downloads"), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["shares"],     value_or_none (record, "shares"), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["cites"],      value_or_none (record, "cites"), XSD.integer)
        rdf.add (self.store, uri, rdf.COL["created_at"], now, XSD.dateTime)

        return True

    def insert_article_totals (self, record, article_id):
        """Procedure to insert totals statistics for an article."""

        return self.insert_totals_statistics (record,
                                              item_id=article_id,
                                              item_type="article")

    def insert_collection_totals (self, record, collection_id):
        """Procedure to insert totals statistics for a collection."""

        return self.insert_totals_statistics (record,
                                              item_id=collection_id,
                                              item_type="collection")

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

    def insert_article (self, record):
        """Procedure to insert an article record."""

        article_id = value_or_none (record, "id")
        if article_id is None:
            return False

        account_id = value_or_none (record, "account_id")
        uri        = rdf.unique_node ("article")

        self.store.add ((uri, RDF.type,              rdf.SG["Article"]))
        self.store.add ((uri, rdf.COL["article_id"], Literal(article_id, datatype=XSD.integer)))

        self.insert_timeline (uri, value_or_none (record, "timeline"))
        self.insert_license (uri, value_or_none (record, "license"))

        is_embargoed       = bool (value_or (record, "is_embargoed", False))
        is_public          = bool (value_or (record, "is_public", False))
        is_latest          = bool (value_or (record, "is_latest", False))
        is_editable        = bool (value_or (record, "is_editable", False))
        is_confidential    = bool (value_or (record, "is_confidential", False))
        is_metadata_record = bool (value_or (record, "is_metadata_record", False))
        has_linked_file    = bool (value_or (record, "has_linked_file", False))

        rdf.add (self.store, uri, rdf.COL["account_id"],          account_id, XSD.integer)
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

        if "statistics" in record:
            stats = record["statistics"]
            self.insert_article_totals (stats["totals"], article_id)
        elif is_latest:
            logging.warning ("No statistics available for article %d.", article_id)

        for field in value_or (record, "custom_fields", []):
            self.insert_custom_field (uri, field)

        return True

    def insert_institution_group (self, record):
        """Procedure to insert a institution group record."""

        uri        = rdf.unique_node ("institution_group")
        self.store.add ((uri, RDF.type, rdf.SG["InstitutionGroup"]))

        rdf.add (self.store, uri, rdf.COL["id"],                   value_or_none (record, "id"), datatype=XSD.integer)
        rdf.add (self.store, uri, rdf.COL["parent_id"],            value_or_none (record, "parent_id"), datatype=XSD.integer)
        rdf.add (self.store, uri, rdf.COL["resource_id"],          value_or_none (record, "resource_id"), datatype=XSD.string)
        rdf.add (self.store, uri, rdf.COL["name"],                 value_or_none (record, "name"), datatype=XSD.string)
        rdf.add (self.store, uri, rdf.COL["association_criteria"], value_or_none (record, "association_criteria"), datatype=XSD.string)

        return True
