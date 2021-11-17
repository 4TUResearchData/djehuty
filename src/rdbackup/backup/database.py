from datetime import datetime
from mysql.connector import connect, Error
import ast
import json
import logging
import requests
import xml.etree.ElementTree as ET
from rdbackup.utils import convenience

class DatabaseInterface:

    def __init__(self):
        self.connection = None

    def getFromUrl (self, url: str, headers, parameters):
        """Procedure to perform a GET request to a Figshare-compatible endpoint."""
        response = requests.get(url,
                                headers = headers,
                                params  = parameters)
        if response.status_code == 200:
            return response.text
        else:
            logging.error(f"{url} returned {response.status_code}.")
            logging.error(f"Error message:\n---\n{response.text}\n---")
            return False

    def getFileSizeForCatalog (self, url, article_id):
        total_filesize = 0
        metadata_url   = url.replace(".html", ".xml")
        metadata       = self.getFromUrl(metadata_url, {}, {})
        if not metadata:
            logging.info(f"Couldn't get metadata for {article_id}.")
        else:
            namespaces  = { "c": "http://www.unidata.ucar.edu/namespaces/thredds/InvCatalog/v1.0" }
            xml_root    = ET.fromstring(metadata)
            references  = xml_root.findall(".//c:catalogRef", namespaces)

            ## Recursively handle directories.
            ## XXX: This may overflow the stack.
            if not references:
                logging.info(f"Catalog {url} does not contain subdirectories.")
            else:
                for reference in references:
                    suffix = reference.attrib["{http://www.w3.org/1999/xlink}href"]
                    suburl = metadata_url.replace("catalog.xml", suffix)
                    total_filesize += self.getFileSizeForCatalog(suburl, article_id)

            ## Handle regular files.
            files          = xml_root.findall(".//c:dataSize", namespaces)
            if not files:
                if total_filesize == 0:
                    logging.info(f"There are no files in {url}.")
            else:
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

    def connect(self, host, username, password, database):
        try:
            self.connection = connect(
                host     = host,
                user     = username,
                password = password,
                database = database)
            return self.connection.is_connected()

        except Error as e:
            logging.error("Could not establish connection to database. Reason:")
            logging.error(e)
            return False

    def is_connected (self):
        return self.connection.is_connected()

    def executeQuery (self, template, data):
        try:
            cursor   = self.connection.cursor()
            result = cursor.execute(template, data)
            self.connection.commit()
            cursor.execute("SELECT LAST_INSERT_ID()")
            row = cursor.fetchone()
            return row[0]
        except Error as e:
            logging.error("Executing query failed. Reason:")
            logging.error(e)
            return False

    def insertAccount (self, record):
        template      = ("INSERT IGNORE INTO Account "
                         "(id, active, email, first_name, last_name, "
                         "institution_user_id, institution_id, "
                         "pending_quota_request, used_quota_public, "
                         "used_quota_private, used_quota, maximum_file_size, "
                         "quota, modified_date, created_date) "
                         "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                         "%s, %s, %s, %s)")

        created_date  = convenience.value_or_none (record, "created_date")
        if created_date is not None:
            created_date  = datetime.strptime(record["created_date"], "%Y-%m-%dT%H:%M:%SZ")

        modified_date = convenience.value_or_none (record, "modified_date")
        if modified_date is not None:
            modified_date = datetime.strptime(record["modified_date"], "%Y-%m-%dT%H:%M:%SZ")

        data          = (
            record["id"],
            record["active"],
            record["email"],
            record["first_name"],
            record["last_name"],
            record["institution_user_id"],
            record["institution_id"],
            convenience.value_or_none (record, "pending_quota_request"),
            convenience.value_or_none (record, "used_quota_public"),
            convenience.value_or_none (record, "used_quota_private"),
            convenience.value_or_none (record, "used_quota"),
            convenience.value_or_none (record, "maximum_file_size"),
            convenience.value_or_none (record, "quota"),
            convenience.value_or_none (record, "modified_date"),
            None if not "created_date" in record else datetime.strftime (created_date, "%Y-%m-%d %H:%M:%S")
        )

        return self.executeQuery(template, data)

    def insertInstitution (self, record):
        template = "INSERT IGNORE INTO Institution (id, name) VALUES (%s, %s)"
        data     = (record["institution_id"], record["name"])
        return self.executeQuery(template, data)

    def insertAuthor (self, record, article_id):
        template = ("INSERT IGNORE INTO Author "
                    "(id, full_name, is_active, url_name, orcid_id) "
                    "VALUES (%s, %s, %s, %s, %s)")

        data     = (record["id"],
                    record["full_name"],
                    "is_active" in record and record["is_active"],
                    record["url_name"],
                    None if not "orcid_id" in record else record["orcid_id"])

        if self.executeQuery(template, data):
            template = "INSERT IGNORE INTO ArticleAuthor (article_id, author_id) VALUES (%s, %s)"
            data     = (article_id, record["id"])

            if self.executeQuery(template, data):
                return record["id"]

        return False

    def insertTimeline (self, record, article_id):
        template = ("INSERT IGNORE INTO Timeline "
                    "(revision, firstOnline, publisherPublication, "
                    "publisherAcceptance, posted, submission) "
                    "VALUES (%s, %s, %s, %s, %s, %s)")

        data     = (convenience.value_or_none (record, "revision"),
                    convenience.value_or_none (record, "firstOnline"),
                    convenience.value_or_none (record, "publisherPublication"),
                    convenience.value_or_none (record, "publisherAcceptance"),
                    convenience.value_or_none (record, "posted"),
                    convenience.value_or_none (record, "submission"))

        return self.executeQuery(template, data)

    def insertCategory (self, record, article_id):
        template = ("INSERT IGNORE INTO Category (id, title, parent_id) VALUES (%s, %s, %s)")
        data     = (record["id"], record["title"], record["parent_id"])

        category_id = self.executeQuery(template, data)

        template = "INSERT IGNORE INTO ArticleCategory (category_id, article_id) VALUES (%s, %s)"
        data     = (category_id, article_id)
        return self.executeQuery(template, data)

    def insertTag (self, tag, article_id):
        template = ("INSERT IGNORE INTO Tag (tag, article_id) VALUES (%s, %s)")
        data     = (tag, article_id)

        return self.executeQuery(template, data)

    def insertCustomField (self, field, article_id):
        template    = ("INSERT IGNORE INTO ArticleCustomField (name, value, "
                       "article_id) VALUES (%s, %s, %s)")

        settings    = []
        validations = []
        if "settings" in field:
            settings = field["settings"]
            if "validations" in settings:
                validations = settings["validations"]

        default_value = None
        if "default_value" in settings:
            default_value = settings["default_value"]

        if isinstance(field["value"], list):
            retval = 0

            for value in field["value"]:
                data = (
                    field["name"],
                    default_value if value is None else value,
                    ##None if not "default_value" in settings else settings["default_value"],
                    ##None if not "max_length" in validations else validations["max_length"],
                    ##None if not "min_length" in validations else validations["min_length"],
                    ##None if not "field_type" in field else field["field_type"],
                    ##None if not "is_mandatory" in field else field["is_mandatory"],
                    ##None if not "placeholder" in settings else settings["placeholder"],
                    ##None if not "is_multiple" in settings else settings["is_multiple"],
                    article_id
                )
                retval = self.executeQuery(template, data)
            return retval
        else:
            data    = (
                field["name"],
                default_value if field["value"] is None else field["value"],
                article_id
            )
            return self.executeQuery(template, data)

    def insertCollection (self, record):
        template = ("INSERT IGNORE INTO Collection (url, title, id, modified_date, "
                    "created_date, citation, group_id, institution_id, "
                    "description) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)")

        created_date = None
        if "created_date" in record and not record["created_date"] is None:
            created_date  = datetime.strptime(record["created_date"], "%Y-%m-%dT%H:%M:%SZ")

        modified_date = None
        if "modified_date" in record and not record["modified_date"] is None:
            modified_date = datetime.strptime(record["modified_date"], "%Y-%m-%dT%H:%M:%SZ")

        data     = (
            record["url"],
            record["title"],
            record["id"],
            datetime.strftime (modified_date, "%Y-%m-%d %H:%M:%S"),
            datetime.strftime (created_date, "%Y-%m-%d %H:%M:%S"),
            record["citation"],
            record["group_id"],
            record["institution_id"],
            None if not "description" in record else record["description"]
        )
        if not self.executeQuery(template, data):
            logging.error("Inserting collection failed.")
            return False

        ## Insert links between Collections and authors
        if "authors" in record:
            author_ids = list(map (self.insertAuthor, record["authors"]))
            if not all(author_ids):
                logging.error("Inserting authors of collection failed.")
                return False

            template   = ("INSERT IGNORE INTO CollectionAuthors "
                          "(collection_id, author_id) VALUES (%s, %s)")
            tuples     = map (lambda author_id : (record["id"], author_id), author_ids)
            retvals    = map (lambda record : self.executeQuery(template, record), tuples)

            if all(retvals):
                return True
            else:
                logging.error("Inserting links between a connection and its authors failed.")
                return False

    def insertLicense (self, record):
        template = "INSERT IGNORE INTO License (id, name, url) VALUES (%s, %s, %s)"

        if not self.executeQuery (template, (record["value"], record["name"], record["url"])):
            logging.error("Inserting license failed.")
            return False

        return True

    def insertStatistics (self, record, article_id):
        template = ("INSERT INTO ArticleStatistics (article_id, views, "
                    "downloads, shares, date) VALUES (%s, %s, %s, %s, %s)")

        data = (article_id,
                record["views"],
                record["downloads"],
                record["shares"],
                record["date"])

        return self.executeQuery (template, data)

    def insertFile (self, record, article_id):
        template = ("INSERT IGNORE INTO File (id, name, size, is_link_only, "
                    "download_url, supplied_md5, computed_md5, viewer_type, "
                    "preview_state, status, upload_url, upload_token) VALUES "
                    "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")


        if record["download_url"].startswith("https://opendap.4tu.nl/thredds") and record["size"] == 0:
            metadata_url   = record["download_url"].replace(".html", ".xml")
            metadata       = self.getFromUrl(metadata_url, {}, {})
            record["size"] = self.getFileSizeForCatalog(record["download_url"], article_id)

        data = (record["id"],
                record["name"],
                record["size"],
                record["is_link_only"],
                record["download_url"],
                record["supplied_md5"],
                record["computed_md5"],
                record["viewer_type"],
                record["preview_state"],
                record["status"],
                record["upload_url"],
                record["upload_token"])

        if self.executeQuery (template, data):
            template = "INSERT IGNORE INTO ArticleFile (article_id, file_id) VALUES (%s, %s)"
            data     = (article_id, record["id"])
            if self.executeQuery (template, data):
                return record["id"]

        return False

    def insertArticleReference (self, url, article_id):
        template = "INSERT IGNORE INTO ArticleReference (article_id, url) VALUES (%s, %s)"
        data     = (article_id, url)

    def insertArticle (self, record):
        template = ("INSERT IGNORE INTO Article (id, account_id, title, doi, "
                    "handle, group_id, url, url_public_html, url_public_api, "
                    "url_private_html, url_private_api, published_date, thumb, "
                    "defined_type, defined_type_name, is_embargoed, citation, "
                    "has_linked_file, metadata_reason, confidential_reason, "
                    "is_metadata_record, is_confidential, is_public, "
                    "modified_date, created_date, size, status, version, "
                    "description, figshare_url, resource_doi, resource_title, "
                    "timeline_id, license_id) VALUES (%s, %s, %s, %s, %s, %s, "
                    "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                    "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")

        article_id  = record["id"]
        timeline_id = None
        if "timeline" in record:
            timeline_id = self.insertTimeline(record["timeline"], article_id)

        ## embargo_option_id = 0
        ## embargo_id        = self.insertArticleEmbargo(record)

        references = record["references"]
        for url in references:
            self.insertArticleReference(url, article_id)

        categories = record["categories"]
        for category in categories:
            self.insertCategory (category, article_id)

        license_id = record["license"]["value"]
        self.insertLicense (record["license"])

        tags = record["tags"]
        for tag in tags:
            self.insertTag(tag, article_id)

        authors = record["authors"]
        for author in authors:
            self.insertAuthor(author, article_id)

        files = record["files"]
        for file in files:
            self.insertFile(file, article_id)

        if "statistics" in record:
            stats = record["statistics"]
            for day in stats:
                self.insertStatistics(day, article_id)

        created_date = None
        if "created_date" in record and not record["created_date"] is None:
            created_date  = datetime.strptime(record["created_date"], "%Y-%m-%dT%H:%M:%SZ")

        modified_date = None
        if "modified_date" in record and not record["modified_date"] is None:
            modified_date = datetime.strptime(record["modified_date"], "%Y-%m-%dT%H:%M:%SZ")

        custom_fields = record["custom_fields"]
        for field in custom_fields:
            self.insertCustomField(field, article_id)

        data          = (article_id,
                         record["account_id"],
                         record["title"],
                         record["doi"],
                         record["handle"],
                         record["group_id"],
                         record["url"],
                         record["url_public_html"],
                         record["url_public_api"],
                         record["url_private_html"],
                         record["url_private_api"],
                         record["published_date"],
                         record["thumb"],
                         record["defined_type"],
                         record["defined_type_name"],
                         "is_embargoed" in record and record["is_embargoed"],
                         record["citation"],
                         "has_linked_file" in record and record["has_linked_file"],
                         record["metadata_reason"],
                         record["confidential_reason"],
                         record["is_metadata_record"],
                         record["is_confidential"],
                         record["is_public"],
                         modified_date,
                         created_date,
                         record["size"],
                         record["status"],
                         record["version"],
                         record["description"],
                         record["figshare_url"],
                         record["resource_doi"],
                         record["resource_title"],
                         timeline_id,
                         license_id)

        if not self.executeQuery(template, data):
            logging.error("Inserting article failed.")
            return False

        return True

    def disconnect(self):
        self.connection.commit()
        cursor = self.connection.cursor()
        cursor.close()
        self.connection.close()
        return True
