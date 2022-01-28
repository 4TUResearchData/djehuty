"""
This module describes the API calls to create a collection.
"""

import os
import unittest
import requests
import json
from djehuty.utils import convenience as conv

token    = os.getenv("DJEHUTY_TEST_TOKEN")
base_url = "http://127.0.0.1:8080/v2"

class TestCollectionCreation(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestCollectionCreation, self).__init__(*args, **kwargs)
        self.collection_location = None

    def api_url (self, path):
        return f"{base_url}{path}"

    ## Create and destroy
    ## ------------------------------------------------------------------------
    def test_create_delete_collection (self):
        response = requests.post(
            url    = self.api_url("/account/collections"),
            data   = json.dumps({ "title": "Test collection" }),
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            })

        self.assertEqual(response.status_code, 200)

        data     = response.json()
        location = conv.value_or_none (data, "location")
        self.assertIsNotNone (location)

        response = requests.delete (
            url     = location,
            headers = { "Authorization": f"token {token}" })

        self.assertEqual(response.status_code, 204)

    ## Unauthorized uses
    ## ------------------------------------------------------------------------
    def test_unauthorized_uses (self):
        response = requests.post(
            url    = self.api_url("/account/collections"),
            data   = json.dumps({ "title": "Test collection" }),
            headers = {
                "Authorization": f"token invalid_token",
                "Accept": "application/json",
                "Content-Type": "application/json"
            })

        self.assertEqual(response.status_code, 403)

if __name__ == "__main__":
    unittest.main()
