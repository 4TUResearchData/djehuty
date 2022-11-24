"""
This module contains a test that runs the back-up tool to retrieve data
from a running instance.
"""

import os
import unittest
import requests
import json
import djehuty.utils.convenience as conv
import djehuty.backup.ui as backup_ui

account_id = os.getenv("DJEHUTY_ACCOUNT_ID")
token      = os.getenv("DJEHUTY_TEST_TOKEN")
base_url   = "http://127.0.0.1:8080/v2"

class TestRunBackup(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestRunBackup, self).__init__(*args, **kwargs)
        self.collection_location = None

    ## Create and destroy
    ## ------------------------------------------------------------------------
    def test_run_backup (self):
        """Runs the back-up tool and tests whether it reaches the end."""
        result = backup_ui.main (token, "-", account_id, base_url)
        self.assertTrue (result)
