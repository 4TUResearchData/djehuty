"""
This module describes the API calls to create a collection.
"""

import os
import json
import unittest
import requests
from djehuty.utils import convenience as conv

TOKEN    = os.getenv("DJEHUTY_TEST_TOKEN")
BASE_URL = "http://127.0.0.1:8080/v2"
TIMEOUT  = 30

class TestCollectionCreation(unittest.TestCase):
    """Class to test various collection functionalities."""

    def __init__(self, *args, **kwargs):
        """Constructor for this class."""
        super(TestCollectionCreation, self).__init__(*args, **kwargs)
        self.collection_location = None

    def api_url (self, path):
        """Convenience procedure to construct API URLs."""
        return f"{BASE_URL}{path}"

    ## Create and destroy
    ## ------------------------------------------------------------------------
    def test_create_delete_collection (self):
        """Procedure to test operations on collections."""
        response = requests.post(
            url    = self.api_url("/account/collections"),
            data   = json.dumps({ "title": "Test collection" }),
            headers = {
                "Authorization": f"token {TOKEN}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            timeout = TIMEOUT)

        self.assertEqual(response.status_code, 200)

        data     = response.json()
        location = conv.value_or_none (data, "location")
        self.assertIsNotNone (location)

        response = requests.delete (
            url     = location,
            headers = { "Authorization": f"token {TOKEN}" },
            timeout = TIMEOUT)

        self.assertEqual(response.status_code, 204)

    ## Unauthorized uses
    ## ------------------------------------------------------------------------
    def test_unauthorized_uses (self):
        """Procedure to test unauthorized access to a user's collections."""
        response = requests.post(
            url    = self.api_url("/account/collections"),
            data   = json.dumps({ "title": "Test collection" }),
            headers = {
                "Authorization": "token invalid_token",
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            timeout = TIMEOUT)

        self.assertEqual(response.status_code, 403)
