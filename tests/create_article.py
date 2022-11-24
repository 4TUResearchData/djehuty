"""
This module describes the API calls to create an article.
"""

import os
import json
import unittest
import requests
from djehuty.utils import convenience as conv

TOKEN    = os.getenv("DJEHUTY_TEST_TOKEN")
BASE_URL = "http://127.0.0.1:8080/"
API_BASE_URL = f"{BASE_URL}/v2"
ARTICLE_IDS = [ 12694961, 12689147, 20089760 ]
TIMEOUT = 30

class TestDatasetFunctionality(unittest.TestCase):
    """Class to test various dataset functionalities."""

    def __init__(self, *args, **kwargs):
        """Constructor for this class."""
        super(TestDatasetFunctionality, self).__init__(*args, **kwargs)

    def api_url (self, path):
        """Convenience procedure to construct API URLs."""
        return f"{API_BASE_URL}{path}"

    ## Create, update, view and delete
    ## ------------------------------------------------------------------------
    def test_crud_dataset (self):
        """Tests whether a dataset can be created."""

        ## Create the dataset.
        ## --------------------------------------------------------------------
        response = requests.post(
            url  = self.api_url("/account/articles"),
            data = json.dumps({ "title": "Test article" }),
            headers = {
                "Authorization": f"token {TOKEN}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            timeout = TIMEOUT)

        self.assertEqual(response.status_code, 200)

        data     = response.json()
        self.assertIsNotNone (data)
        location = conv.value_or_none (data, "location")
        self.assertIsNotNone (location)

        dataset_location = location
        dataset_uuid = location.split("/")[-1]

        ## Retrieve the dataset.
        ## --------------------------------------------------------------------
        # Private access.
        response = requests.get(
            url  = dataset_location,
            headers = {
                "Authorization": f"token {TOKEN}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            timeout = TIMEOUT)

        self.assertEqual(response.status_code, 200)

        # Public access to non-published dataset.
        response = requests.get(
            url     = f"{BASE_URL}datasets/{dataset_uuid}",
            headers = { "Accept": "text/html" },
            timeout = TIMEOUT)

        self.assertEqual (response.status_code, 404)

        ## Create private link.
        ## --------------------------------------------------------------------
        response = requests.post(
            url  = self.api_url(f"/account/articles/{dataset_uuid}/private_links"),
            data = json.dumps({ "read_only": True }),
            headers = {
                "Authorization": f"token {TOKEN}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            timeout = TIMEOUT)

        self.assertEqual(response.status_code, 200)

        response = requests.get(
            url  = self.api_url(f"/account/articles/{dataset_uuid}/private_links"),
            headers = {
                "Authorization": f"token {TOKEN}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            timeout = TIMEOUT)

        data     = response.json()
        self.assertIsNotNone (data)
        print(f"Data: {data}")
        link_id = conv.value_or_none (data[0], "id")
        self.assertIsNotNone (link_id)

        ## Delete private link.
        ## --------------------------------------------------------------------
        response = requests.delete(
            url  = self.api_url(f"/account/articles/{dataset_uuid}/private_links/{link_id}"),
            headers = {
                "Authorization": f"token {TOKEN}",
                "Accept": "application/json",
            },
            timeout = TIMEOUT)

        self.assertEqual(response.status_code, 204)

        ## Delete the dataset.
        ## --------------------------------------------------------------------
        response = requests.delete (
            url     = dataset_location,
            headers = { "Authorization": f"token {TOKEN}" },
            timeout = TIMEOUT)

        self.assertEqual(response.status_code, 204)

    def test_get_published_dataset (self):
        """Tests whether a known published dataset can be accessed."""

        # The articles are hand-picked to contain multiple versions,
        # funding and geolocations.
        for article_id in ARTICLE_IDS:

            ## Landing page.
            ## ----------------------------------------------------------------
            response = requests.get(
                url     = f"{BASE_URL}datasets/{article_id}",
                headers = { "Accept": "text/html" },
                timeout = TIMEOUT)

            self.assertEqual (response.status_code, 200)

            ## Export formats.
            ## ----------------------------------------------------------------
            for export_format in [ "refworks", "bibtex", "refman",
                                   "endnote", "datacite", "nlm", "dc" ]:
                response = requests.get(
                    url     = f"{BASE_URL}export/{export_format}/datasets/{article_id}",
                    headers = { "Accept": "*/*" },
                    timeout = TIMEOUT)

                self.assertEqual (response.status_code, 200)

            ## API.
            ## ----------------------------------------------------------------
            response = requests.get(
                url     = f"{BASE_URL}/v2/articles/{article_id}",
                headers = { "Accept": "application/json" },
                timeout = TIMEOUT)

            self.assertEqual (response.status_code, 200)

            ## Versions
            ## ----------------------------------------------------------------
            response = requests.get(
                url     = f"{BASE_URL}/v2/articles/{article_id}/versions",
                headers = { "Accept": "application/json" },
                timeout = TIMEOUT)

            self.assertEqual (response.status_code, 200)

    def test_wrong_api_calls (self):
        """Tests whether the Accept and Content-Type is handled properly."""
        response = requests.put(
            url     = f"{BASE_URL}datasets/{ARTICLE_IDS[0]}",
            headers = { "Content-Type": "application/json" },
            timeout = TIMEOUT)

        self.assertEqual (response.status_code, 405)

        response = requests.post(
            url  = f"{BASE_URL}logout",
            data = "(+ 1 2 3 4)",
            headers = {
                "Accept": "application/s-expression",
                "Content-Type": "application/s-expression"
            },
            timeout = TIMEOUT)

        self.assertEqual (response.status_code, 406)

    def test_search_dataset (self):
        """Tests whether a dataset can be searched."""

        ## UI.
        ## --------------------------------------------------------------------
        response = requests.get(
            url     = f"{BASE_URL}search",
            params  = { "search": "Hello :or: world",
                        "limit": 15,
                        "order": "title",
                        "order_direction": "desc" },
            headers = { "Accept": "text/html" },
            timeout = TIMEOUT)
        self.assertEqual (response.status_code, 200)

        ## API
        ## --------------------------------------------------------------------
        response = requests.post(
            url     = self.api_url("/articles/search"),
            data  = json.dumps({ "search_for": "Test",
                                 "limit": 15,
                                 "order": "title",
                                 "order_direction": "desc" }),
            headers = { "Accept": "application/json",
                        "Content-Type": "application/json" },
            timeout = TIMEOUT)

        self.assertEqual (response.status_code, 200)

    def test_non_existing_dataset (self):
        """Tests whether an unknown dataset can be accessed."""
        response = requests.get(
            url     = f"{BASE_URL}datasets/1234567890",
            headers = { "Accept": "text/html" },
            timeout = TIMEOUT)

        self.assertEqual (response.status_code, 404)
