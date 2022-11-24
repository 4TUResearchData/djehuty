"""
This module tests browsing the admin features.
"""

import os
import unittest
import requests

TOKEN    = os.getenv("DJEHUTY_TEST_TOKEN")
BASE_URL = "http://127.0.0.1:8080"
TIMEOUT  = 30

class TestDepositorFunctionality(unittest.TestCase):
    """Class to test various depositor functionalities."""

    def __init__(self, *args, **kwargs):
        super(TestDepositorFunctionality, self).__init__(*args, **kwargs)

    ## Access
    ## ------------------------------------------------------------------------
    def test_access (self):
        """Tests whether the depositor panel can be reached."""

        for page in [ "dashboard", "datasets", "collections", "profile" ]:

            ## No token
            ## ----------------------------------------------------------------
            response = requests.get(
                url  = f"{BASE_URL}/my/{page}",
                headers = { "Accept": "text/html" },
                timeout = TIMEOUT)

            self.assertEqual (response.status_code, 403)

            ## Wrong token
            ## ----------------------------------------------------------------
            response = requests.get(
                url  = f"{BASE_URL}/my/{page}",
                headers = {
                    "Cookie": f"djehuty_session=zz{TOKEN}",
                    "Accept": "text/html"
                },
                timeout = TIMEOUT)

            self.assertEqual (response.status_code, 403)

            ## Valid token
            ## ----------------------------------------------------------------
            response = requests.get(
                url  = f"{BASE_URL}/my/{page}",
                headers = {
                    "Cookie": f"djehuty_session={TOKEN}",
                    "Accept": "text/html"
                },
                timeout = TIMEOUT)

            self.assertEqual (response.status_code, 200)

            ## No acceptable type
            ## ----------------------------------------------------------------
            response = requests.get(
                url  = f"{BASE_URL}/my/{page}",
                headers = {
                    "Cookie": f"djehuty_session={TOKEN}",
                    "Accept": "application/json"
                },
                timeout = TIMEOUT)

            self.assertEqual (response.status_code, 406)

        ## Non-existent page
        ## ----------------------------------------------------------------
        response = requests.get(
            url  = f"{BASE_URL}/my/12345asdfg",
            headers = {
                "Cookie": f"djehuty_session={TOKEN}",
                "Accept": "text/html"
            },
            timeout = TIMEOUT)

        self.assertEqual (response.status_code, 404)
