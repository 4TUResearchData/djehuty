"""This module provides an interface to extract data from Figshare."""

from datetime import datetime
from threading import Lock
import concurrent.futures
import os
import time
import logging
import json
import requests

from djehuty.utils import convenience as conv

class FigshareEndpoint:
    """
    This class provides the functionality to retrieve information using the
    Figshare API.  It is tailored to retrieve all metadata related to
    4TU.ResearchData.
    """

    def __init__ (self, maximum_simultaneous_connections=None):
        self.base             = "https://api.figshare.com/v2"
        self.token            = None
        self.stats_base       = "https://stats.figshare.com"
        self.stats_auth       = None
        self.institution_id   = 898 # Defaults to 4TU.ResearchData
        self.institution_name = "4tu"
        self.rdf_store        = None
        self.author_ids       = {}
        self.author_ids_lock  = Lock()
        self.requests         = requests.Session()

        if maximum_simultaneous_connections is None:
            maximum_simultaneous_connections = os.cpu_count()

        # Modify connection pooling settings.
        adapter = requests.adapters.HTTPAdapter(
            pool_connections = 2,
            pool_maxsize     = maximum_simultaneous_connections,
            pool_block       = False)
        self.requests.mount('https://', adapter)

    # REQUEST HANDLING PROCEDURES
    # -----------------------------------------------------------------------------

    def __request_headers (self, additional_headers=None):
        """Returns a dictionary of HTTP headers"""
        defaults = {
            "Accept":        "application/json",
            "Authorization": "token " + self.token,
            "Content-Type":  "application/json",
            "User-Agent":    "Djehuty"
        }
        if additional_headers is not None:
            return { **defaults, **additional_headers }

        return defaults

    def get_statistics (self, path: str, headers, parameters):
        """Procedure to perform a GET request to a Figshare-compatible endpoint."""
        response = self.requests.get(f"{self.stats_base}{path}",
                                     headers = headers,
                                     params  = parameters)
        if response.status_code == 200:
            return response.json()

        logging.error("%s returned %d.", path, response.status_code)
        return []

    def get (self, path: str, headers, parameters):
        """Procedure to perform a GET request to a Figshare-compatible endpoint."""
        try:
            response = self.requests.get(self.base + path,
                                         headers = headers,
                                         params  = parameters)
            if response.status_code == 200:
                return response.json()

            logging.error("%s returned %d.", path, response.status_code)
            logging.error("Parameters:\n---\n%s\n---", parameters)
            logging.error("Error message:\n---\n%s\n---", response.text)
        except requests.exceptions.SSLError as error:
            logging.error ("SSLError: %s", error)

        return []

    def post (self, path: str, parameters):
        """Procedure to perform a POST request to a Figshare-compatible endpoint."""
        return self.requests.post (self.base + path, parameters)

    # API SPECIFICS
    # -----------------------------------------------------------------------------

    def get_record (self, path, impersonate=None):
        """Procedure to get a single record from the Figshare API."""

        headers    = self.__request_headers()
        parameters = {}

        if impersonate is not None:
            parameters["impersonate"] = impersonate

        chunk      = self.get(path, headers, parameters)
        return chunk

    def get_one_page (self,
                      path,
                      page_size,
                      page,
                      institution_id=None,
                      published_since=None,
                      published_until=None,
                      impersonate=None):
        """Procedure to get one results page from the Figshare API."""

        ## Even though 'page_size' is a parameter, any setting higher than 10
        ## does not provide more than 10 results.

        if institution_id is None:
            institution_id = self.institution_id

        headers    = self.__request_headers()
        parameters = {
            "page_size": page_size,
            "page": page,
            "institution": institution_id,
        }

        if published_since is not None:
            parameters["published_since"] = published_since

        if published_until is not None:
            parameters["published_until"] = published_until

        if published_since is not None and published_until is not None:
            parameters["order"]           = "published_date"
            parameters["order_direction"] = "desc"

        if impersonate is not None:
            parameters["impersonate"] = impersonate

        chunk      = self.get(path, headers, parameters)
        return chunk

    def get_all (self,
                 path,
                 institution_id=None,
                 published_since=None,
                 published_until=None,
                 impersonate=None):
        """Procedure to get all results from the Figshare API."""

        if institution_id is None:
            institution_id = self.institution_id

        ## It almost seems as if Figshare artificially delays each request by
        ## roughly one second.  This makes serial retrieval slow.  Instead we
        ## adopt a parallel retrieval strategy where we do N requests
        ## simultaneously and merge the results afterwards.  N is set to
        ## the number of cores available on the machine, because each page
        ## will be fetched in a separate thread.

        total = []
        number_of_pages = os.cpu_count()

        ## We fetch pages concurrently in a loop because we cannot predict
        ## when we have fetched all items.  We can test whether there are
        ## more items to fetch by comparing the number of fetched datasets
        ## to the number of datasets it should've fetched.
        start_page = 1
        start_time = time.perf_counter()

        ## Instead of letting the program iterate indefinitely, we limit
        ## the number of iterations to a high amount. You have to multiply
        ## the number of iterations with the number of CPUs and then by ten
        ## to know how many items will be fetched.
        iteration = 0
        fetch_more = True
        while iteration < 10000 and fetch_more:
            end_page   = start_page + number_of_pages
            with concurrent.futures.ThreadPoolExecutor() as executor:
                results = [executor.submit(self.get_one_page,
                                           path,
                                           10,
                                           page,
                                           institution_id,
                                           published_since,
                                           published_until,
                                           impersonate)
                           for page in range(start_page, end_page)]
                for response in results:
                    result = response.result()
                    num_result = len(result)
                    if num_result > 0:
                        total.extend(result)

                    if len(result) < 10:
                        fetch_more = False

            start_page = end_page
            iteration += 1

        end_time   = time.perf_counter()
        total_fetched = len(total)
        logging.debug ("Fetched %d items in %.2f seconds", total_fetched, end_time - start_time)
        return total

    def get_datasets (self,
                      published_since="1970-01-01",
                      published_until="2300-01-01"):
        """Procedure to get datasets from the Figshare API."""

        return self.get_all ("/articles",
                             published_since = published_since,
                             published_until = published_until)

    def get_dataset_details_by_account_by_id (self, account_id, account_uri, dataset_id):
        """Procedure to get detailed dataset information for a given account_id."""

        headers      = self.__request_headers()
        parameters   = { "impersonate": account_id }
        record       = self.get(f"/account/articles/{dataset_id}", headers, parameters)

        if isinstance(record, list):
            logging.error ("Failed to get dataset %d for account %d.", dataset_id, account_id)
            logging.error ("Received: %s", json.dumps(record))
            return None

        authors = []

        try:
            with self.author_ids_lock:
                for author in record["authors"]:
                    author_id = conv.value_or_none (author, "id")
                    if author_id in self.author_ids:
                        authors.append (self.author_ids[author_id])
                    else:
                        details = self.get_author_details_by_id (author_id, account_id)
                        self.author_ids[author_id] = details
                        authors.append (details)
        except TypeError:
            logging.error ("Failed to process authors for account %d", account_id)

        record["authors"]       = authors
        record["private_links"] = self.get_dataset_private_links_by_account_by_id (account_id,
                                                                                   dataset_id)
        record["account_id"]    = account_id
        record["account_uri"]   = account_uri
        record["is_latest"]     = 0
        record["is_editable"]   = 1

        ## Other versions
        ## --------------------------------------------------------------------
        current_version         = conv.value_or_none (record, "version")

        # In the private version, the version is reset to None to avoid
        # confusing it with the public/published version.
        record["version"]       = None

        if conv.value_or (record, "is_public", False):
            versions = self.get_dataset_versions (dataset_id, account_id,
                                                  latest=current_version)
            record["versions"] = versions
        else:
            reviews = self.get_dataset_reviews (dataset_id)
            if reviews:
                record["review"] = reviews[0]

        ## Statistics
        ## --------------------------------------------------------------------
        if conv.value_or (record, "is_public", False):
            now          = datetime.strftime(datetime.now(), "%Y-%m-%d")
            created_date = "2020-07-01"

            if "created_date" in record and not record["created_date"] is None:
                date         = datetime.strptime(record["created_date"]
                                                 .replace("Z", "")
                                                 .replace("T", " "),
                                                 "%Y-%m-%d %H:%M:%S")
                created_date = datetime.strftime(date, "%Y-%m-%d")

            record["statistics"] = self.get_statistics_for_dataset(dataset_id,
                                                                   created_date,
                                                                   now)

        return record

    def get_dataset_private_links_by_account_by_id (self, account_id, dataset_id):
        """Procedure to get private links to a dataset."""

        headers    = self.__request_headers()
        parameters = { "impersonate": account_id }
        record     = self.get(f"/account/articles/{dataset_id}/private_links",
                              headers,
                              parameters)
        return record

    def get_collection_private_links_by_account_by_id (self, account_id, collection_id):
        """Procedure to get private links to an collection."""

        headers    = self.__request_headers()
        parameters = { "impersonate": account_id }
        record     = self.get(f"/account/collections/{collection_id}/private_links",
                              headers,
                              parameters)
        return record

    def get_datasets_by_account (self, account_id, account_uri):
        """Procedure to get datasets for a given account_id."""

        summaries = self.get_all ("/account/articles", impersonate=account_id)
        if not summaries:
            return []

        dataset_ids = list(map(lambda dataset : dataset['id'], summaries))
        with concurrent.futures.ThreadPoolExecutor() as executor:
            start_time = time.perf_counter()
            datasets = [executor.submit(self.get_dataset_details_by_account_by_id,
                                        account_id,
                                        account_uri,
                                        dataset_id)
                        for dataset_id in dataset_ids]
            results = list(map(lambda item : item.result(), datasets))
            end_time   = time.perf_counter()
            total_fetched = len(results)
            logging.debug ("Fetched %d full datasets in %.2f seconds",
                           total_fetched, end_time - start_time)
            return results

    def get_collections_by_account (self, account_id, account_uri):
        """Procedure to get collections for a given account_id."""

        logging.info("Getting collections for account %d.", account_id)
        summaries = self.get_all ("/account/collections", impersonate=account_id)

        collection_ids = list(map(lambda collection : collection['id'], summaries))
        with concurrent.futures.ThreadPoolExecutor() as executor:
            start_time  = time.perf_counter()
            collections = [executor.submit(self.get_collection_by_id,
                                           account_id,
                                           account_uri,
                                           collection_id)
                        for collection_id in collection_ids]
            results     = list(map(lambda item : item.result(), collections))
            end_time   = time.perf_counter()
            total_fetched = len(results)
            logging.debug ("Fetched %d full collections in %.2f seconds",
                         total_fetched, end_time - start_time)
            return results

    def get_collection_by_id (self, account_id, account_uri, collection_id):
        """Procedure to get detailed collection information."""

        headers      = self.__request_headers ()
        parameters   = { "impersonate": account_id }
        record       = self.get(f"/account/collections/{collection_id}",
                                headers, parameters)
        datasets     = self.get_datasets_for_collection (account_id,
                                                         collection_id)
        authors      = []
        for author in record["authors"]:
            details = self.get_author_details_by_id (author["id"], account_id)
            authors.append(details)

        private_links = self.get_collection_private_links_by_account_by_id (account_id,
                                                                            collection_id)

        record["authors"]       = authors
        record["private_links"] = private_links
        record["datasets"]      = datasets
        record["account_id"]    = account_id
        record["account_uri"]   = account_uri
        record["is_latest"]     = 0
        record["is_editable"]   = 1

        ## Other versions
        ## --------------------------------------------------------------------
        current_version         = conv.value_or_none (record, "version")
        record["version"]       = None

        if conv.value_or (record, "public", False):
            numbers = self.get_collection_versions (collection_id, account_id)
            versions = []
            for number_record in numbers:
                number = number_record['version']
                versioned_record = self.get_record(f"/collections/{collection_id}/versions/{number}")
                versioned_record["is_latest"]   = 0
                versioned_record["is_editable"] = 0
                version = conv.value_or_none (versioned_record, "version")
                if current_version is not None and version == current_version:
                    datasets = self.get_datasets_for_collection (account_id,
                                                                 collection_id,
                                                                 is_public = True)
                    versioned_record["is_latest"] = 1
                    versioned_record["datasets"]  = datasets

                versions.append(versioned_record)

            record["versions"] = versions

        ## Statistics
        ## --------------------------------------------------------------------
        record["statistics"] = self.get_statistics_for_collection(
           collection_id,
           None,
           datetime.strftime(datetime.now(), "%Y-%m-%d"))

        return record

    def get_collections (self, published_since="1970-01-01"):
        """Procedure to get collections."""

        logging.info("Getting collections.")
        return self.get_all ("/collections", published_since=published_since)

    def get_datasets_for_collection (self, account_id, collection_id, is_public=False):
        """Procedure to retrieve the datasets for a given collection."""

        prefix      = "" if is_public else "/account"
        uri_path    = f"{prefix}/collections/{collection_id}/articles"
        impersonate = None if is_public else account_id
        datasets    = self.get_all (uri_path, impersonate=impersonate)
        output      = []

        for item in datasets:
            output.append (item["id"])

        return output

    def get_dataset_versions (self, dataset_id, account_id, exclude=None,
                              latest=None):
        """Procedure to get versioning information for a dataset."""

        headers  = self.__request_headers ()
        versions = self.get (f"/articles/{dataset_id}/versions", headers, {})
        output   = []
        reviews  = self.get_dataset_reviews (dataset_id)

        for item in versions:
            version = item["version"]
            if exclude is None or version != exclude:
                record  = self.get_record (f"/articles/{dataset_id}/versions/{version}")
                record["account_id"] = account_id
                record["is_latest"]  = 0
                record["is_editable"]= 0
                record["review"] = next((item for item in reviews if item["version"] == int(version)), None)

                if  latest is not None and version == latest:
                    record["is_latest"] = 1

                output.append (record)

        return output

    def get_collection_versions (self, collection_id, account_id, exclude=None):
        """Procedure to get versioning information for a collection."""

        headers  = self.__request_headers ()
        versions = self.get (f"/collections/{collection_id}/versions", headers, {})
        output   = []

        for item in versions:
            version = item["version"]
            if exclude is None or version != exclude:
                record = self.get (f"/collections/{collection_id}/versions/{version}", headers, {})
                record["account_id"] = account_id
                output.append (record)

        return output

    def get_projects (self):
        """Procedure to get projects."""

        logging.info("Getting projects.")
        return self.get_all ("/projects")

    def get_institutional_accounts (self, account_id=None):
        """Procedure to get institutional accounts."""

        logging.info("Getting institutional accounts.")
        if account_id is None:
            return self.get_all ("/account/institution/accounts")

        return self.get ("/account/institution/accounts",
                         self.__request_headers (), {
                             "id_lte": account_id,
                             "id_gte": account_id
                         })

    def get_dataset_reviews (self, dataset_id):
        """Procedure to get review information of datasets."""
        return self.get ("/account/institution/reviews", self.__request_headers (), {
            "article_id": dataset_id,
            "limit": 10
        })

    def get_author_details_by_id (self, author_id, account_id):
        """Procedure to get a detailed author record."""

        return self.get_record (f"/account/authors/{author_id}",
                                impersonate=account_id)

    def get_statistics_for_type (self,
                                 item_id,
                                 item_type,
                                 start_date = None,
                                 end_date   = None):
        """Procedure to get statistics for a dataset or collection."""

        if self.stats_auth is None:
            logging.info("Missing authentication for the statistics endpoint.")
            return {
                "views":     None,
                "downloads": None,
                "shares":    None,
                "totals":    None,
            }

        headers    = self.__request_headers()
        headers["Authorization"] = f"Basic {self.stats_auth}"

        output     = None
        totals     = self.get_statistics (f"/total/{item_type}/{item_id}", headers, {})

        try:
            output = {
                "views":     None,
                "downloads": None,
                "shares":    None,
                "totals":    totals
            }
        except KeyError:
            logging.error ("Failed to gather statistics for %s %d.",
                           item_type, item_id)
            output = {
                "views":      None,
                "downloads":  None,
                "shares":     None,
                "totals":     None
            }

        return output

    def get_statistics_for_dataset (self,
                                    dataset_id,
                                    start_date = None,
                                    end_date   = None):
        """Procedure to get statistics for a dataset."""
        return self.get_statistics_for_type (item_id    = dataset_id,
                                             item_type  = "article",
                                             start_date = start_date,
                                             end_date   = end_date)

    def get_statistics_for_collection (self,
                                       collection_id,
                                       start_date = None,
                                       end_date   = None):
        """Procedure to get statistics for a collection."""
        return self.get_statistics_for_type (item_id    = collection_id,
                                             item_type  = "collection",
                                             start_date = start_date,
                                             end_date   = end_date)

    def get_institutional_groups (self):
        """Procedure to get groups of an institution."""
        return self.get_record ("/account/institution/groups")

    def get_author_for_account (self, account_id):
        """Procedure to get the author linked to an account."""

        try:
            record = self.get_record (f"/account/institution/users/{account_id}")
            if record:
                return record["id"]
        except KeyError:
            pass

        return None
