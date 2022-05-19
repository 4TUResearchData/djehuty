"""
This module describes the API calls to create an article.
"""

import unittest
import requests
import os
import json
from djehuty.utils import convenience as conv

token    = os.getenv("DJEHUTY_TEST_TOKEN")
base_url = "http://127.0.0.1:8080/v2"

class TestArticleCreation(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestArticleCreation, self).__init__(*args, **kwargs)
        self.article_location = None

    def api_url (self, path):
        return f"{base_url}{path}"

    ## Create and destroy
    ## ------------------------------------------------------------------------
    def test_create_delete_article (self):
        response = requests.post(
            url    = self.api_url("/account/articles"),
            data   = json.dumps({ "title": "Test article" }),
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

if __name__ == "__main__":
    unittest.main()
