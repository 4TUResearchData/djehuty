"""This module provides an interface to extract data from Figshare."""

from datetime import datetime
from datetime import timedelta
import concurrent.futures
import multiprocessing
import time
import logging
import requests

class FigshareEndpoint:
    """
    This class provides the functionality to retrieve information using the
    Figshare API.  It is tailored to retrieve all metadata related to
    4TU.ResearchData.
    """

    def __init__ (self):
        self.api_location     = "/v2"
        self.domain           = "api.figshare.com"
        self.base             = "https://api.figshare.com/v2"
        self.token            = None
        self.stats_auth       = None
        self.institution_id   = 898 # Defaults to 4TU.ResearchData
        self.institution_name = "4tu"

    # REQUEST HANDLING PROCEDURES
    # -----------------------------------------------------------------------------

    def __request_headers (self, additional_headers=None):
        """Returns a dictionary of HTTP headers"""
        defaults = {
            "Accept":        "application/json",
            "Authorization": "token " + self.token,
            "Content-Type":  "application/json",
            "User-Agent":    "rdbackup"
        }
        if not additional_headers is None:
            return { **defaults, **additional_headers }

        return defaults

    def get_statistics (self, path: str, headers, parameters):
        """Procedure to perform a GET request to a Figshare-compatible endpoint."""
        response = requests.get("https://stats.figshare.com" + path,
                                headers = headers,
                                params  = parameters)
        if response.status_code == 200:
            return response.json()

        logging.error("%s returned %d.", path, response.status_code)
        return []

    def get (self, path: str, headers, parameters):
        """Procedure to perform a GET request to a Figshare-compatible endpoint."""
        response = requests.get(self.base + path,
                                headers = headers,
                                params  = parameters)
        if response.status_code == 200:
            return response.json()

        logging.error("%s returned %d.", path, response.status_code)
        logging.error("Error message:\n---\n%s\n---", response.text)
        return []

    def post (self, path: str, parameters):
        """Procedure to perform a POST request to a Figshare-compatible endpoint."""
        return requests.post (self.base + path, parameters)

    # API SPECIFICS
    # -----------------------------------------------------------------------------

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

        if not published_since is None:
            parameters["published_since"] = published_since

        if not published_until is None:
            parameters["published_until"] = published_until

        if not published_since is None and not published_until is None:
            parameters["order"]           = "published_date"
            parameters["order_direction"] = "desc"

        if not impersonate is None:
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
        number_of_pages = multiprocessing.cpu_count()

        ## We fetch pages concurrently in a loop because we cannot predict
        ## when we have fetched all items.  We can test whether there are
        ## more items to fetch by comparing the number of fetched articles
        ## to the number of articles it should've fetched.
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
        logging.info("Fetched %d items in %.2f seconds", total_fetched, end_time - start_time)
        return total

    def get_articles (self,
                      published_since="1970-01-01",
                      published_until="2300-01-01"):
        """Procedure to get articles from the Figshare API."""

        return self.get_all ("/articles",
                             published_since = published_since,
                             published_until = published_until)

    def get_article_details_by_account_by_id (self, account_id, article_id):
        """Procedure to get detailed article information for a given account_id."""

        headers      = self.__request_headers()
        parameters   = { "impersonate": account_id }
        record       = self.get(f"/account/articles/{article_id}", headers, parameters)

        now          = datetime.now()
        created_date = now
        if "created_date" in record and not record["created_date"] is None:
            created_date  = datetime.strptime(record["created_date"]
                                              .replace("Z", "")
                                              .replace("T", " "),
                                              "%Y-%m-%d %H:%M:%S")

        record["account_id"] = account_id
        record["statistics"] = self.get_statistics_for_article(
            article_id,
            datetime.strftime(created_date, "%Y-%m-%d"),
            datetime.strftime(now, "%Y-%m-%d"))

        return record

    def get_articles_by_account (self, account_id):
        """Procedure to get articles for a given account_id."""

        summaries = self.get_all ("/account/articles", impersonate=account_id)
        if not summaries:
            return []

        article_ids = list(map(lambda article : article['id'], summaries))
        with concurrent.futures.ThreadPoolExecutor() as executor:
            start_time = time.perf_counter()
            articles = [executor.submit(self.get_article_details_by_account_by_id,
                                        account_id,
                                        article_id)
                        for article_id in article_ids]
            results = list(map(lambda item : item.result(), articles))
            end_time   = time.perf_counter()
            total_fetched = len(results)
            logging.info("Fetched %d full articles in %.2f seconds",
                         total_fetched, end_time - start_time)
            return results

    def get_collections_by_account (self, account_id):
        """Procedure to get collections for a given account_id."""

        logging.info("Getting collections for account %d.", account_id)
        summaries = self.get_all ("/account/collections", impersonate=account_id)

        collection_ids = list(map(lambda collection : collection['id'], summaries))
        with concurrent.futures.ThreadPoolExecutor() as executor:
            start_time  = time.perf_counter()
            collections = [executor.submit(self.get_collection_by_id,
                                        account_id,
                                        collection_id)
                        for collection_id in collection_ids]
            results     = list(map(lambda item : item.result(), collections))
            end_time   = time.perf_counter()
            total_fetched = len(results)
            logging.info("Fetched %d full collections in %.2f seconds",
                         total_fetched, end_time - start_time)
            return results

    def get_collection_by_id (self, account_id, collection_id):
        """Procedure to get detailed collection information."""

        headers      = self.__request_headers ()
        parameters   = { "impersonate": account_id }
        record       = self.get(f"/account/collections/{collection_id}",
                                headers, parameters)

        record["account_id"] = account_id
        return record

    def get_collections (self, published_since="1970-01-01"):
        """Procedure to get collections."""

        logging.info("Getting collections.")
        return self.get_all ("/collections", published_since=published_since)

    def get_article_versions (self, article_id):
        """Procedure to get versioning information for an article."""

        headers  = self.__request_headers ()
        versions = self.get (f"/articles/{article_id}/versions", headers, {})
        output   = []

        for item in versions:
            version = item["version"]
            record  = self.get (f"/articles/{article_id}/versions/{version}", headers, {})
            output.append (record)

        return output

    def get_projects (self):
        """Procedure to get projects."""

        logging.info("Getting projects.")
        return self.get_all ("/projects")

    def get_institutional_accounts (self):
        """Procedure to get institutional accounts."""

        logging.info("Getting institutional accounts.")
        return self.get_all ("/account/institution/accounts")

    def get_statistics_for_article (self,
                                    article_id,
                                    start_date = None,
                                    end_date   = None):
        """Procedure to get statistics for an article."""

        if self.stats_auth is None:
            return [{
                "views":      0,
                "downloads":  0,
                "shares":     0,
                "date":       datetime.strftime(datetime.now(), "%Y-%m-%d")
            }]

        headers    = self.__request_headers()
        headers["Authorization"] = f"Basic {self.stats_auth}"

        output     = []
        if start_date is None:
            start_date = datetime.strftime(datetime.now() - timedelta(days=365), "%Y-%m-%d")

        if end_date is None:
            end_date    = datetime.strftime(datetime.now(), "%Y-%m-%d") ##  + timedelta(days=1)

        parameters = {
            "start_date": start_date,
            "end_date":   end_date
        }
        prefix     = "/4tu/timeline/day"
        views      = self.get_statistics (f"{prefix}/views/article/{article_id}", headers, parameters)
        downloads  = self.get_statistics (f"{prefix}/downloads/article/{article_id}", headers, parameters)
        shares     = self.get_statistics (f"{prefix}/shares/article/{article_id}", headers, parameters)

        if not views or views["timeline"] is None:
            output.append({
                "views":      0,
                "downloads":  0,
                "shares":     0,
                "date":       datetime.strftime(datetime.now(), "%Y-%m-%d")
            })
        else:
            dates = list(views["timeline"].keys())
            for date in dates:
                nviews     = views["timeline"][date]
                ndownloads = downloads["timeline"][date] if downloads["timeline"] is not None and date in downloads["timeline"] else 0
                nshares    = shares["timeline"][date]    if shares["timeline"] is not None and date in shares["timeline"] else 0

                output.append({
                    "views":      nviews,
                    "downloads":  ndownloads,
                    "shares":     nshares,
                    "date":       date
                })

        return output
