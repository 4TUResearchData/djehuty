"""
This module tests browsing the admin features.
"""

import os
import unittest
import requests
from djehuty.utils import rdf

TOKEN    = os.getenv("DJEHUTY_TEST_TOKEN")
BASE_URL = "http://127.0.0.1:8080"
TIMEOUT  = 30

class TestAdminFunctionality(unittest.TestCase):
    """Class to test the administrator functionality."""

    def __init__(self, *args, **kwargs):
        super(TestAdminFunctionality, self).__init__(*args, **kwargs)

    ## Access
    ## ------------------------------------------------------------------------
    def test_access (self):
        """Tests whether the admin panel can be reached."""

        for page in [ "dashboard", "users", "maintenance", "exploratory" ]:

            ## No token
            ## ----------------------------------------------------------------
            response = requests.get(
                url  = f"{BASE_URL}/admin/{page}",
                headers = { "Accept": "text/html" },
                timeout = TIMEOUT)

            self.assertEqual (response.status_code, 403)

            ## Wrong token
            ## ----------------------------------------------------------------
            response = requests.get(
                url  = f"{BASE_URL}/admin/{page}",
                headers = {
                    "Cookie": f"djehuty_session=zz{TOKEN}",
                    "Accept": "text/html"
                },
                timeout = TIMEOUT)

            self.assertEqual (response.status_code, 403)

            ## Valid token
            ## ----------------------------------------------------------------
            response = requests.get(
                url  = f"{BASE_URL}/admin/{page}",
                headers = {
                    "Cookie": f"djehuty_session={TOKEN}",
                    "Accept": "text/html"
                },
                timeout = TIMEOUT)

            self.assertEqual (response.status_code, 200)

            ## No acceptable type
            ## ----------------------------------------------------------------
            response = requests.get(
                url  = f"{BASE_URL}/admin/{page}",
                headers = {
                    "Cookie": f"djehuty_session={TOKEN}",
                    "Accept": "application/json"
                },
                timeout = TIMEOUT)

            self.assertEqual (response.status_code, 406)

        ## Non-existent page
        ## ----------------------------------------------------------------
        response = requests.get(
            url  = f"{BASE_URL}/admin/12345asdfg",
            headers = {
                "Cookie": f"djehuty_session={TOKEN}",
                "Accept": "text/html"
            },
            timeout = TIMEOUT)

        self.assertEqual (response.status_code, 404)

    def test_exploratory (self):
        """Specific tests for the exploratory API."""

        ## Types
        ## --------------------------------------------------------------------
        response = requests.get(
            url  = f"{BASE_URL}/v3/explore/types",
            headers = {
                "Cookie": f"djehuty_session={TOKEN}",
                "Accept": "application/json"
            },
            timeout = TIMEOUT)

        self.assertEqual (response.status_code, 200)

        ## Properties
        ## --------------------------------------------------------------------
        response = requests.get(
            url  = f"{BASE_URL}/v3/explore/properties",
            params = { "uri": rdf.DJHT["Dataset"] },
            headers = {
                "Cookie": f"djehuty_session={TOKEN}",
                "Accept": "application/json"
            },
            timeout = TIMEOUT)

        self.assertEqual (response.status_code, 200)

        ## Property values
        ## --------------------------------------------------------------------
        response = requests.get(
            url  = f"{BASE_URL}/v3/explore/property_value_types",
            params = {
                "type": rdf.DJHT["Dataset"],
                "property": rdf.DJHT["container"]
            },
            headers = {
                "Cookie": f"djehuty_session={TOKEN}",
                "Accept": "application/json"
            },
            timeout = TIMEOUT)

        self.assertEqual (response.status_code, 200)
